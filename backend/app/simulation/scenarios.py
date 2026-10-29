import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord

def simulate_system_scenarios(
    records: List[CanonicalRecord],
    baseline_battery_kwh: float = 15.0,
    add_battery_kwh: float = 5.0,
    baseline_pv_kwp: float = 5.0,
    add_pv_kwp: float = 2.0,
    new_reserve_soc: float = 20.0,
    shift_load_kwh: float = 2.0,
    tariff_rate: float = 11.50
) -> Dict[str, Any]:
    if not records:
        return {}

    total_baseline_grid_kwh = 0.0
    total_baseline_pv_kwh = 0.0
    total_baseline_load_kwh = 0.0

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

    pv_scale_factor = (baseline_pv_kwp + add_pv_kwp) / baseline_pv_kwp if baseline_pv_kwp > 0 else 1.0
    modeled_pv_kwh = round(total_baseline_pv_kwh * pv_scale_factor, 3)

    extra_pv_generated_kwh = modeled_pv_kwh - total_baseline_pv_kwh
    extra_solar_absorbed_kwh = min(extra_pv_generated_kwh * 0.70, add_battery_kwh)

    current_reserve_soc = 25.0
    reserve_delta_pct = max(0.0, current_reserve_soc - new_reserve_soc)
    usable_reserve_discharge_kwh = (reserve_delta_pct / 100.0) * baseline_battery_kwh

    total_simulated_battery_kwh = baseline_battery_kwh + add_battery_kwh
    expanded_battery_absorption_kwh = min(total_baseline_grid_kwh * 0.45, add_battery_kwh * 0.85)

    modeled_grid_reduction_kwh = min(
        total_baseline_grid_kwh,
        expanded_battery_absorption_kwh + usable_reserve_discharge_kwh + (shift_load_kwh * 0.80)
    )

    modeled_grid_kwh = max(0.0, round(total_baseline_grid_kwh - modeled_grid_reduction_kwh, 3))
    
    baseline_daily_cost = round(total_baseline_grid_kwh * tariff_rate, 2)
    modeled_daily_cost = round(modeled_grid_kwh * tariff_rate, 2)
    daily_incremental_savings = round(baseline_daily_cost - modeled_daily_cost, 2)
    annual_incremental_savings = round(daily_incremental_savings * 365.0, 2)

    battery_est_cost = add_battery_kwh * 25000.0
    pv_est_cost = add_pv_kwp * 35000.0
    total_upgrade_cost = battery_est_cost + pv_est_cost
    upgrade_payback_years = round(total_upgrade_cost / annual_incremental_savings, 2) if annual_incremental_savings > 0 else 99.0

    return {
        "status": "MODELED_SIMULATION",
        "assumptions": {
            "baseline_battery_kwh": baseline_battery_kwh,
            "added_battery_kwh": add_battery_kwh,
            "baseline_pv_kwp": baseline_pv_kwp,
            "added_pv_kwp": add_pv_kwp,
            "new_reserve_soc": new_reserve_soc,
            "shifted_load_kwh": shift_load_kwh,
            "tariff_rate": tariff_rate
        },
        "baseline_grid_kwh": round(total_baseline_grid_kwh, 3),
        "modeled_grid_kwh": modeled_grid_kwh,
        "grid_reduction_kwh": round(modeled_grid_reduction_kwh, 3),
        "grid_reduction_percent": round((modeled_grid_reduction_kwh / total_baseline_grid_kwh) * 100.0, 1) if total_baseline_grid_kwh > 0 else 0.0,
        "baseline_daily_cost": baseline_daily_cost,
        "modeled_daily_cost": modeled_daily_cost,
        "daily_incremental_savings": daily_incremental_savings,
        "annual_incremental_savings": annual_incremental_savings,
        "total_upgrade_cost": total_upgrade_cost,
        "upgrade_payback_years": upgrade_payback_years
    }
