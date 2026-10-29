import datetime
from collections import defaultdict
from typing import List, Dict, Any, Optional
import numpy as np

from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.integrator import integrate_power_series
from backend.app.metrics.time_utils import format_time_12h

def calculate_daily_summaries(
    records: List[CanonicalRecord],
    pv_capacity_kwp: float = 5.0,
    nominal_battery_kwh: float = 15.0,
    reserve_soc: float = 25.0
) -> List[Dict[str, Any]]:
    if not records:
        return []

    day_buckets: Dict[str, List[CanonicalRecord]] = defaultdict(list)
    for r in records:
        day_str = r.timestamp[:10]
        day_buckets[day_str].append(r)

    summaries: List[Dict[str, Any]] = []

    for day_str in sorted(day_buckets.keys()):
        day_recs = day_buckets[day_str]
        timestamps = [r.timestamp for r in day_recs]

        pv_series = [r.pv_power_kw for r in day_recs]
        load_series = [r.load_power_kw for r in day_recs]
        grid_import_series = [max(0.0, r.grid_power_kw) for r in day_recs]
        grid_export_series = [abs(min(0.0, r.grid_power_kw)) for r in day_recs]
        batt_disch_series = [max(0.0, r.battery_power_kw) for r in day_recs]
        batt_chg_series = [abs(min(0.0, r.battery_power_kw)) for r in day_recs]
        soc_series = [r.soc_percent for r in day_recs]

        pv_kwh, _, dur_hours = integrate_power_series(timestamps, pv_series)
        load_kwh, _, _ = integrate_power_series(timestamps, load_series)
        grid_import_kwh, _, _ = integrate_power_series(timestamps, grid_import_series)
        grid_export_kwh, _, _ = integrate_power_series(timestamps, grid_export_series)
        batt_disch_kwh, _, _ = integrate_power_series(timestamps, batt_disch_series)
        batt_chg_kwh, _, _ = integrate_power_series(timestamps, batt_chg_series)

        residual_kwh = round((pv_kwh + batt_disch_kwh + grid_import_kwh) - (load_kwh + batt_chg_kwh + grid_export_kwh), 4)

        peak_pv_val = max(pv_series) if pv_series else 0.0
        peak_pv_idx = pv_series.index(peak_pv_val) if pv_series else 0
        peak_pv_time = timestamps[peak_pv_idx] if timestamps else ""

        peak_load_val = max(load_series) if load_series else 0.0
        peak_load_idx = load_series.index(peak_load_val) if load_series else 0
        peak_load_time = timestamps[peak_load_idx] if timestamps else ""

        peak_grid_val = max(grid_import_series) if grid_import_series else 0.0
        peak_grid_idx = grid_import_series.index(peak_grid_val) if grid_import_series else 0
        peak_grid_time = timestamps[peak_grid_idx] if timestamps else ""

        daytime_pv_kwh = 0.0
        daytime_load_kwh = 0.0
        nighttime_load_kwh = 0.0

        for r in day_recs:
            hour = int(r.timestamp[11:13]) if len(r.timestamp) >= 13 else 12
            if 6 <= hour < 18:
                daytime_pv_kwh += r.pv_power_kw
                daytime_load_kwh += r.load_power_kw
            else:
                nighttime_load_kwh += r.load_power_kw

        coverage_pct = round(min(100.0, (dur_hours / 24.0) * 100.0), 1)
        if coverage_pct >= 90.0:
            status = "COMPLETE"
        elif coverage_pct >= 10.0:
            status = "PARTIAL"
        else:
            status = "INVALID"

        max_gap_min = 0.0
        for i in range(len(timestamps) - 1):
            try:
                t0 = datetime.datetime.fromisoformat(timestamps[i])
                t1 = datetime.datetime.fromisoformat(timestamps[i + 1])
                diff_m = (t1 - t0).total_seconds() / 60.0
                if diff_m > max_gap_min:
                    max_gap_min = diff_m
            except ValueError:
                continue

        grid_import_duration_hours = 0.0
        for i in range(len(timestamps) - 1):
            if grid_import_series[i] > 0.05:
                try:
                    t0 = datetime.datetime.fromisoformat(timestamps[i])
                    t1 = datetime.datetime.fromisoformat(timestamps[i + 1])
                    grid_import_duration_hours += (t1 - t0).total_seconds() / 3600.0
                except ValueError:
                    continue

        self_consumption = round((pv_kwh - grid_export_kwh) / pv_kwh, 4) if pv_kwh > 0 else 0.0
        self_sufficiency = round((load_kwh - grid_import_kwh) / load_kwh, 4) if load_kwh > 0 else 0.0
        grid_dependence = round(grid_import_kwh / load_kwh, 4) if load_kwh > 0 else 0.0

        summaries.append({
            "date": day_str,
            "status": status,
            "coverage_pct": coverage_pct,
            "record_count": len(day_recs),
            "duration_hours": round(dur_hours, 2),
            "longest_gap_min": round(max_gap_min, 1),
            "pv_kwh": pv_kwh,
            "load_kwh": load_kwh,
            "grid_import_kwh": grid_import_kwh,
            "grid_export_kwh": grid_export_kwh,
            "battery_discharge_kwh": batt_disch_kwh,
            "battery_charge_kwh": batt_chg_kwh,
            "residual_kwh": residual_kwh,
            "self_consumption_ratio": min(1.0, max(0.0, self_consumption)),
            "self_sufficiency_ratio": min(1.0, max(0.0, self_sufficiency)),
            "grid_dependence_ratio": min(1.0, max(0.0, grid_dependence)),
            "start_soc": soc_series[0] if soc_series else 0.0,
            "end_soc": soc_series[-1] if soc_series else 0.0,
            "min_soc": min(soc_series) if soc_series else 0.0,
            "max_soc": max(soc_series) if soc_series else 0.0,
            "avg_soc": round(float(np.mean(soc_series)), 1) if soc_series else 0.0,
            "peak_pv_kw": peak_pv_val,
            "peak_pv_time_12h": format_time_12h(peak_pv_time),
            "peak_load_kw": peak_load_val,
            "peak_load_time_12h": format_time_12h(peak_load_time),
            "peak_grid_kw": peak_grid_val,
            "peak_grid_time_12h": format_time_12h(peak_grid_time),
            "grid_import_hours": round(grid_import_duration_hours, 2)
        })

    return summaries

