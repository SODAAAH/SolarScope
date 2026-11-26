from typing import List, Dict, Any, Optional
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.integrator import integrate_power_series
from backend.app.metrics.time_utils import format_time_12h

def calculate_battery_metrics(
    records: List[CanonicalRecord],
    nominal_capacity_kwh: float = 0.0,
    reserve_soc: float = 20.0,
    bms_max_current_a: float = 0.0,
    battery_voltage: float = 0.0,
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

    has_soc_telemetry = any(
        "soc_percent" not in r.missing_channels and "soc_percent" not in r.invalid_channels
        for r in records
    )

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
        if has_soc_telemetry and r.soc_percent <= reserve_threshold:
            at_reserve_intervals += 1
            if cutoff_time is None:
                cutoff_time = r.timestamp

    avg_interval_hours = (dur_h / len(records)) if len(records) > 0 and dur_h > 0 else (5.0 / 60.0)
    hours_at_reserve = round(at_reserve_intervals * avg_interval_hours, 2)

    usable_above_reserve_kwh = max(0.0, round(((final_soc - reserve_soc) / 100.0) * nominal_capacity_kwh, 3)) if nominal_capacity_kwh > 0 else 0.0

    total_throughput = chg_kwh + disch_kwh
    if nominal_capacity_kwh > 0:
        equivalent_full_cycles: Optional[float] = round(total_throughput / (2.0 * nominal_capacity_kwh), 3)
        cycles_status = "calculated"
    else:
        equivalent_full_cycles = None
        cycles_status = "unavailable_missing_capacity"

    net_energy_kwh = round(disch_kwh - chg_kwh, 4)
    delta_stored_kwh = round((delta_soc / 100.0) * nominal_capacity_kwh, 4) if nominal_capacity_kwh > 0 else 0.0

    rte_pct: Optional[float] = None
    rte_status = "insufficient_cycle_data"
    rte_note = "Insufficient full charge/discharge cycle throughput in this window to compute physical round-trip efficiency."

    if chg_kwh >= 1.0 and disch_kwh >= 1.0:
        if abs(delta_soc) <= 5.0 and has_soc_telemetry:
            raw_rte = (disch_kwh / chg_kwh) * 100.0
            if 50.0 <= raw_rte <= 100.0:
                rte_pct = round(raw_rte, 1)
                rte_status = "measured_closed_cycle"
                rte_note = "Measured across nearly matched start and end SOC (<=5% delta)."
        elif nominal_capacity_kwh > 0 and total_throughput >= nominal_capacity_kwh * 0.4:
            effective_in = chg_kwh - delta_stored_kwh
            if effective_in > 1.0:
                adj_rte = (disch_kwh / effective_in) * 100.0
                if 50.0 <= adj_rte <= 100.0:
                    rte_pct = round(adj_rte, 1)
                    rte_status = "soc_adjusted_estimate"
                    rte_note = f"Estimated by compensating charge energy for {delta_soc:+.1f}% SOC change ({delta_stored_kwh:+.2f} kWh)."

    recent_loads = load_powers[-12:] if len(load_powers) >= 12 else load_powers
    avg_recent_load = (sum(recent_loads) / len(recent_loads)) if recent_loads else 0.0

    if nominal_capacity_kwh > 0 and avg_recent_load > 0.01 and has_soc_telemetry:
        autonomy_hours = min(48.0, round(usable_above_reserve_kwh / avg_recent_load, 1))
        whole_h = int(autonomy_hours)
        mins = int(round((autonomy_hours - whole_h) * 60))
        autonomy_formatted = f"{whole_h}h {mins}m"
        autonomy_status = "estimated"
    else:
        autonomy_hours = 0.0
        autonomy_formatted = "--"
        autonomy_status = "unavailable"

    bms_limit_kw = round((bms_max_current_a * battery_voltage) / 1000.0, 2) if (bms_max_current_a > 0 and battery_voltage > 0) else 0.0

    return {
        "discharging_energy_kwh": disch_kwh,
        "charging_energy_kwh": chg_kwh,
        "net_battery_kwh": net_energy_kwh,
        "throughput_kwh": round(total_throughput, 4),
        "soc_delta_kwh": delta_stored_kwh,
        "peak_discharge_kw": round(peak_discharge_kw, 3),
        "peak_charge_kw": round(peak_charge_kw, 3),
        "initial_soc_percent": round(initial_soc, 1),
        "min_soc_percent": round(min_soc, 1),
        "max_soc_percent": round(max_soc, 1),
        "final_soc_percent": round(final_soc, 1),
        "delta_soc_percent": round(delta_soc, 1),
        "depth_of_discharge_percent": round(depth_of_discharge, 1),
        "round_trip_efficiency_percent": rte_pct,
        "rte_status": rte_status,
        "rte_note": rte_note,
        "reserve_soc_percent": round(reserve_soc, 1),
        "reserve_cutoff_time": cutoff_time,
        "reserve_cutoff_time_12h": format_time_12h(cutoff_time),
        "hours_at_reserve_limit": hours_at_reserve,
        "usable_energy_above_reserve_kwh": usable_above_reserve_kwh,
        "estimated_autonomy_hours": autonomy_hours,
        "estimated_autonomy_formatted": autonomy_formatted,
        "autonomy_status": autonomy_status,
        "equivalent_full_cycles": equivalent_full_cycles if equivalent_full_cycles is not None else 0.0,
        "cycles_status": cycles_status,
        "nominal_capacity_kwh": nominal_capacity_kwh,
        "bms_limit_enforced_a": bms_max_current_a,
        "bms_limit_enforced_kw": bms_limit_kw,
        "cumulative_discharge": cum_disch,
        "cumulative_charge": cum_chg
    }
