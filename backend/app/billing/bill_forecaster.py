import datetime
import numpy as np
from typing import List, Dict, Any, Tuple
from backend.app.ingestion.models import CanonicalRecord
from backend.app.billing.tariff_models import (
    TEIRateSchedule,
    TEIBillingProfile,
    BillForecastResponse,
    BillForecastScenario,
    StatementOfAccount
)
from backend.app.billing.bill_calculator import calculate_statement_of_account
from backend.app.billing.solar_savings import calculate_solar_bill_savings
from backend.app.billing.billing_profile import compute_cycle_dates
from backend.app.metrics.integrator import integrate_power_series

def forecast_tei_bill(
    records: List[CanonicalRecord],
    schedule: TEIRateSchedule,
    profile: TEIBillingProfile,
    last_check_status: Dict[str, Any]
) -> BillForecastResponse:
    cycle_day = max(1, min(31, int(profile.billing_cycle_day or 25)))
    tz_manila = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz_manila)
    start_date, end_date = compute_cycle_dates(cycle_day, now.date())

    cycle_total_days = max(1, (end_date - start_date).days)
    today_date = now.date()
    days_elapsed = min(cycle_total_days, max(1, (today_date - start_date).days))
    days_remaining = max(0, (end_date - today_date).days)

    daily_imports: Dict[str, float] = {}
    daily_exports: Dict[str, float] = {}
    daily_loads: Dict[str, float] = {}
    daily_solar_direct: Dict[str, float] = {}
    daily_battery_disch: Dict[str, float] = {}

    day_records_map: Dict[str, List[CanonicalRecord]] = {}
    for r in records:
        day_str = r.timestamp[:10]
        if day_str not in day_records_map:
            day_records_map[day_str] = []
        day_records_map[day_str].append(r)

    for day_str, recs in day_records_map.items():
        if len(recs) < 2:
            continue
        ts_list = [r.timestamp for r in recs]
        daily_imports[day_str] = integrate_power_series(ts_list, [max(0.0, r.grid_power_kw) for r in recs])[0]
        daily_exports[day_str] = integrate_power_series(ts_list, [max(0.0, -r.grid_power_kw) for r in recs])[0]
        daily_loads[day_str] = integrate_power_series(ts_list, [max(0.0, r.load_power_kw) for r in recs])[0]
        daily_battery_disch[day_str] = integrate_power_series(ts_list, [max(0.0, r.battery_power_kw) for r in recs])[0]

        pv_energy = integrate_power_series(ts_list, [max(0.0, r.pv_power_kw) for r in recs])[0]
        exp_energy = daily_exports[day_str]
        daily_solar_direct[day_str] = max(0.0, pv_energy - exp_energy)

    cycle_days_observed = [d for d in daily_imports.keys() if start_date.strftime("%Y-%m-%d") <= d <= end_date.strftime("%Y-%m-%d")]
    cycle_days_observed.sort()

    actual_imported_kwh = sum(daily_imports[d] for d in cycle_days_observed)
    actual_exported_kwh = sum(daily_exports[d] for d in cycle_days_observed)
    total_home_demand = sum(daily_loads.get(d, 0.0) for d in cycle_days_observed)
    direct_solar_used = sum(daily_solar_direct.get(d, 0.0) for d in cycle_days_observed)
    battery_discharged = sum(daily_battery_disch.get(d, 0.0) for d in cycle_days_observed)

    if profile.latest_meter_reading is not None and profile.prev_meter_reading is not None:
        meter_diff = profile.latest_meter_reading - profile.prev_meter_reading
        if meter_diff > 0:
            actual_imported_kwh = meter_diff

    all_sorted_days = sorted(daily_imports.keys())
    if profile.forecast_method == "7day" and len(all_sorted_days) >= 7:
        sample_days = all_sorted_days[-7:]
    elif profile.forecast_method == "14day" and len(all_sorted_days) >= 14:
        sample_days = all_sorted_days[-14:]
    elif profile.forecast_method == "30day" and len(all_sorted_days) >= 30:
        sample_days = all_sorted_days[-30:]
    elif cycle_days_observed:
        sample_days = cycle_days_observed
    else:
        sample_days = all_sorted_days

    sample_import_values = [daily_imports[d] for d in sample_days] if sample_days else [0.0]
    mean_daily_import = float(np.mean(sample_import_values)) if sample_import_values else 0.0
    std_daily_import = float(np.std(sample_import_values)) if len(sample_import_values) > 1 else (mean_daily_import * 0.20)

    expected_daily_rate = max(0.0, mean_daily_import)
    lower_daily_rate = max(0.0, mean_daily_import - (0.80 * std_daily_import))
    higher_daily_rate = max(expected_daily_rate, mean_daily_import + (0.80 * std_daily_import))

    expected_additional_kwh = round(expected_daily_rate * days_remaining, 2)
    lower_additional_kwh = round(lower_daily_rate * days_remaining, 2)
    higher_additional_kwh = round(higher_daily_rate * days_remaining, 2)

    expected_total_kwh = round(actual_imported_kwh + expected_additional_kwh, 2)
    lower_total_kwh = round(actual_imported_kwh + lower_additional_kwh, 2)
    higher_total_kwh = round(actual_imported_kwh + higher_additional_kwh, 2)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    current_so_far_soa = calculate_statement_of_account(
        billed_kwh=actual_imported_kwh,
        schedule=schedule,
        profile=profile,
        billing_start=start_str,
        billing_end=today_date.strftime("%Y-%m-%d"),
        exported_kwh=actual_exported_kwh,
        is_estimate=True
    )

    expected_soa = calculate_statement_of_account(
        billed_kwh=expected_total_kwh,
        schedule=schedule,
        profile=profile,
        billing_start=start_str,
        billing_end=end_str,
        exported_kwh=actual_exported_kwh,
        is_estimate=True
    )

    lower_soa = calculate_statement_of_account(
        billed_kwh=lower_total_kwh,
        schedule=schedule,
        profile=profile,
        billing_start=start_str,
        billing_end=end_str,
        exported_kwh=actual_exported_kwh,
        is_estimate=True
    )

    higher_soa = calculate_statement_of_account(
        billed_kwh=higher_total_kwh,
        schedule=schedule,
        profile=profile,
        billing_start=start_str,
        billing_end=end_str,
        exported_kwh=actual_exported_kwh,
        is_estimate=True
    )

    expected_scenario = BillForecastScenario(
        name="Expected Forecast",
        description=f"Most likely outcome based on your recent {len(sample_days)}-day average of {expected_daily_rate:.2f} kWh/day.",
        projected_additional_kwh=expected_additional_kwh,
        total_projected_kwh=expected_total_kwh,
        estimated_current_charges=expected_soa.total_current_charges,
        estimated_total_amount=expected_soa.total_amount_due,
        daily_import_rate_kwh=round(expected_daily_rate, 2),
        statement=expected_soa
    )

    lower_scenario = BillForecastScenario(
        name="Lower Cost Scenario",
        description=f"Favorable outcome with reduced night demand and high solar self-sufficiency ({lower_daily_rate:.2f} kWh/day).",
        projected_additional_kwh=lower_additional_kwh,
        total_projected_kwh=lower_total_kwh,
        estimated_current_charges=lower_soa.total_current_charges,
        estimated_total_amount=lower_soa.total_amount_due,
        daily_import_rate_kwh=round(lower_daily_rate, 2),
        statement=lower_soa
    )

    higher_scenario = BillForecastScenario(
        name="Higher Cost Scenario",
        description=f"Conservative estimate reflecting rainy/cloudy weather or heavier air conditioning usage ({higher_daily_rate:.2f} kWh/day).",
        projected_additional_kwh=higher_additional_kwh,
        total_projected_kwh=higher_total_kwh,
        estimated_current_charges=higher_soa.total_current_charges,
        estimated_total_amount=higher_soa.total_amount_due,
        daily_import_rate_kwh=round(higher_daily_rate, 2),
        statement=higher_soa
    )

    solar_savings_data = calculate_solar_bill_savings(
        actual_imported_kwh=actual_imported_kwh,
        actual_exported_kwh=actual_exported_kwh,
        total_home_demand_kwh=total_home_demand,
        direct_solar_used_kwh=direct_solar_used,
        battery_discharged_kwh=battery_discharged,
        schedule=schedule,
        profile=profile,
        billing_start=start_str,
        billing_end=end_str
    )

    gen_charge_val = 0.0
    gen_vat_val = 0.0
    for comp in schedule.components:
        if comp.component_id == "gen_charge":
            gen_charge_val = comp.rate_per_kwh
            gen_vat_val = comp.vat_rate_per_kwh

    coverage_pct = round(min(100.0, (len(cycle_days_observed) / max(1, days_elapsed)) * 100.0), 1)

    return BillForecastResponse(
        billing_cycle_start=start_str,
        billing_cycle_end=end_str,
        next_meter_reading_date=end_str,
        days_elapsed=days_elapsed,
        days_remaining=days_remaining,
        cycle_total_days=cycle_total_days,
        actual_imported_kwh=round(actual_imported_kwh, 2),
        actual_exported_kwh=round(actual_exported_kwh, 2),
        active_rate_effective_month=schedule.effective_month,
        active_generation_charge=gen_charge_val,
        active_generation_vat=gen_vat_val,
        last_rate_check_timestamp=last_check_status.get("checked_at", now.isoformat()),
        rate_monitor_status=last_check_status.get("status", "pending"),
        rate_change_alert=last_check_status.get("rate_change_alert"),
        current_so_far_statement=current_so_far_soa,
        lower_estimate=lower_scenario,
        expected_estimate=expected_scenario,
        higher_estimate=higher_scenario,
        forecasting_method=profile.forecast_method,
        data_coverage_percent=coverage_pct,
        solar_savings=solar_savings_data
    )
