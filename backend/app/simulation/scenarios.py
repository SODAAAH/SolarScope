import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord

def simulate_system_scenarios(
    records: List[CanonicalRecord],
    baseline_battery_kwh: float = 0.0,
    add_battery_kwh: float = 0.0,
    baseline_pv_kwp: float = 0.0,
    add_pv_kwp: float = 0.0,
    new_reserve_soc: float = 20.0,
    shift_load_kwh: float = 0.0,
    tariff_rate: float = 0.0,
    inverter_rated_kw: float = 0.0,
    inverter_peak_va: float = 0.0,
    inverter_max_current_a: float = 0.0,
    bms_max_current_a: float = 0.0,
    battery_voltage: float = 0.0,
    mppt_range_v: str = "--",
    pv_max_voltage_v: str = "--"
) -> Dict[str, Any]:
    if not records:
        return {}

    total_baseline_grid_kwh = 0.0
    total_baseline_pv_kwh = 0.0
    total_baseline_load_kwh = 0.0

    try:
        t0_all = datetime.datetime.strptime(records[0].timestamp, "%Y-%m-%d %H:%M:%S")
        t1_all = datetime.datetime.strptime(records[-1].timestamp, "%Y-%m-%d %H:%M:%S")
        span_days = max(1.0, (t1_all - t0_all).total_seconds() / 86400.0)
    except Exception:
        span_days = 1.0

    clipped_energy_kwh = 0.0
    if inverter_max_current_a > 0 and bms_max_current_a > 0:
        effective_bms_current_a = min(inverter_max_current_a, bms_max_current_a)
    else:
        effective_bms_current_a = max(inverter_max_current_a, bms_max_current_a)
    max_battery_charge_kw = round((effective_bms_current_a * battery_voltage) / 1000.0, 2) if (effective_bms_current_a > 0 and battery_voltage > 0) else 0.0

    for i in range(len(records) - 1):
        try:
            t0 = datetime.datetime.strptime(records[i].timestamp, "%Y-%m-%d %H:%M:%S")
            t1 = datetime.datetime.strptime(records[i + 1].timestamp, "%Y-%m-%d %H:%M:%S")
            dt_h = (t1 - t0).total_seconds() / 3600.0
        except Exception:
            dt_h = 5.0 / 60.0

        p_grid = 0.5 * (max(0.0, records[i].grid_power_kw) + max(0.0, records[i + 1].grid_power_kw))
        p_pv = 0.5 * (records[i].pv_power_kw + records[i + 1].pv_power_kw)
        p_load = 0.5 * (records[i].load_power_kw + records[i + 1].load_power_kw)

        total_baseline_grid_kwh += p_grid * dt_h
        total_baseline_pv_kwh += p_pv * dt_h
        total_baseline_load_kwh += p_load * dt_h

        scaled_pv = p_pv * ((baseline_pv_kwp + add_pv_kwp) / baseline_pv_kwp) if baseline_pv_kwp > 0 else p_pv
        if inverter_rated_kw > 0 and scaled_pv > inverter_rated_kw:
            clipped_energy_kwh += (scaled_pv - inverter_rated_kw) * dt_h

    daily_grid_kwh = total_baseline_grid_kwh / span_days
    daily_pv_kwh = total_baseline_pv_kwh / span_days
    daily_load_kwh = total_baseline_load_kwh / span_days
    daily_clipped_kwh = clipped_energy_kwh / span_days

    pv_scale = (baseline_pv_kwp + add_pv_kwp) / baseline_pv_kwp if baseline_pv_kwp > 0 else 1.0
    unconstrained_new_pv_kwh = daily_pv_kwh * pv_scale
    effective_new_pv_kwh = max(0.0, unconstrained_new_pv_kwh - daily_clipped_kwh)
    net_extra_pv_kwh = max(0.0, effective_new_pv_kwh - daily_pv_kwh)

    max_daily_battery_absorption = add_battery_kwh * 0.90
    battery_absorption_kwh = min(max_daily_battery_absorption, net_extra_pv_kwh + (daily_grid_kwh * 0.35))

    reserve_delta_pct = max(0.0, 20.0 - new_reserve_soc)
    reserve_energy_released_kwh = (reserve_delta_pct / 100.0) * baseline_battery_kwh if baseline_battery_kwh > 0 else 0.0

    achievable_grid_reduction = min(
        daily_grid_kwh,
        battery_absorption_kwh + reserve_energy_released_kwh + (shift_load_kwh * 0.85)
    )

    modeled_daily_grid_kwh = max(0.0, round(daily_grid_kwh - achievable_grid_reduction, 3))
    grid_reduction_pct = round((achievable_grid_reduction / daily_grid_kwh) * 100.0, 1) if daily_grid_kwh > 0 else 0.0

    daily_savings_php = round(achievable_grid_reduction * tariff_rate, 2)
    monthly_savings_php = round(daily_savings_php * 30.5, 2)
    annual_savings_php = round(daily_savings_php * 365.25, 2)

    battery_cost_est = add_battery_kwh * 22000.0
    pv_cost_est = add_pv_kwp * 28000.0
    total_est_cost = battery_cost_est + pv_cost_est
    payback_years = round(total_est_cost / annual_savings_php, 2) if (annual_savings_php > 0 and total_est_cost > 0) else 0.0

    discount_rate = 0.06
    degradation = 0.005
    inflation = 0.035
    cum_cash_flow = -total_est_cost
    for yr in range(1, 11):
        adj_sav = annual_savings_php * ((1.0 - degradation) ** (yr - 1)) * ((1.0 + inflation) ** (yr - 1))
        disc_val = adj_sav / ((1.0 + discount_rate) ** yr)
        cum_cash_flow += disc_val
    npv_10yr = round(cum_cash_flow, 2)

    avg_night_power = (daily_load_kwh * 0.45) / 12.0 if daily_load_kwh > 0 else 0.0
    added_autonomy_hours = round(battery_absorption_kwh / avg_night_power, 1) if avg_night_power > 0 else 0.0
    autonomy_formatted = f"+{int(added_autonomy_hours)}h {int(round((added_autonomy_hours - int(added_autonomy_hours)) * 60))}m"

    electrical_limits_report = {
        "inverter_rated_continuous_kw": inverter_rated_kw,
        "inverter_peak_apparent_va": inverter_peak_va,
        "inverter_max_battery_current_a": inverter_max_current_a,
        "bms_configured_limit_a": bms_max_current_a,
        "effective_battery_current_limit_a": effective_bms_current_a,
        "max_battery_charge_power_kw": max_battery_charge_kw,
        "pv_mppt_operating_range_v": mppt_range_v,
        "pv_max_voltage_v": pv_max_voltage_v,
        "daily_inverter_clipped_kwh": round(daily_clipped_kwh, 3),
        "is_clipping_observed": inverter_rated_kw > 0 and daily_clipped_kwh > 0.1
    }

    def build_option(name: str, batt_kwh: float, pv_kwp: float, desc: str):
        b_cost = batt_kwh * 22000.0
        p_cost = pv_kwp * 28000.0
        tot_cost = b_cost + p_cost
        red_kwh = min(daily_grid_kwh, (batt_kwh * 0.80) + (pv_kwp * 2.2))
        d_sav = red_kwh * tariff_rate
        a_sav = d_sav * 365.25
        pb = round(tot_cost / a_sav, 2) if (a_sav > 0 and tot_cost > 0) else 0.0
        c_npv = -tot_cost
        for y in range(1, 11):
            s = a_sav * ((1.0 - degradation) ** (y - 1)) * ((1.0 + inflation) ** (y - 1))
            c_npv += s / ((1.0 + discount_rate) ** y)
        return {
            "name": name,
            "description": desc,
            "added_battery_kwh": batt_kwh,
            "added_pv_kwp": pv_kwp,
            "estimated_cost_php": tot_cost,
            "daily_grid_reduction_kwh": round(red_kwh, 2),
            "monthly_savings_php": round(d_sav * 30.5, 2),
            "payback_years": pb,
            "ten_year_npv_php": round(c_npv, 2)
        }

    comparison_options = [
        build_option("Option A: Storage Expansion", 5.0, 0.0, "Add 5 kWh battery storage to absorb excess daytime solar for nighttime loads."),
        build_option("Option B: Array Expansion", 0.0, 1.0, "Add 1.0 kWp of solar panel capacity to boost morning and afternoon generation."),
        build_option("Option C: Balanced Storage & PV", 5.0, 1.0, "Add 5 kWh battery and 1.0 kWp PV capacity for higher self-sufficiency."),
        build_option("Option D: High-Capacity Storage", 10.0, 0.0, "Add 10 kWh storage capacity for extended multi-day backup autonomy.")
    ]

    return {
        "status": "HARDWARE_CONSTRAINED_SIMULATION",
        "inputs": {
            "baseline_battery_kwh": baseline_battery_kwh,
            "added_battery_kwh": add_battery_kwh,
            "baseline_pv_kwp": baseline_pv_kwp,
            "added_pv_kwp": add_pv_kwp,
            "new_reserve_soc": new_reserve_soc,
            "shifted_load_kwh": shift_load_kwh,
            "tariff_rate": tariff_rate
        },
        "baseline": {
            "daily_grid_import_kwh": round(daily_grid_kwh, 2),
            "daily_solar_yield_kwh": round(daily_pv_kwh, 2),
            "daily_household_load_kwh": round(daily_load_kwh, 2),
            "span_days": round(span_days, 1)
        },
        "modeled_result": {
            "modeled_daily_grid_kwh": modeled_daily_grid_kwh,
            "daily_grid_reduction_kwh": round(achievable_grid_reduction, 2),
            "grid_reduction_percentage": grid_reduction_pct,
            "added_night_autonomy_hours": added_autonomy_hours,
            "added_night_autonomy_formatted": autonomy_formatted,
            "daily_savings_php": daily_savings_php,
            "monthly_savings_php": monthly_savings_php,
            "annual_savings_php": annual_savings_php,
            "estimated_investment_cost_php": total_est_cost,
            "simple_payback_years": payback_years,
            "ten_year_npv_php": npv_10yr
        },
        "electrical_limits": electrical_limits_report,
        "comparison_options": comparison_options
    }