def calculate_weekly_summaries(daily_summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not daily_summaries:
        return []

    week_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for day in daily_summaries:
        try:
            dt = datetime.date.fromisoformat(day["date"])
            iso_year, iso_week, _ = dt.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            week_map[week_key].append(day)
        except ValueError:
            continue

    weeks: List[Dict[str, Any]] = []
    for w_key in sorted(week_map.keys()):
        days = week_map[w_key]
        pv_list = [d["pv_kwh"] for d in days]
        load_list = [d["load_kwh"] for d in days]
        grid_list = [d["grid_import_kwh"] for d in days]
        complete_count = sum(1 for d in days if d["status"] == "COMPLETE")

        weeks.append({
            "week": w_key,
            "start_date": days[0]["date"],
            "end_date": days[-1]["date"],
            "days_observed": len(days),
            "complete_days": complete_count,
            "total_pv_kwh": round(sum(pv_list), 2),
            "mean_daily_pv_kwh": round(float(np.mean(pv_list)), 2) if pv_list else 0.0,
            "median_daily_pv_kwh": round(float(np.median(pv_list)), 2) if pv_list else 0.0,
            "total_load_kwh": round(sum(load_list), 2),
            "mean_daily_load_kwh": round(float(np.mean(load_list)), 2) if load_list else 0.0,
            "median_daily_load_kwh": round(float(np.median(load_list)), 2) if load_list else 0.0,
            "total_grid_import_kwh": round(sum(grid_list), 2),
            "mean_daily_grid_kwh": round(float(np.mean(grid_list)), 2) if grid_list else 0.0
        })

    return weeks

def calculate_monthly_summaries(daily_summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not daily_summaries:
        return []

    month_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for day in daily_summaries:
        month_key = day["date"][:7]
        month_map[month_key].append(day)

    months: List[Dict[str, Any]] = []
    for m_key in sorted(month_map.keys()):
        days = month_map[m_key]
        pv_list = [d["pv_kwh"] for d in days]
        load_list = [d["load_kwh"] for d in days]
        grid_list = [d["grid_import_kwh"] for d in days]
        complete_count = sum(1 for d in days if d["status"] == "COMPLETE")
        partial_count = sum(1 for d in days if d["status"] == "PARTIAL")

        best_day = max(days, key=lambda d: d["pv_kwh"]) if days else None
        worst_day = min(days, key=lambda d: d["pv_kwh"]) if days else None

        months.append({
            "month": m_key,
            "days_observed": len(days),
            "complete_days": complete_count,
            "partial_days": partial_count,
            "total_pv_kwh": round(sum(pv_list), 2),
            "mean_daily_pv_kwh": round(float(np.mean(pv_list)), 2) if pv_list else 0.0,
            "median_daily_pv_kwh": round(float(np.median(pv_list)), 2) if pv_list else 0.0,
            "std_daily_pv_kwh": round(float(np.std(pv_list)), 2) if len(pv_list) > 1 else 0.0,
            "total_load_kwh": round(sum(load_list), 2),
            "mean_daily_load_kwh": round(float(np.mean(load_list)), 2) if load_list else 0.0,
            "median_daily_load_kwh": round(float(np.median(load_list)), 2) if load_list else 0.0,
            "total_grid_import_kwh": round(sum(grid_list), 2),
            "best_day_date": best_day["date"] if best_day else "",
            "best_day_pv_kwh": best_day["pv_kwh"] if best_day else 0.0,
            "worst_day_date": worst_day["date"] if worst_day else "",
            "worst_day_pv_kwh": worst_day["pv_kwh"] if worst_day else 0.0
        })

    return months

def calculate_averages_comparison(
    records: List[CanonicalRecord],
    daily_summaries: List[Dict[str, Any]]
) -> Dict[str, Any]:
    if not records or not daily_summaries:
        return {
            "time_weighted_avg_power_kw": 0.0,
            "arithmetic_mean_power_kw": 0.0,
            "mean_daily_pv_energy_kwh": 0.0,
            "median_daily_pv_energy_kwh": 0.0,
            "mean_daily_load_energy_kwh": 0.0,
            "median_daily_load_energy_kwh": 0.0
        }

    timestamps = [r.timestamp for r in records]
    pv_series = [r.pv_power_kw for r in records]
    load_series = [r.load_power_kw for r in records]

    pv_total_kwh, _, total_dur_hours = integrate_power_series(timestamps, pv_series)
    load_total_kwh, _, _ = integrate_power_series(timestamps, load_series)

    tw_pv_power = round(pv_total_kwh / total_dur_hours, 3) if total_dur_hours > 0 else 0.0
    tw_load_power = round(load_total_kwh / total_dur_hours, 3) if total_dur_hours > 0 else 0.0

    arith_pv = round(float(np.mean(pv_series)), 3)
    arith_load = round(float(np.mean(load_series)), 3)

    daily_pv = [d["pv_kwh"] for d in daily_summaries if d["status"] != "INVALID"]
    daily_load = [d["load_kwh"] for d in daily_summaries if d["status"] != "INVALID"]

    return {
        "time_weighted_avg_pv_power_kw": tw_pv_power,
        "arithmetic_mean_pv_power_kw": arith_pv,
        "time_weighted_avg_load_power_kw": tw_load_power,
        "arithmetic_mean_load_power_kw": arith_load,
        "mean_daily_pv_energy_kwh": round(float(np.mean(daily_pv)), 2) if daily_pv else 0.0,
        "median_daily_pv_energy_kwh": round(float(np.median(daily_pv)), 2) if daily_pv else 0.0,
        "mean_daily_load_energy_kwh": round(float(np.mean(daily_load)), 2) if daily_load else 0.0,
        "median_daily_load_energy_kwh": round(float(np.median(daily_load)), 2) if daily_load else 0.0
    }

