import re
import unicodedata
from typing import List, Dict, Any, Tuple
from backend.app.ingestion.models import ColumnMappingItem

def clean_column_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(name)).lower()
    cleaned = re.sub(r"[^\w\s%]", " ", normalized)
    return " ".join(cleaned.split())

def match_column_meaning(header: str) -> Tuple[str | None, str | None, float]:
    cleaned = clean_column_name(header)
    
    if any(k in cleaned for k in ["time", "date", "timestamp", "datetime", "waktu", "jam"]):
        return "timestamp", None, 0.95
        
    if any(k in cleaned for k in ["soc", "state of charge", "battery percentage", "baterai %"]):
        return "soc_percent", "%", 0.95
        
    if any(k in cleaned for k in ["pv", "photovoltaic", "solar", "panel"]):
        return "pv_power_kw", "kW", 0.90
        
    if any(k in cleaned for k in ["production", "gen power", "solar power"]):
        return "production_power_kw", "kW", 0.85
        
    if any(k in cleaned for k in ["consumption", "load", "demand", "beban", "household"]):
        return "load_power_kw", "kW", 0.90
        
    if any(k in cleaned for k in ["battery", "batt", "baterai", "storage"]) and not any(k in cleaned for k in ["soc", "%"]):
        return "battery_power_kw", "kW", 0.90
        
    if any(k in cleaned for k in ["grid tied", "grid-tied", "inverter power", "on grid"]):
        return "grid_tied_inverter_power_kw", "kW", 0.85
        
    if any(k in cleaned for k in ["grid", "utility", "pln", "network"]):
        return "grid_power_kw", "kW", 0.90
        
    if any(k in cleaned for k in ["generator", "genset", "diesel"]):
        return "generator_power_kw", "kW", 0.90
        
    return None, None, 0.0

def build_column_mapping_preview(
    headers: List[str],
    sample_records: List[Dict[str, Any]]
) -> List[ColumnMappingItem]:
    items: List[ColumnMappingItem] = []
    
    col_values: Dict[str, List[float]] = {}
    for h in headers:
        vals: List[float] = []
        for r in sample_records:
            v = r.get(h)
            if v is not None and v != "":
                try:
                    vals.append(float(v))
                except (ValueError, TypeError):
                    pass
        col_values[h] = vals

    for h in headers:
        canonical_name, unit, conf = match_column_meaning(h)
        samples = [r.get(h) for r in sample_records[:5] if r.get(h) is not None]
        
        data_type = "numeric"
        if canonical_name == "timestamp" or (samples and isinstance(samples[0], str) and ("-" in samples[0] or ":" in samples[0])):
            data_type = "datetime"
            
        sign_conv = "positive"
        if canonical_name == "battery_power_kw":
            sign_conv = "positive_discharge"
        elif canonical_name == "grid_power_kw":
            sign_conv = "positive_import"
            
        is_inactive = False
        vals = col_values.get(h, [])
        if vals and all(v == 0.0 for v in vals):
            is_inactive = True
            
        item = ColumnMappingItem(
            original_name=h,
            canonical_name=canonical_name,
            unit=unit,
            data_type=data_type,
            confidence=conf,
            sample_values=samples,
            sign_convention=sign_conv,
            is_duplicate=False,
            duplicate_of=None,
            is_inactive=is_inactive
        )
        items.append(item)
        
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            h1 = items[i].original_name
            h2 = items[j].original_name
            v1 = col_values.get(h1, [])
            v2 = col_values.get(h2, [])
            if v1 and v2 and len(v1) == len(v2) and v1 == v2 and not all(x == 0.0 for x in v1):
                if items[i].canonical_name == "pv_power_kw" and items[j].canonical_name == "production_power_kw":
                    items[j].is_duplicate = True
                    items[j].duplicate_of = items[i].original_name
                elif items[j].canonical_name == "pv_power_kw" and items[i].canonical_name == "production_power_kw":
                    items[i].is_duplicate = True
                    items[i].duplicate_of = items[j].original_name
                    
    return items
