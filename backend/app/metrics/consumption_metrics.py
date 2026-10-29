import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.integrator import integrate_power_series
from backend.app.metrics.time_utils import format_time_12h, hour_index_to_12h

def calculate_consumption_metrics(
    records: List[CanonicalRecord],
    method: str = "trapezoidal"
) -> Dict[str, Any]:
    if not records:
        return {}

    timestamps = [r.timestamp for r in records]
    loads = [r.load_power_kw for r in records]

    total_kwh, cumulative, duration_h = integrate_power_series(timestamps, loads, method=method)

    peak_load = 0.0
    peak_time = None
    for r in records:
        if r.load_power_kw > peak_load:
            peak_load = r.load_power_kw
            peak_time = r.timestamp

    avg_load = sum(loads) / len(loads) if loads else 0.0
    load_factor = round(avg_load / peak_load, 3) if peak_load > 0 else 0.0
    par = round(peak_load / avg_load, 3) if avg_load > 0 else 0.0

    night_early_loads = []
    daytime_kwh = 0.0
    nighttime_kwh = 0.0
    coincident_solar_load_kwh = 0.0

    for i in range(len(records) - 1):
        try:
            t0 = datetime.datetime.strptime(records[i].timestamp, "%Y-%m-%d %H:%M:%S")
            t1 = datetime.datetime.strptime(records[i + 1].timestamp, "%Y-%m-%d %H:%M:%S")
            dt_h = (t1 - t0).total_seconds() / 3600.0
            avg_p = 0.5 * (records[i].load_power_kw + records[i + 1].load_power_kw)
            delta_e = avg_p * dt_h

            if 2 <= t0.hour <= 5:
                night_early_loads.append(records[i].load_power_kw)

            if 6 <= t0.hour < 18:
                daytime_kwh += delta_e
            else:
                nighttime_kwh += delta_e

            avg_pv = 0.5 * (records[i].pv_power_kw + records[i + 1].pv_power_kw)
            if avg_pv >= 0.1:
                coincident_solar_load_kwh += delta_e
        except Exception:
            continue

    if night_early_loads:
        sorted_early = sorted(night_early_loads)
        idx_5p = max(0, int(len(sorted_early) * 0.05))
        base_load_estimate = sorted_early[idx_5p]
    else:
        sorted_all = sorted(loads)
        idx_5p = max(0, int(len(sorted_all) * 0.05))
        base_load_estimate = sorted_all[idx_5p] if sorted_all else 0.0

    hourly_load: Dict[int, float] = {h: 0.0 for h in range(24)}
    for i in range(len(records) - 1):
        try:
            t0 = datetime.datetime.strptime(records[i].timestamp, "%Y-%m-%d %H:%M:%S")
            t1 = datetime.datetime.strptime(records[i + 1].timestamp, "%Y-%m-%d %H:%M:%S")
            dt_h = (t1 - t0).total_seconds() / 3600.0
            avg_p = 0.5 * (records[i].load_power_kw + records[i + 1].load_power_kw)
            hourly_load[t0.hour] += avg_p * dt_h
        except Exception:
            continue

    hourly_breakdown = [{"hour": h, "hour_label_12h": hour_index_to_12h(h), "energy_kwh": round(hourly_load[h], 4)} for h in range(24)]

    return {
        "total_demand_kwh": total_kwh,
        "peak_load_kw": round(peak_load, 3),
        "peak_load_time": peak_time,
        "peak_load_time_12h": format_time_12h(peak_time),
        "average_load_kw": round(avg_load, 3),
        "base_load_estimate_kw": round(base_load_estimate, 3),
        "load_factor": load_factor,
        "peak_to_average_ratio": par,
        "daytime_demand_kwh": round(daytime_kwh, 4),
        "nighttime_demand_kwh": round(nighttime_kwh, 4),
        "coincident_solar_load_kwh": round(coincident_solar_load_kwh, 4),
        "cumulative_curve": cumulative,
        "hourly_breakdown": hourly_breakdown
    }
