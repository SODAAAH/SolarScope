import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.integrator import integrate_power_series
from backend.app.metrics.time_utils import format_time_12h, hour_index_to_12h

def calculate_solar_metrics(
    records: List[CanonicalRecord],
    pv_capacity_kwp: float = 0.0,
    inverter_rating_kw: float = 0.0,
    method: str = "trapezoidal"
) -> Dict[str, Any]:
    if not records:
        return {}

    timestamps = [r.timestamp for r in records]
    pv_powers = [r.pv_power_kw for r in records]

    total_kwh, cumulative, duration_h = integrate_power_series(timestamps, pv_powers, method=method)

    peak_power = 0.0
    peak_time = None
    for r in records:
        if r.pv_power_kw > peak_power:
            peak_power = r.pv_power_kw
            peak_time = r.timestamp

    startup_time = None
    shutdown_time = None
    for r in records:
        if r.pv_power_kw >= 0.05 and startup_time is None:
            startup_time = r.timestamp
        if r.pv_power_kw >= 0.05:
            shutdown_time = r.timestamp

    specific_yield = round(total_kwh / pv_capacity_kwp, 3) if pv_capacity_kwp > 0 else 0.0
    
    theoretical_max = pv_capacity_kwp * (duration_h if duration_h > 0 else 24.0)
    capacity_factor = round((total_kwh / theoretical_max) * 100.0, 2) if theoretical_max > 0 else 0.0

    near_peak_count = 0
    if inverter_rating_kw > 0:
        clipping_threshold = min(inverter_rating_kw, peak_power) * 0.98
        for p in pv_powers:
            if p >= clipping_threshold and p > 1.0:
                near_peak_count += 1

    clipping_suspected = inverter_rating_kw > 0 and near_peak_count >= 8

    hourly_energy: Dict[int, float] = {h: 0.0 for h in range(24)}
    for i in range(len(records) - 1):
        try:
            t0 = datetime.datetime.strptime(records[i].timestamp, "%Y-%m-%d %H:%M:%S")
            t1 = datetime.datetime.strptime(records[i + 1].timestamp, "%Y-%m-%d %H:%M:%S")
            dt_h = (t1 - t0).total_seconds() / 3600.0
            avg_p = 0.5 * (records[i].pv_power_kw + records[i + 1].pv_power_kw)
            hourly_energy[t0.hour] += avg_p * dt_h
        except Exception:
            continue

    hourly_breakdown = [{"hour": h, "hour_label_12h": hour_index_to_12h(h), "energy_kwh": round(hourly_energy[h], 4)} for h in range(24)]

    return {
        "total_generation_kwh": total_kwh,
        "peak_power_kw": round(peak_power, 3),
        "peak_power_time": peak_time,
        "peak_power_time_12h": format_time_12h(peak_time),
        "specific_yield_kwh_per_kwp": specific_yield,
        "capacity_factor_percent": capacity_factor,
        "pv_capacity_kwp": pv_capacity_kwp,
        "duration_hours": duration_h,
        "startup_time": startup_time,
        "startup_time_12h": format_time_12h(startup_time),
        "shutdown_time": shutdown_time,
        "shutdown_time_12h": format_time_12h(shutdown_time),
        "clipping_suspected": clipping_suspected,
        "near_peak_intervals": near_peak_count,
        "cumulative_curve": cumulative,
        "hourly_breakdown": hourly_breakdown
    }
