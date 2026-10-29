import numpy as np
from scipy import stats
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord

def calculate_correlation_matrices(records: List[CanonicalRecord]) -> Dict[str, Any]:
    if len(records) < 3:
        return {"pearson": {}, "spearman": {}, "channels": []}

    channels = ["PV Power", "Household Load", "Grid Power", "Battery Power", "Battery SOC"]
    
    data = np.array([
        [r.pv_power_kw for r in records],
        [r.load_power_kw for r in records],
        [r.grid_power_kw for r in records],
        [r.battery_power_kw for r in records],
        [r.soc_percent for r in records]
    ], dtype=float)

    n = len(channels)
    pearson_matrix: List[List[float]] = []
    spearman_matrix: List[List[float]] = []

    for i in range(n):
        row_p = []
        row_s = []
        for j in range(n):
            if i == j:
                row_p.append(1.0)
                row_s.append(1.0)
            else:
                std_i = np.std(data[i])
                std_j = np.std(data[j])
                if std_i == 0 or std_j == 0:
                    row_p.append(0.0)
                    row_s.append(0.0)
                else:
                    p_corr, _ = stats.pearsonr(data[i], data[j])
                    s_corr, _ = stats.spearmanr(data[i], data[j])
                    row_p.append(round(float(p_corr), 3))
                    row_s.append(round(float(s_corr), 3))
        pearson_matrix.append(row_p)
        spearman_matrix.append(row_s)

    scatter_soc_load = [
        {"x": round(r.soc_percent, 1), "y": round(r.load_power_kw, 3), "time": r.timestamp}
        for r in records
    ]
    scatter_pv_load = [
        {"x": round(r.pv_power_kw, 3), "y": round(r.load_power_kw, 3), "time": r.timestamp}
        for r in records
    ]

    return {
        "channels": channels,
        "pearson_matrix": pearson_matrix,
        "spearman_matrix": spearman_matrix,
        "scatter_soc_load": scatter_soc_load,
        "scatter_pv_load": scatter_pv_load
    }
