from datetime import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.finance.tariff_engine import TariffConfig, calculate_grid_cost
from backend.app.energy_balance.reconciliation import reconcile_energy_balance

def calculate_financial_performance(
    records: List[CanonicalRecord],
    config: TariffConfig,
    system_capex: float = 0.0,
    annual_degradation: float = 0.008,
    discount_rate: float = 0.06
) -> Dict[str, Any]:
    if not records:
        return {}

    grid_cost = calculate_grid_cost(records, config)
    balance = reconcile_energy_balance(records)

    total_demand_kwh = balance.get("household_demand_kwh", 0.0)
    total_imported_kwh = grid_cost.get("total_imported_kwh", 0.0)

    try:
        t0 = datetime.strptime(records[0].timestamp, "%Y-%m-%d %H:%M:%S")
        t1 = datetime.strptime(records[-1].timestamp, "%Y-%m-%d %H:%M:%S")
        span_days = max(1.0, (t1 - t0).total_seconds() / 86400.0)
    except Exception:
        span_days = 1.0

    daily_imported_kwh = round(total_imported_kwh / span_days, 2)
    daily_demand_kwh = round(total_demand_kwh / span_days, 2)

    effective_tariff = grid_cost.get("effective_rate_per_kwh", config.flat_rate)
    
    daily_import_cost = grid_cost["total_import_cost"] / span_days
    daily_export_credit = grid_cost["total_export_credit"] / span_days
    daily_fixed_charge = grid_cost["fixed_daily_charge"]
    
    daily_grid_cost = round(daily_import_cost + daily_fixed_charge - daily_export_credit, 2)
    hypothetical_full_grid_cost = round((daily_demand_kwh * effective_tariff) + daily_fixed_charge, 2)
    daily_avoided_cost = max(0.0, round(hypothetical_full_grid_cost - daily_grid_cost, 2))

    monthly_savings = round(daily_avoided_cost * 30.5, 2)
    annual_savings = round(daily_avoided_cost * 365.25, 2)

    simple_payback_years = round(system_capex / annual_savings, 2) if (annual_savings > 0 and system_capex > 0) else 0.0

    npv = -system_capex
    cash_flows = []
    for yr in range(1, 11):
        deg_factor = (1.0 - annual_degradation) ** (yr - 1)
        savings_yr = annual_savings * deg_factor
        discounted_savings = savings_yr / ((1.0 + discount_rate) ** yr)
        npv += discounted_savings
        cash_flows.append({
            "year": yr,
            "annual_savings": round(savings_yr, 2),
            "discounted_value": round(discounted_savings, 2)
        })

    return {
        "daily_cost": daily_grid_cost,
        "daily_grid_cost": daily_grid_cost,
        "counterfactual_daily_cost": hypothetical_full_grid_cost,
        "hypothetical_full_grid_cost": hypothetical_full_grid_cost,
        "daily_savings": daily_avoided_cost,
        "daily_avoided_cost": daily_avoided_cost,
        "monthly_savings": monthly_savings,
        "annual_savings": annual_savings,
        "system_capex": system_capex,
        "simple_payback_years": simple_payback_years,
        "ten_year_npv": round(npv, 2),
        "currency": config.currency,
        "cash_flows": cash_flows,
        "observed_daily_import_kwh": daily_imported_kwh,
        "baseline_demand_kwh": daily_demand_kwh,
        "span_days": round(span_days, 1),
        "total_imported_kwh": round(total_imported_kwh, 2),
        "total_demand_kwh": round(total_demand_kwh, 2)
    }
