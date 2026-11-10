import io
import csv
import pytest
from backend.app.ingestion.csv_reader import read_csv_file
from backend.app.ingestion.column_mapper import build_column_mapping_preview
from backend.app.ingestion.normalizer import normalize_dataset
from backend.app.metrics.solar_metrics import calculate_solar_metrics
from backend.app.metrics.consumption_metrics import calculate_consumption_metrics

def _build_synthetic_csv(path):
    rows = [
        ["Timestamp", "Solar Power (kW)", "Load Power (kW)", "Battery Power (kW)", "Grid Power (kW)", "SOC (%)"],
    ]
    for h in range(24):
        for m in (0, 30):
            ts = f"2025-01-15 {h:02d}:{m:02d}:00"
            hour_f = h + m / 60.0
            pv = round(max(0.0, 4.2 * (1.0 - ((hour_f - 12.0) / 5.5) ** 2)), 3) if 6.5 <= hour_f <= 17.5 else 0.0
            load = 1.4
            batt = round(-(pv - load), 3) if pv > load else round(load - pv, 3)
            grid = 0.0
            soc = min(98.0, max(25.0, round(40.0 + pv * 10.0, 1)))
            rows.append([ts, pv, load, batt, grid, soc])
    rows.append(["2025-01-16 00:00:00", 0.0, 1.4, 1.4, 0.0, 40.0])
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

def test_synthetic_csv_ingestion_and_metrics(tmp_path):
    csv_path = tmp_path / "synthetic_station.csv"
    _build_synthetic_csv(csv_path)

    headers, records, total_count = read_csv_file(csv_path)
    assert total_count == 49
    assert len(headers) == 6

    mapping_items = build_column_mapping_preview(headers, records)
    mappings = {item.original_name: item.canonical_name for item in mapping_items if item.canonical_name}
    sign_conventions = {item.canonical_name: item.sign_convention for item in mapping_items if item.canonical_name}
    canonical = normalize_dataset(records, mappings, sign_conventions)
    assert len(canonical) == 49

    solar = calculate_solar_metrics(canonical, pv_capacity_kwp=5.0, inverter_rating_kw=6.0)
    assert solar["total_generation_kwh"] > 0
    assert solar["peak_power_kw"] > 3.5

    consumption = calculate_consumption_metrics(canonical)
    assert 33.0 <= consumption["total_demand_kwh"] <= 34.5
    assert consumption["peak_load_kw"] == 1.4
