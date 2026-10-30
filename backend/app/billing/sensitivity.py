from typing import Dict, Any, Optional
from backend.app.billing.tariff_models import TEIRateSchedule, TEIBillingProfile, StatementOfAccount
from backend.app.billing.bill_calculator import calculate_statement_of_account

def simulate_rate_sensitivity(
    base_kwh: float,
    schedule: TEIRateSchedule,
    profile: TEIBillingProfile,
    billing_start: str,
    billing_end: str,
    delta_gen_rate: float = 0.0,
    delta_usage_pct: float = 0.0,
    custom_kwh: Optional[float] = None
) -> Dict[str, Any]:
    base_kwh = max(0.0, float(base_kwh))
    baseline_soa = calculate_statement_of_account(
        billed_kwh=base_kwh,
        schedule=schedule,
        profile=profile,
        billing_start=billing_start,
        billing_end=billing_end,
        is_estimate=True
    )

    if custom_kwh is not None and custom_kwh >= 0:
        simulated_kwh = float(custom_kwh)
    else:
        multiplier = 1.0 + (delta_usage_pct / 100.0)
        simulated_kwh = max(0.0, base_kwh * multiplier)

    sim_schedule = schedule.model_copy(deep=True)
    if delta_gen_rate != 0.0:
        for comp in sim_schedule.components:
            if comp.component_id == "gen_charge":
                comp.rate_per_kwh = max(0.0, comp.rate_per_kwh + delta_gen_rate)

    simulated_soa = calculate_statement_of_account(
        billed_kwh=simulated_kwh,
        schedule=sim_schedule,
        profile=profile,
        billing_start=billing_start,
        billing_end=billing_end,
        is_estimate=True
    )

    diff_amount = round(simulated_soa.total_current_charges - baseline_soa.total_current_charges, 2)
    diff_pct = round((diff_amount / baseline_soa.total_current_charges) * 100.0, 1) if baseline_soa.total_current_charges > 0 else 0.0

    return {
        "baseline_kwh": round(base_kwh, 2),
        "simulated_kwh": round(simulated_kwh, 2),
        "delta_gen_rate": delta_gen_rate,
        "delta_usage_pct": delta_usage_pct,
        "baseline_bill": baseline_soa.total_current_charges,
        "simulated_bill": simulated_soa.total_current_charges,
        "difference_pesos": diff_amount,
        "difference_percentage": diff_pct,
        "baseline_statement": baseline_soa,
        "simulated_statement": simulated_soa
    }
