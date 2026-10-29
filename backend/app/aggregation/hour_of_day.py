from collections import defaultdict
from typing import List, Dict, Any
import numpy as np

from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.time_utils import hour_index_to_12h

def calculate_hour_of_day_profiles(records: List[CanonicalRecord]) -> List[Dict[str, Any]]:
    if not records:
        return []

    hour_recs: Dict[int, List[CanonicalRecord]] = defaultdict(list)
    for r in records:
        try:
            h = int(r.timestamp[11:13])
            hour_recs[h].append(r)
        except (ValueError, IndexError):
            continue

    profiles: List[Dict[str, Any]] = []

    for h in range(24):
        recs = hour_recs.get(h, [])
        pv = [r.pv_power_kw for r in recs]
        load = [r.load_power_kw for r in recs]
        grid = [max(0.0, r.grid_power_kw) for r in recs]
        batt = [r.battery_power_kw for r in recs]
        soc = [r.soc_percent for r in recs]

        profiles.append({
            "hour": h,
            "hour_label_12h": hour_index_to_12h(h),
            "sample_count": len(recs),
            "pv_mean_kw": round(float(np.mean(pv)), 3) if pv else 0.0,
            "pv_median_kw": round(float(np.median(pv)), 3) if pv else 0.0,
            "pv_p10_kw": round(float(np.percentile(pv, 10)), 3) if pv else 0.0,
            "pv_p90_kw": round(float(np.percentile(pv, 90)), 3) if pv else 0.0,
            "load_mean_kw": round(float(np.mean(load)), 3) if load else 0.0,
            "load_median_kw": round(float(np.median(load)), 3) if load else 0.0,
            "grid_mean_kw": round(float(np.mean(grid)), 3) if grid else 0.0,
            "grid_median_kw": round(float(np.median(grid)), 3) if grid else 0.0,
            "batt_mean_kw": round(float(np.mean(batt)), 3) if batt else 0.0,
            "soc_mean_percent": round(float(np.mean(soc)), 1) if soc else 0.0,
            "soc_median_percent": round(float(np.median(soc)), 1) if soc else 0.0
        })

    return profiles

def calculate_hour_date_heatmap(
    records: List[CanonicalRecord],
    metric: str = "pv_power_kw"
) -> Dict[str, Any]:
    if not records:
        return {"dates": [], "hours": [], "matrix": []}

    dates = sorted(list(set(r.timestamp[:10] for r in records)))
    hours = [hour_index_to_12h(h) for h in range(24)]

    day_hour_map: Dict[str, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        d = r.timestamp[:10]
        try:
            h = int(r.timestamp[11:13])
            val = getattr(r, metric, 0.0)
            if metric == "grid_import":
                val = max(0.0, r.grid_power_kw)
            day_hour_map[d][h].append(val)
        except (ValueError, IndexError):
            continue

    matrix: List[List[Any]] = []
    for d_idx, d in enumerate(dates):
        for h in range(24):
            vals = day_hour_map[d].get(h, [])
            avg_val = round(float(np.mean(vals)), 2) if vals else 0.0
            matrix.append([h, d_idx, avg_val])

    return {
        "dates": dates,
        "hours": hours,
        "matrix": matrix
    }

