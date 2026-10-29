import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord

def parse_iso_timestamp(val: Any) -> str:
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    s = str(val).strip()
    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ]:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return s

def safe_float(val: Any, default: float = 0.0) -> float:
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def normalize_dataset(
    records: List[Dict[str, Any]],
    mapping: Dict[str, str],
    sign_conventions: Dict[str, str]
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
        raw_time = r.get(time_col) if time_col else f"row_{idx}"
        ts = parse_iso_timestamp(raw_time)

        pv = max(0.0, safe_float(r.get(pv_col) if pv_col else 0.0))
        load = max(0.0, safe_float(r.get(load_col) if load_col else 0.0))
        
        raw_grid = safe_float(r.get(grid_col) if grid_col else 0.0)
        if grid_sign == "negative_import":
            grid = -raw_grid
        else:
            grid = raw_grid

        raw_batt = safe_float(r.get(batt_col) if batt_col else 0.0)
        if batt_sign == "positive_charge":
            batt = -raw_batt
        else:
            batt = raw_batt

        soc = max(0.0, min(100.0, safe_float(r.get(soc_col) if soc_col else 0.0)))
        gen = max(0.0, safe_float(r.get(gen_col) if gen_col else 0.0))
        grid_tied = max(0.0, safe_float(r.get(grid_tied_col) if grid_tied_col else 0.0))

        flags: List[str] = []
        if pv > 10.0:
            flags.append("HIGH_PV_SPIKE")
        if load > 15.0:
            flags.append("HIGH_LOAD_SPIKE")
        if soc <= 25.0:
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
                quality_flags=flags
            )
        )

    return canonical_records
