from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.finance.tariff_engine import TariffConfig, calculate_grid_cost
from backend.app.energy_balance.reconciliation import reconcile_energy_balance

def calculate_financial_performance(
    records: List[CanonicalRecord],
    config: TariffConfig,
    system_capex: float = 350000.0,
    annual_degradation: float = 0.008,
    discount_rate: float = 0.06
) -> Dict[str, Any]:
    if not records:
        return {}

    grid_cost = calculate_grid_cost(records, config)
    balance = reconcile_energy_balance(records)

    demand_kwh = balance["household_demand_kwh"]
    solar_supplied_kwh = balance["direct_solar_used_kwh"] + balance["battery_discharged_kwh"]

    effective_tariff = grid_cost.get("effective_rate_per_kwh", config.flat_rate)
    
    daily_grid_cost = grid_cost["net_daily_bill"]
    hypothetical_full_grid_cost = round((demand_kwh * effective_tariff) + grid_cost["fixed_daily_charge"], 2)
    daily_avoided_cost = max(0.0, round(hypothetical_full_grid_cost - daily_grid_cost, 2))

    monthly_savings = round(daily_avoided_cost * 30.0, 2)
    annual_savings = round(daily_avoided_cost * 365.0, 2)

    simple_payback_years = round(system_capex / annual_savings, 2) if annual_savings > 0 else 99.0

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
        "daily_grid_cost": daily_grid_cost,
        "hypothetical_full_grid_cost": hypothetical_full_grid_cost,
        "daily_avoided_cost": daily_avoided_cost,
        "monthly_savings": monthly_savings,
        "annual_savings": annual_savings,
        "system_capex": system_capex,
        "simple_payback_years": simple_payback_years,
        "ten_year_npv": round(npv, 2),
        "currency": config.currency,
        "cash_flows": cash_flows
    }
