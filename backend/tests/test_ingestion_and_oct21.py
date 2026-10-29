import pytest
from pathlib import Path
from backend.app.config import settings
from backend.app.ingestion.excel_reader import list_excel_sheets, read_excel_sheet
from backend.app.ingestion.column_mapper import build_column_mapping_preview
from backend.app.ingestion.normalizer import normalize_dataset
from backend.app.metrics.solar_metrics import calculate_solar_metrics
from backend.app.metrics.consumption_metrics import calculate_consumption_metrics

def test_oct21_file_exists():
    sample_path = settings.sample_dir / "Oct 21.xlsx"
    if not sample_path.exists():
        pytest.skip("Oct 21.xlsx not in sample dir")
    sheets = list_excel_sheets(sample_path)
    assert "2026-10-21" in sheets

def test_oct21_ground_truth_metrics():
    sample_path = settings.sample_dir / "Oct 21.xlsx"
    if not sample_path.exists():
        pytest.skip("Oct 21.xlsx not in sample dir")
    headers, records, total_count = read_excel_sheet(sample_path, sheet_name="2026-10-21")
    assert total_count == 257
    mapping_items = build_column_mapping_preview(headers, records)
    mappings = {item.original_name: item.canonical_name for item in mapping_items if item.canonical_name}
    sign_conventions = {item.canonical_name: item.sign_convention for item in mapping_items if item.canonical_name}
    canonical = normalize_dataset(records, mappings, sign_conventions)
    
    solar = calculate_solar_metrics(canonical, pv_capacity_kwp=5.0)
    assert 21.6 <= solar["total_generation_kwh"] <= 21.8
    assert solar["peak_power_kw"] == 4.17

    consumption = calculate_consumption_metrics(canonical)
    assert 33.4 <= consumption["total_demand_kwh"] <= 33.6
    assert consumption["peak_load_kw"] == 3.27
