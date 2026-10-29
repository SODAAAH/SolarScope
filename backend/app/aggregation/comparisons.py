from typing import List, Dict, Any, Optional
import datetime
import numpy as np

from backend.app.ingestion.models import CanonicalRecord
from backend.app.aggregation.historical import calculate_daily_summaries
from backend.app.metrics.time_utils import hour_index_to_12h

def compare_periods(
    records_a: List[CanonicalRecord],
    records_b: List[CanonicalRecord],
    label_a: str = "Period A",
    label_b: str = "Period B"
) -> Dict[str, Any]:
    days_a = calculate_daily_summaries(records_a)
    days_b = calculate_daily_summaries(records_b)

    def summarize_days(days: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
        valid_days = [d for d in days if d["status"] != "INVALID"]
        pv_tot = sum(d["pv_kwh"] for d in valid_days)
        load_tot = sum(d["load_kwh"] for d in valid_days)
        grid_tot = sum(d["grid_import_kwh"] for d in valid_days)
        n = len(valid_days)

        return {
            "label": label,
            "days_count": n,
            "total_pv_kwh": round(pv_tot, 2),
            "mean_daily_pv_kwh": round(pv_tot / n, 2) if n > 0 else 0.0,
            "total_load_kwh": round(load_tot, 2),
            "mean_daily_load_kwh": round(load_tot / n, 2) if n > 0 else 0.0,
            "total_grid_import_kwh": round(grid_tot, 2),
            "mean_daily_grid_kwh": round(grid_tot / n, 2) if n > 0 else 0.0,
            "avg_self_sufficiency": round(float(np.mean([d["self_sufficiency_ratio"] for d in valid_days])), 3) if valid_days else 0.0,
            "avg_grid_dependence": round(float(np.mean([d["grid_dependence_ratio"] for d in valid_days])), 3) if valid_days else 0.0
        }

    sum_a = summarize_days(days_a, label_a)
    sum_b = summarize_days(days_b, label_b)

    delta_pv_mean = round(sum_b["mean_daily_pv_kwh"] - sum_a["mean_daily_pv_kwh"], 2)
    delta_pv_pct = round((delta_pv_mean / sum_a["mean_daily_pv_kwh"]) * 100.0, 1) if sum_a["mean_daily_pv_kwh"] > 0 else 0.0

    delta_load_mean = round(sum_b["mean_daily_load_kwh"] - sum_a["mean_daily_load_kwh"], 2)
    delta_load_pct = round((delta_load_mean / sum_a["mean_daily_load_kwh"]) * 100.0, 1) if sum_a["mean_daily_load_kwh"] > 0 else 0.0

    delta_grid_mean = round(sum_b["mean_daily_grid_kwh"] - sum_a["mean_daily_grid_kwh"], 2)
    delta_grid_pct = round((delta_grid_mean / sum_a["mean_daily_grid_kwh"]) * 100.0, 1) if sum_a["mean_daily_grid_kwh"] > 0 else 0.0

    return {
        "period_a": sum_a,
        "period_b": sum_b,
        "delta": {
            "mean_daily_pv_kwh": delta_pv_mean,
            "pv_pct_change": delta_pv_pct,
            "mean_daily_load_kwh": delta_load_mean,
            "load_pct_change": delta_load_pct,
            "mean_daily_grid_kwh": delta_grid_mean,
            "grid_pct_change": delta_grid_pct,
            "self_sufficiency_change": round(sum_b["avg_self_sufficiency"] - sum_a["avg_self_sufficiency"], 3),
            "grid_dependence_change": round(sum_b["avg_grid_dependence"] - sum_a["avg_grid_dependence"], 3)
        }
    }

def compare_weekdays_vs_weekends(records: List[CanonicalRecord]) -> Dict[str, Any]:
    weekdays: List[CanonicalRecord] = []
    weekends: List[CanonicalRecord] = []

    for r in records:
        try:
            dt = datetime.date.fromisoformat(r.timestamp[:10])
            if dt.weekday() < 5:
                weekdays.append(r)
            else:
                weekends.append(r)
        except ValueError:
            continue

    def get_hourly_load(recs: List[CanonicalRecord]) -> List[float]:
        hour_loads = [[] for _ in range(24)]
        for r in recs:
            try:
                h = int(r.timestamp[11:13])
                hour_loads[h].append(r.load_power_kw)
            except (ValueError, IndexError):
                continue
        return [round(float(np.mean(vals)), 3) if vals else 0.0 for vals in hour_loads]

    return {
        "hours_12h": [hour_index_to_12h(h) for h in range(24)],
        "weekday_hourly_load_kw": get_hourly_load(weekdays),
        "weekend_hourly_load_kw": get_hourly_load(weekends),
        "weekday_sample_count": len(weekdays),
        "weekend_sample_count": len(weekends)
    }

