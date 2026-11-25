import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.integrator import integrate_power_series
from backend.app.metrics.time_utils import format_time_12h, hour_index_to_12h

def _parse_ts_fast(ts_str: str) -> datetime.datetime:
    if len(ts_str) >= 19 and ts_str[10] in (" ", "T"):
        return datetime.datetime.fromisoformat(ts_str[:19])
    return datetime.datetime.fromisoformat(ts_str)

def calculate_grid_metrics(
    records: List[CanonicalRecord],
    reserve_soc: float = 20.0,
    inverter_power_kw: float = 0.0,
    import_tariff: float = 0.0,
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
    first_import_time = None
    last_import_time = None
    for r in records:
        g = r.grid_power_kw
        if g > peak_import:
            peak_import = g
            peak_import_time = r.timestamp
        if g >= 0.1:
            if first_import_time is None:
                first_import_time = r.timestamp
            last_import_time = r.timestamp

    daylight_import_kwh = 0.0
    reserve_import_kwh = 0.0
    reserve_threshold = reserve_soc + 1.0

    cat_reserve_kwh = 0.0
    cat_scheduled_kwh = 0.0
    cat_overnight_kwh = 0.0
    cat_peak_assist_kwh = 0.0
    cat_day_deficit_kwh = 0.0
    cat_trickle_kwh = 0.0

    cat_reserve_count = 0
    cat_scheduled_count = 0
    cat_overnight_count = 0
    cat_peak_assist_count = 0
    cat_day_deficit_count = 0
    cat_trickle_count = 0

    hourly_grid: Dict[int, float] = {h: 0.0 for h in range(24)}
    parsed_times: List[Any] = []
    for r in records:
        try:
            parsed_times.append(_parse_ts_fast(r.timestamp))
        except Exception:
            parsed_times.append(None)

    for i in range(len(records) - 1):
        t0 = parsed_times[i]
        t1 = parsed_times[i + 1]
        if t0 is None or t1 is None:
            continue
        dt_h = (t1 - t0).total_seconds() / 3600.0
        if dt_h <= 0.0:
            continue

        r0 = records[i]
        r1 = records[i + 1]
        avg_grid = 0.5 * (max(0.0, r0.grid_power_kw) + max(0.0, r1.grid_power_kw))
        delta_e = avg_grid * dt_h
        if delta_e <= 0.0:
            continue

        hourly_grid[t0.hour] += delta_e

        avg_pv = 0.5 * (r0.pv_power_kw + r1.pv_power_kw)
        if avg_pv >= 0.2:
            daylight_import_kwh += delta_e

        avg_soc = 0.5 * (r0.soc_percent + r1.soc_percent)
        avg_load = 0.5 * (r0.load_power_kw + r1.load_power_kw)
        avg_batt = 0.5 * (r0.battery_power_kw + r1.battery_power_kw)

        if avg_soc <= reserve_threshold and avg_grid > 0.08:
            reserve_import_kwh += delta_e

        if avg_grid <= 0.08:
            cat_trickle_kwh += delta_e
            cat_trickle_count += 1
        elif avg_batt < -0.1 and avg_grid > 0.1:
            cat_scheduled_kwh += delta_e
            cat_scheduled_count += 1
        elif avg_soc <= reserve_threshold:
            cat_reserve_kwh += delta_e
            cat_reserve_count += 1
        elif (inverter_power_kw > 0 and avg_load > (inverter_power_kw * 0.90)) or avg_batt >= 0.08:
            cat_peak_assist_kwh += delta_e
            cat_peak_assist_count += 1
        elif avg_pv >= 0.15:
            cat_day_deficit_kwh += delta_e
            cat_day_deficit_count += 1
        else:
            cat_overnight_kwh += delta_e
            cat_overnight_count += 1

    total_load_powers = [r.load_power_kw for r in records]
    total_load_kwh, _, _ = integrate_power_series(timestamps, total_load_powers, method=method)

    grid_dependence_ratio = round(import_kwh / total_load_kwh, 4) if total_load_kwh > 0 else 0.0

    hourly_breakdown = [
        {"hour": h, "hour_label_12h": hour_index_to_12h(h), "energy_kwh": round(hourly_grid[h], 4)}
        for h in range(24)
    ]

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
        make_cat_dict(
            "Overnight Grid Standby",
            cat_overnight_kwh,
            cat_overnight_count,
            "Nighttime or low-solar demand supplied by the grid while the battery held charge above reserve."
        ),
        make_cat_dict(
            "Peak Load & Inverter Assist",
            cat_peak_assist_kwh,
            cat_peak_assist_count,
            "Household load exceeded battery discharge or continuous inverter output, requiring grid assist."
        ),
        make_cat_dict(
            "Daytime Solar / Cloud Deficit",
            cat_day_deficit_kwh,
            cat_day_deficit_count,
            "Daylight solar output fell short of demand due to cloud cover or daytime load spikes."
        ),
        make_cat_dict(
            "Scheduled Battery Charging",
            cat_scheduled_kwh,
            cat_scheduled_count,
            "Electricity drawn from the grid to actively recharge the battery bank."
        ),
        make_cat_dict(
            "Battery Reserve Cutoff",
            cat_reserve_kwh,
            cat_reserve_count,
            "Battery reached its configured minimum reserve SOC limit and transferred load to the grid."
        ),
        make_cat_dict(
            "Grid Trickle & Sync",
            cat_trickle_kwh,
            cat_trickle_count,
            "Low background draw (≤80W) maintaining zero-export CT balance and grid synchronization."
        )
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
