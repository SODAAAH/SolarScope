import math
from typing import List, Dict, Any, Optional, Tuple
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.time_utils import parse_timestamp

def parse_iso_timestamp(val: Any, target_tz: str = "Asia/Manila") -> Optional[str]:
    dt = parse_timestamp(val, target_tz=target_tz)
    if dt is not None:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return None

def parse_measurement(val: Any) -> Tuple[Optional[float], str]:
    if val is None:
        return None, "missing"
    if isinstance(val, bool):
        return None, "invalid"
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned or cleaned.lower() in ("none", "null", "na", "n/a", "--", "-", "nan"):
            return None, "missing"
        try:
            num = float(cleaned)
        except (ValueError, TypeError):
            return None, "invalid"
    else:
        try:
            num = float(val)
        except (ValueError, TypeError):
            return None, "invalid"
    if math.isnan(num):
        return None, "missing"
    if math.isinf(num):
        return None, "invalid"
    return num, "measured"

def safe_float(val: Any, default: float = 0.0) -> float:
    num, status = parse_measurement(val)
    if status == "measured" and num is not None:
        return num
    return default

def normalize_dataset(
    records: List[Dict[str, Any]],
    mapping: Dict[str, str],
    sign_conventions: Dict[str, str],
    timezone: str = "Asia/Manila"
) -> List[CanonicalRecord]:
    canonical_records: List[CanonicalRecord] = []

    rev_map: Dict[str, str] = {canon: orig for orig, canon in mapping.items()}

    time_col = rev_map.get("timestamp")
    pv_col = rev_map.get("pv_power_kw") or rev_map.get("production_power_kw")
    load_col = rev_map.get("load_power_kw")
    grid_col = rev_map.get("grid_power_kw")
    batt_col = rev_map.get("battery_power_kw")
    soc_col = rev_map.get("soc_percent")
    gen_col = rev_map.get("generator_power_kw")
    grid_tied_col = rev_map.get("grid_tied_inverter_power_kw")

    batt_sign = sign_conventions.get("battery_power_kw", "positive_discharge")
    grid_sign = sign_conventions.get("grid_power_kw", "positive_import")

    for idx, r in enumerate(records):
        raw_time = r.get(time_col) if time_col else None
        parsed_ts = parse_iso_timestamp(raw_time, target_tz=timezone)
        ts_valid = parsed_ts is not None
        ts = parsed_ts if parsed_ts is not None else f"INVALID_TS_ROW_{idx}"

        missing_channels: List[str] = []
        invalid_channels: List[str] = []
        flags: List[str] = []
        if not ts_valid:
            flags.append("INVALID_TIMESTAMP")

        def read_chan(col_name: Optional[str], chan_key: str, required_for_audit: bool = False) -> float:
            if not col_name:
                if required_for_audit:
                    missing_channels.append(chan_key)
                return 0.0
            num, status = parse_measurement(r.get(col_name))
            if status == "missing":
                missing_channels.append(chan_key)
                return 0.0
            if status == "invalid":
                invalid_channels.append(chan_key)
                return 0.0
            return num if num is not None else 0.0

        raw_pv = read_chan(pv_col, "pv_power_kw", required_for_audit=True)
        if raw_pv < 0.0:
            flags.append("NEGATIVE_PV_RAW")
        pv = max(0.0, raw_pv)

        raw_load = read_chan(load_col, "load_power_kw", required_for_audit=True)
        if raw_load < 0.0:
            flags.append("NEGATIVE_LOAD_RAW")
        load = max(0.0, raw_load)

        raw_grid = read_chan(grid_col, "grid_power_kw", required_for_audit=True)
        grid = -raw_grid if grid_sign == "negative_import" else raw_grid

        raw_batt = read_chan(batt_col, "battery_power_kw", required_for_audit=True)
        batt = -raw_batt if batt_sign == "positive_charge" else raw_batt

        raw_soc = read_chan(soc_col, "soc_percent", required_for_audit=False)
        if soc_col and "soc_percent" not in missing_channels and "soc_percent" not in invalid_channels:
            if raw_soc < 0.0 or raw_soc > 100.0:
                flags.append("SOC_OUT_OF_RANGE")
        soc = max(0.0, min(100.0, raw_soc))

        gen = max(0.0, read_chan(gen_col, "generator_power_kw", required_for_audit=False))
        grid_tied = max(0.0, read_chan(grid_tied_col, "grid_tied_inverter_power_kw", required_for_audit=False))

        if pv > 10.0:
            flags.append("HIGH_PV_SPIKE")
        if load > 15.0:
            flags.append("HIGH_LOAD_SPIKE")
        if soc_col and "soc_percent" not in missing_channels and soc <= 25.0:
            flags.append("AT_OR_BELOW_RESERVE")

        batt_disch = max(0.0, batt)
        batt_chg = max(0.0, -batt)
        grid_imp = max(0.0, grid)
        grid_exp = max(0.0, -grid)

        sources = pv + grid_imp + batt_disch + gen
        sinks = load + batt_chg + grid_exp
        residual = sources - sinks

        canonical_records.append(
            CanonicalRecord(
                timestamp=ts,
                pv_power_kw=round(pv, 4),
                load_power_kw=round(load, 4),
                grid_power_kw=round(grid, 4),
                battery_power_kw=round(batt, 4),
                soc_percent=round(soc, 2),
                generator_power_kw=round(gen, 4),
                grid_tied_inverter_power_kw=round(grid_tied, 4),
                residual_power_kw=round(residual, 4),
                quality_flags=flags,
                missing_channels=missing_channels,
                invalid_channels=invalid_channels,
                timestamp_valid=ts_valid
            )
        )

    return canonical_records
