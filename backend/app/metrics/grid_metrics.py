import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.integrator import integrate_power_series
from backend.app.metrics.time_utils import format_time_12h, hour_index_to_12h

def calculate_grid_metrics(
    records: List[CanonicalRecord],
    reserve_soc: float = 25.0,
    method: str = "trapezoidal"
) -> Dict[str, Any]:
    if not records:
        return {}

    timestamps = [r.timestamp for r in records]
    grid_powers = [r.grid_power_kw for r in records]

    import_powers = [max(0.0, g) for g in grid_powers]
    export_powers = [max(0.0, -g) for g in grid_powers]

    import_kwh, cum_import, dur_h = integrate_power_series(timestamps, import_powers, method=method)
    export_kwh, cum_export, _ = integrate_power_series(timestamps, export_powers, method=method)

    peak_import = 0.0
    peak_import_time = None
    for r in records:
        if r.grid_power_kw > peak_import:
            peak_import = r.grid_power_kw
            peak_import_time = r.timestamp

    first_import_time = None
    last_import_time = None
    for r in records:
        if r.grid_power_kw >= 0.1:
            if first_import_time is None:
                first_import_time = r.timestamp
            last_import_time = r.timestamp

    daylight_import_kwh = 0.0
    reserve_import_kwh = 0.0
    reserve_threshold = reserve_soc + 0.5

    for i in range(len(records) - 1):
        try:
            t0 = datetime.datetime.strptime(records[i].timestamp, "%Y-%m-%d %H:%M:%S")
            t1 = datetime.datetime.strptime(records[i + 1].timestamp, "%Y-%m-%d %H:%M:%S")
            dt_h = (t1 - t0).total_seconds() / 3600.0
            avg_grid = 0.5 * (max(0.0, records[i].grid_power_kw) + max(0.0, records[i + 1].grid_power_kw))
            delta_e = avg_grid * dt_h

            avg_pv = 0.5 * (records[i].pv_power_kw + records[i + 1].pv_power_kw)
            if avg_pv >= 0.2:
                daylight_import_kwh += delta_e

            avg_soc = 0.5 * (records[i].soc_percent + records[i + 1].soc_percent)
            if avg_soc <= reserve_threshold:
                reserve_import_kwh += delta_e
        except Exception:
            continue

    total_load_powers = [r.load_power_kw for r in records]
    total_load_kwh, _, _ = integrate_power_series(timestamps, total_load_powers, method=method)
    
    grid_dependence_ratio = round(import_kwh / total_load_kwh, 4) if total_load_kwh > 0 else 0.0

    hourly_grid: Dict[int, float] = {h: 0.0 for h in range(24)}
    for i in range(len(records) - 1):
        try:
            t0 = datetime.datetime.strptime(records[i].timestamp, "%Y-%m-%d %H:%M:%S")
            t1 = datetime.datetime.strptime(records[i + 1].timestamp, "%Y-%m-%d %H:%M:%S")
            dt_h = (t1 - t0).total_seconds() / 3600.0
            avg_p = 0.5 * (max(0.0, records[i].grid_power_kw) + max(0.0, records[i + 1].grid_power_kw))
            hourly_grid[t0.hour] += avg_p * dt_h
        except Exception:
            continue

    hourly_breakdown = [{"hour": h, "hour_label_12h": hour_index_to_12h(h), "energy_kwh": round(hourly_grid[h], 4)} for h in range(24)]

    return {
        "imported_energy_kwh": import_kwh,
        "exported_energy_kwh": export_kwh,
        "peak_import_kw": round(peak_import, 3),
        "peak_import_time": peak_import_time,
        "peak_import_time_12h": format_time_12h(peak_import_time),
        "first_import_time": first_import_time,
        "first_import_time_12h": format_time_12h(first_import_time),
        "last_import_time": last_import_time,
        "last_import_time_12h": format_time_12h(last_import_time),
        "daylight_import_kwh": round(daylight_import_kwh, 4),
        "reserve_coincident_import_kwh": round(reserve_import_kwh, 4),
        "grid_dependence_ratio": grid_dependence_ratio,
        "cumulative_import": cum_import,
        "cumulative_export": cum_export,
        "hourly_breakdown": hourly_breakdown
    }
