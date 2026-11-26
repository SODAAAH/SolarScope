from collections import Counter
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.time_utils import parse_timestamp

def validate_channel_ranges(records: List[CanonicalRecord]) -> Dict[str, Any]:
    if not records:
        return {
            "invalid_soc_count": 0,
            "negative_load_count": 0,
            "negative_pv_count": 0,
            "nighttime_pv_zeros": 0,
            "daytime_pv_zeros": 0,
            "constant_channels": [],
            "missing_channel_counts": {},
            "invalid_channel_counts": {},
            "energy_imbalance_intervals": 0,
            "max_load_kw": 0.0,
            "max_pv_kw": 0.0,
            "max_grid_kw": 0.0
        }

    invalid_soc = 0
    neg_load = 0
    neg_pv = 0
    night_pv_zero = 0
    day_pv_zero = 0
    energy_imbalance = 0

    missing_counter: Counter = Counter()
    invalid_counter: Counter = Counter()

    pv_vals = [r.pv_power_kw for r in records]
    load_vals = [r.load_power_kw for r in records]
    grid_vals = [r.grid_power_kw for r in records]
    soc_vals = [r.soc_percent for r in records]
    gen_vals = [r.generator_power_kw for r in records]
    grid_tied_vals = [r.grid_tied_inverter_power_kw for r in records]

    for r in records:
        if r.soc_percent < 0.0 or r.soc_percent > 100.0 or "SOC_OUT_OF_RANGE" in r.quality_flags:
            invalid_soc += 1
        if r.load_power_kw < 0.0 or "NEGATIVE_LOAD_RAW" in r.quality_flags:
            neg_load += 1
        if r.pv_power_kw < 0.0 or "NEGATIVE_PV_RAW" in r.quality_flags:
            neg_pv += 1
        if abs(r.residual_power_kw) > 1.5:
            energy_imbalance += 1

        for ch in r.missing_channels:
            missing_counter[ch] += 1
        for ch in r.invalid_channels:
            invalid_counter[ch] += 1

        dt = parse_timestamp(r.timestamp)
        hour = dt.hour if dt is not None else 12

        if r.pv_power_kw == 0.0 and "pv_power_kw" not in r.missing_channels and "pv_power_kw" not in r.invalid_channels:
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
        "missing_channel_counts": dict(missing_counter),
        "invalid_channel_counts": dict(invalid_counter),
        "energy_imbalance_intervals": energy_imbalance,
        "max_load_kw": round(max(load_vals) if load_vals else 0.0, 3),
        "max_pv_kw": round(max(pv_vals) if pv_vals else 0.0, 3),
        "max_grid_kw": round(max(grid_vals) if grid_vals else 0.0, 3),
        "min_soc_percent": round(min(soc_vals) if soc_vals else 0.0, 1),
        "max_soc_percent": round(max(soc_vals) if soc_vals else 0.0, 1)
    }
