import numpy as np
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.time_utils import format_datetime_12h

def detect_system_anomalies(records: List[CanonicalRecord]) -> List[Dict[str, Any]]:
    if len(records) < 5:
        return []

    anomalies: List[Dict[str, Any]] = []

    loads = np.array([r.load_power_kw for r in records], dtype=float)
    mean_load = np.mean(loads)
    std_load = np.std(loads) if np.std(loads) > 0 else 1.0

    for i in range(1, len(records)):
        r = records[i]
        prev = records[i - 1]

        z_load = (r.load_power_kw - mean_load) / std_load
        step_load = r.load_power_kw - prev.load_power_kw
        if z_load > 3.5 and step_load > 2.0:
            anomalies.append({
                "timestamp": r.timestamp,
                "timestamp_12h": format_datetime_12h(r.timestamp),
                "type": "SUDDEN_LOAD_SPIKE",
                "channel": "load_power_kw",
                "severity": "HIGH",
                "value": round(r.load_power_kw, 3),
                "baseline": round(mean_load, 3),
                "confidence": 0.90,
                "description": f"Household load spiked abruptly by {round(step_load, 2)} kW to {round(r.load_power_kw, 2)} kW (z-score: {round(z_load, 2)})."
            })

        if r.grid_power_kw >= 0.5 and r.soc_percent > 30.0 and r.battery_power_kw <= 0.05:
            anomalies.append({
                "timestamp": r.timestamp,
                "timestamp_12h": format_datetime_12h(r.timestamp),
                "type": "UNEXPECTED_GRID_IMPORT_WITH_CHARGE",
                "channel": "grid_power_kw",
                "severity": "HIGH",
                "value": round(r.grid_power_kw, 3),
                "baseline": round(r.soc_percent, 1),
                "confidence": 0.85,
                "description": f"Grid imported {round(r.grid_power_kw, 2)} kW while battery retained {round(r.soc_percent, 1)}% SOC without discharging. Indicates inverter charge-rate limit or bypass mode."
            })

        step_pv = prev.pv_power_kw - r.pv_power_kw
        if prev.pv_power_kw > 2.5 and step_pv > 2.0 and r.timestamp[11:13] in ["11", "12", "13", "14"]:
            anomalies.append({
                "timestamp": r.timestamp,
                "timestamp_12h": format_datetime_12h(r.timestamp),
                "type": "RAPID_SOLAR_CURTAILMENT_OR_SHADING",
                "channel": "pv_power_kw",
                "severity": "MEDIUM",
                "value": round(r.pv_power_kw, 3),
                "baseline": round(prev.pv_power_kw, 3),
                "confidence": 0.80,
                "description": f"Midday solar generation plummeted abruptly by {round(step_pv, 2)} kW in a single interval, consistent with severe cloud passing or inverter curtailment."
            })

    consecutive_flat = 0
    flat_val = None
    flat_start = None
    for r in records:
        if r.load_power_kw > 0.1 and r.load_power_kw == flat_val:
            consecutive_flat += 1
            if consecutive_flat == 8:
                anomalies.append({
                    "timestamp": flat_start,
                    "timestamp_12h": format_datetime_12h(flat_start),
                    "type": "FLATLINED_LOAD_MEASUREMENT",
                    "channel": "load_power_kw",
                    "severity": "LOW",
                    "value": round(flat_val, 3),
                    "baseline": 0.0,
                    "confidence": 0.75,
                    "description": f"Household load held an exact constant value of {round(flat_val, 3)} kW across 8 consecutive intervals."
                })
        else:
            flat_val = r.load_power_kw
            consecutive_flat = 1
            flat_start = r.timestamp

    return anomalies
