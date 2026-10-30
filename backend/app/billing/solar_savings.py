from typing import Dict, Any, List
from backend.app.billing.tariff_models import TEIRateSchedule, TEIBillingProfile, StatementOfAccount
from backend.app.billing.bill_calculator import calculate_statement_of_account

def calculate_solar_bill_savings(
    actual_imported_kwh: float,
    actual_exported_kwh: float,
    total_home_demand_kwh: float,
    direct_solar_used_kwh: float,
    battery_discharged_kwh: float,
    schedule: TEIRateSchedule,
    profile: TEIBillingProfile,
    billing_start: str,
    billing_end: str
) -> Dict[str, Any]:
    baseline_kwh = max(total_home_demand_kwh, actual_imported_kwh)
    baseline_soa = calculate_statement_of_account(
        billed_kwh=baseline_kwh,
        schedule=schedule,
        profile=profile,
        billing_start=billing_start,
        billing_end=billing_end,
        exported_kwh=0.0,
        is_estimate=True
    )

    actual_soa = calculate_statement_of_account(
        billed_kwh=actual_imported_kwh,
        schedule=schedule,
        profile=profile,
        billing_start=billing_start,
        billing_end=billing_end,
        exported_kwh=actual_exported_kwh,
        is_estimate=True
    )

    savings_amount = max(0.0, round(baseline_soa.total_current_charges - actual_soa.total_current_charges, 2))
    savings_pct = round((savings_amount / baseline_soa.total_current_charges) * 100.0, 1) if baseline_soa.total_current_charges > 0 else 0.0

    avoided_kwh = max(0.0, round(direct_solar_used_kwh + battery_discharged_kwh, 2))
    eff_rate = actual_soa.effective_average_rate_per_kwh if actual_soa.effective_average_rate_per_kwh > 0 else baseline_soa.effective_average_rate_per_kwh

    direct_solar_savings = round(direct_solar_used_kwh * eff_rate, 2)
    battery_savings = round(battery_discharged_kwh * eff_rate, 2)

    return {
        "bill_without_solar": baseline_soa.total_current_charges,
        "bill_with_solar": actual_soa.total_current_charges,
        "savings_pesos": savings_amount,
        "savings_percentage": savings_pct,
        "avoided_grid_kwh": avoided_kwh,
        "direct_solar_used_kwh": round(direct_solar_used_kwh, 2),
        "direct_solar_savings_pesos": direct_solar_savings,
        "battery_discharged_kwh": round(battery_discharged_kwh, 2),
        "battery_savings_pesos": battery_savings,
        "net_metering_credits_pesos": actual_soa.net_metering_credits,
        "household_total_demand_kwh": round(total_home_demand_kwh, 2),
        "actual_imported_kwh": round(actual_imported_kwh, 2),
        "baseline_statement": baseline_soa,
        "actual_statement": actual_soa
    }
