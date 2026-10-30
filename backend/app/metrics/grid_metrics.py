import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.integrator import integrate_power_series
from backend.app.metrics.time_utils import format_time_12h, hour_index_to_12h

def calculate_grid_metrics(
    records: List[CanonicalRecord],
    reserve_soc: float = 20.0,
    inverter_power_kw: float = 6.0,
    import_tariff: float = 11.50,
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
    reserve_threshold = reserve_soc + 1.0

    cat_reserve_kwh = 0.0
    cat_power_limit_kwh = 0.0
    cat_trickle_kwh = 0.0
    cat_scheduled_kwh = 0.0
    cat_unknown_kwh = 0.0

    cat_reserve_count = 0
    cat_power_limit_count = 0
    cat_trickle_count = 0
    cat_scheduled_count = 0
    cat_unknown_count = 0

    for i in range(len(records) - 1):
        try:
            t0 = datetime.datetime.strptime(records[i].timestamp, "%Y-%m-%d %H:%M:%S")
            t1 = datetime.datetime.strptime(records[i + 1].timestamp, "%Y-%m-%d %H:%M:%S")
            dt_h = (t1 - t0).total_seconds() / 3600.0
            avg_grid = 0.5 * (max(0.0, records[i].grid_power_kw) + max(0.0, records[i + 1].grid_power_kw))
            delta_e = avg_grid * dt_h

            if delta_e <= 0.0:
                continue

            avg_pv = 0.5 * (records[i].pv_power_kw + records[i + 1].pv_power_kw)
            if avg_pv >= 0.2:
                daylight_import_kwh += delta_e

            avg_soc = 0.5 * (records[i].soc_percent + records[i + 1].soc_percent)
            avg_load = 0.5 * (records[i].load_power_kw + records[i + 1].load_power_kw)
            avg_batt = 0.5 * (records[i].battery_power_kw + records[i + 1].battery_power_kw)

            if avg_soc <= reserve_threshold:
                reserve_import_kwh += delta_e
                cat_reserve_kwh += delta_e
                cat_reserve_count += 1
            elif avg_batt < -0.1 and avg_grid > 0.1:
                cat_scheduled_kwh += delta_e
                cat_scheduled_count += 1
            elif avg_load > (inverter_power_kw * 0.95):
                cat_power_limit_kwh += delta_e
                cat_power_limit_count += 1
            elif avg_grid <= 0.08:
                cat_trickle_kwh += delta_e
                cat_trickle_count += 1
            else:
                cat_unknown_kwh += delta_e
                cat_unknown_count += 1
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

    def make_cat_dict(name: str, kwh: float, count: int, desc: str):
        pct = round((kwh / import_kwh) * 100.0, 1) if import_kwh > 0 else 0.0
        cost = round(kwh * import_tariff, 2)
        return {
            "category": name,
            "description": desc,
            "energy_kwh": round(kwh, 3),
            "percentage": pct,
            "estimated_cost_php": cost,
            "count": count
        }

    categories = [
        make_cat_dict("Battery Reserve", cat_reserve_kwh, cat_reserve_count, "Battery reached its configured reserve limit and protected essential storage."),
        make_cat_dict("Power Limit", cat_power_limit_kwh, cat_power_limit_count, "Household power demand exceeded inverter capacity or max battery output."),
        make_cat_dict("Grid Trickle", cat_trickle_kwh, cat_trickle_count, "Small background grid import to maintain zero-export inverter stability."),
        make_cat_dict("Scheduled Charging", cat_scheduled_kwh, cat_scheduled_count, "Electricity intentionally drawn to charge the battery."),
        make_cat_dict("Unclassified", cat_unknown_kwh, cat_unknown_count, "Remaining grid import occurrences.")
    ]

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
        "hourly_breakdown": hourly_breakdown,
        "import_classification": categories
    }
