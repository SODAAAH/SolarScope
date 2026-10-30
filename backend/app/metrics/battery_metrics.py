from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.integrator import integrate_power_series
from backend.app.metrics.time_utils import format_time_12h

def calculate_battery_metrics(
    records: List[CanonicalRecord],
    nominal_capacity_kwh: float = 16.08,
    reserve_soc: float = 20.0,
    bms_max_current_a: float = 100.0,
    battery_voltage: float = 51.2,
    method: str = "trapezoidal"
) -> Dict[str, Any]:
    if not records:
        return {}

    timestamps = [r.timestamp for r in records]
    batt_powers = [r.battery_power_kw for r in records]
    soc_vals = [r.soc_percent for r in records]
    load_powers = [r.load_power_kw for r in records]

    disch_powers = [max(0.0, b) for b in batt_powers]
    chg_powers = [max(0.0, -b) for b in batt_powers]

    disch_kwh, cum_disch, dur_h = integrate_power_series(timestamps, disch_powers, method=method)
    chg_kwh, cum_chg, _ = integrate_power_series(timestamps, chg_powers, method=method)

    initial_soc = soc_vals[0] if soc_vals else 0.0
    min_soc = min(soc_vals) if soc_vals else 0.0
    max_soc = max(soc_vals) if soc_vals else 0.0
    final_soc = soc_vals[-1] if soc_vals else 0.0
    delta_soc = final_soc - initial_soc
    depth_of_discharge = max(0.0, max_soc - min_soc)

    peak_discharge_kw = max(disch_powers) if disch_powers else 0.0
    peak_charge_kw = max(chg_powers) if chg_powers else 0.0

    reserve_threshold = reserve_soc + 0.5
    at_reserve_intervals = 0
    cutoff_time = None
    for r in records:
        if r.soc_percent <= reserve_threshold:
            at_reserve_intervals += 1
            if cutoff_time is None:
                cutoff_time = r.timestamp
            
    avg_interval_hours = (dur_h / len(records)) if len(records) > 0 else (5.0 / 60.0)
    hours_at_reserve = round(at_reserve_intervals * avg_interval_hours, 2)

    usable_above_reserve_kwh = max(0.0, round(((final_soc - reserve_soc) / 100.0) * nominal_capacity_kwh, 3))

    total_throughput = chg_kwh + disch_kwh
    equivalent_full_cycles = round(total_throughput / (2.0 * nominal_capacity_kwh), 3) if nominal_capacity_kwh > 0 else 0.0

    net_energy_kwh = round(disch_kwh - chg_kwh, 4)

    rte_pct = round((disch_kwh / chg_kwh) * 100.0, 1) if chg_kwh > 0.5 else 95.0

    recent_loads = load_powers[-12:] if len(load_powers) >= 12 else load_powers
    avg_recent_load = (sum(recent_loads) / len(recent_loads)) if recent_loads else 0.5
    if avg_recent_load <= 0.05:
        avg_recent_load = 0.5

    autonomy_hours = round(usable_above_reserve_kwh / avg_recent_load, 1) if avg_recent_load > 0 else 24.0
    autonomy_hours = min(48.0, autonomy_hours)

    whole_h = int(autonomy_hours)
    mins = int(round((autonomy_hours - whole_h) * 60))
    autonomy_formatted = f"{whole_h}h {mins}m"

    bms_limit_kw = round((bms_max_current_a * battery_voltage) / 1000.0, 2)

    return {
        "discharging_energy_kwh": disch_kwh,
        "charging_energy_kwh": chg_kwh,
        "net_battery_kwh": net_energy_kwh,
        "peak_discharge_kw": round(peak_discharge_kw, 3),
        "peak_charge_kw": round(peak_charge_kw, 3),
        "initial_soc_percent": round(initial_soc, 1),
        "min_soc_percent": round(min_soc, 1),
        "max_soc_percent": round(max_soc, 1),
        "final_soc_percent": round(final_soc, 1),
        "delta_soc_percent": round(delta_soc, 1),
        "depth_of_discharge_percent": round(depth_of_discharge, 1),
        "round_trip_efficiency_percent": rte_pct,
        "reserve_soc_percent": round(reserve_soc, 1),
        "reserve_cutoff_time": cutoff_time,
        "reserve_cutoff_time_12h": format_time_12h(cutoff_time),
        "hours_at_reserve_limit": hours_at_reserve,
        "usable_energy_above_reserve_kwh": usable_above_reserve_kwh,
        "estimated_autonomy_hours": autonomy_hours,
        "estimated_autonomy_formatted": autonomy_formatted,
        "equivalent_full_cycles": equivalent_full_cycles,
        "nominal_capacity_kwh": nominal_capacity_kwh,
        "bms_limit_enforced_a": bms_max_current_a,
        "bms_limit_enforced_kw": bms_limit_kw,
        "cumulative_discharge": cum_disch,
        "cumulative_charge": cum_chg
    }
