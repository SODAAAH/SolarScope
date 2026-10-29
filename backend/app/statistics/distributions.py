import numpy as np
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord

def calculate_channel_statistics(values: List[float]) -> Dict[str, float]:
    if not values:
        return {
            "mean": 0.0, "median": 0.0, "std": 0.0,
            "min": 0.0, "max": 0.0,
            "p10": 0.0, "p25": 0.0, "p75": 0.0, "p90": 0.0
        }
    arr = np.array(values, dtype=float)
    return {
        "mean": round(float(np.mean(arr)), 3),
        "median": round(float(np.median(arr)), 3),
        "std": round(float(np.std(arr)), 3),
        "min": round(float(np.min(arr)), 3),
        "max": round(float(np.max(arr)), 3),
        "p10": round(float(np.percentile(arr, 10)), 3),
        "p25": round(float(np.percentile(arr, 25)), 3),
        "p75": round(float(np.percentile(arr, 75)), 3),
        "p90": round(float(np.percentile(arr, 90)), 3)
    }

def calculate_histogram(values: List[float], bins: int = 15) -> List[Dict[str, Any]]:
    if not values:
        return []
    arr = np.array(values, dtype=float)
    counts, edges = np.histogram(arr, bins=bins)
    result = []
    for i in range(len(counts)):
        result.append({
            "bin_start": round(float(edges[i]), 2),
            "bin_end": round(float(edges[i + 1]), 2),
            "count": int(counts[i]),
            "percentage": round(float(counts[i] / len(arr) * 100.0), 2)
        })
    return result

def calculate_duration_curve(values: List[float], sample_points: int = 100) -> List[Dict[str, float]]:
    if not values:
        return []
    sorted_vals = sorted(values, reverse=True)
    n = len(sorted_vals)
    curve = []
    for step in range(sample_points + 1):
        percentile = step
        idx = min(n - 1, int(step / sample_points * (n - 1)))
        curve.append({
            "time_percentage": percentile,
            "power_kw": round(sorted_vals[idx], 3)
        })
    return curve

def get_complete_statistical_profile(records: List[CanonicalRecord]) -> Dict[str, Any]:
    if not records:
        return {}

    pv_vals = [r.pv_power_kw for r in records]
    load_vals = [r.load_power_kw for r in records]
    grid_vals = [r.grid_power_kw for r in records]
    batt_vals = [r.battery_power_kw for r in records]
    soc_vals = [r.soc_percent for r in records]

    return {
        "pv": {
            "stats": calculate_channel_statistics(pv_vals),
            "histogram": calculate_histogram(pv_vals),
            "duration_curve": calculate_duration_curve(pv_vals)
        },
        "load": {
            "stats": calculate_channel_statistics(load_vals),
            "histogram": calculate_histogram(load_vals),
            "duration_curve": calculate_duration_curve(load_vals)
        },
        "grid": {
            "stats": calculate_channel_statistics(grid_vals),
            "histogram": calculate_histogram(grid_vals),
            "duration_curve": calculate_duration_curve(grid_vals)
        },
        "battery": {
            "stats": calculate_channel_statistics(batt_vals),
            "histogram": calculate_histogram(batt_vals),
            "duration_curve": calculate_duration_curve(batt_vals)
        },
        "soc": {
            "stats": calculate_channel_statistics(soc_vals),
            "histogram": calculate_histogram(soc_vals),
            "duration_curve": calculate_duration_curve(soc_vals)
        }
    }
