import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord

def validate_channel_ranges(records: List[CanonicalRecord]) -> Dict[str, Any]:
    if not records:
        return {
            "invalid_soc_count": 0,
            "negative_load_count": 0,
            "negative_pv_count": 0,
            "nighttime_pv_zeros": 0,
            "daytime_pv_zeros": 0,
            "constant_channels": [],
            "max_load_kw": 0.0,
            "max_pv_kw": 0.0,
            "max_grid_kw": 0.0
        }

    invalid_soc = 0
    neg_load = 0
    neg_pv = 0
    night_pv_zero = 0
    day_pv_zero = 0

    pv_vals = [r.pv_power_kw for r in records]
    load_vals = [r.load_power_kw for r in records]
    grid_vals = [r.grid_power_kw for r in records]
    batt_vals = [r.battery_power_kw for r in records]
    soc_vals = [r.soc_percent for r in records]
    gen_vals = [r.generator_power_kw for r in records]
    grid_tied_vals = [r.grid_tied_inverter_power_kw for r in records]

    for r in records:
        if r.soc_percent < 0.0 or r.soc_percent > 100.0:
            invalid_soc += 1
        if r.load_power_kw < 0.0:
            neg_load += 1
        if r.pv_power_kw < 0.0:
            neg_pv += 1
            
        try:
            hour = datetime.datetime.strptime(r.timestamp, "%Y-%m-%d %H:%M:%S").hour
        except Exception:
            hour = 12

        if r.pv_power_kw == 0.0:
            if hour < 6 or hour >= 18:
                night_pv_zero += 1
            else:
                day_pv_zero += 1

    constant_channels = []
    if len(gen_vals) > 0 and all(v == 0.0 for v in gen_vals):
        constant_channels.append({
            "channel": "generator_power_kw",
            "type": "INACTIVE_EQUIPMENT",
            "value": 0.0
        })
    if len(grid_tied_vals) > 0 and all(v == 0.0 for v in grid_tied_vals):
        constant_channels.append({
            "channel": "grid_tied_inverter_power_kw",
            "type": "INACTIVE_EQUIPMENT",
            "value": 0.0
        })

    return {
        "invalid_soc_count": invalid_soc,
        "negative_load_count": neg_load,
        "negative_pv_count": neg_pv,
        "nighttime_pv_zeros": night_pv_zero,
        "daytime_pv_zeros": day_pv_zero,
        "constant_channels": constant_channels,
        "max_load_kw": round(max(load_vals) if load_vals else 0.0, 3),
        "max_pv_kw": round(max(pv_vals) if pv_vals else 0.0, 3),
        "max_grid_kw": round(max(grid_vals) if grid_vals else 0.0, 3),
        "min_soc_percent": round(min(soc_vals) if soc_vals else 0.0, 1),
        "max_soc_percent": round(max(soc_vals) if soc_vals else 0.0, 1)
    }
