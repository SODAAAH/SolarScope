import os
import uuid
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.storage.db import get_connection
from backend.app.storage.file_store import save_uploaded_file, get_file_path
from backend.app.ingestion.excel_reader import list_excel_sheets, read_excel_sheet
from backend.app.ingestion.csv_reader import read_csv_file
from backend.app.ingestion.column_mapper import build_column_mapping_preview
from backend.app.ingestion.normalizer import normalize_dataset
from backend.app.ingestion.models import CommitMappingRequest, CanonicalRecord
from backend.app.ingestion.file_hasher import compute_file_hash
from backend.app.ingestion.conflict_detector import detect_record_conflicts, resolve_and_merge_records
from backend.app.validation.quality_scorer import calculate_data_quality_report
from backend.app.metrics.solar_metrics import calculate_solar_metrics
from backend.app.metrics.consumption_metrics import calculate_consumption_metrics
from backend.app.metrics.battery_metrics import calculate_battery_metrics
from backend.app.metrics.grid_metrics import calculate_grid_metrics
from backend.app.energy_balance.reconciliation import reconcile_energy_balance
from backend.app.events.state_classifier import build_operating_state_timeline
from backend.app.statistics.distributions import get_complete_statistical_profile
from backend.app.statistics.correlation import calculate_correlation_matrices
from backend.app.statistics.anomalies import detect_system_anomalies
from backend.app.finance.tariff_engine import TariffConfig, calculate_grid_cost
from backend.app.finance.cost_model import calculate_financial_performance
from backend.app.simulation.scenarios import simulate_system_scenarios
from backend.app.reporting.pdf_builder import build_pdf_report
from backend.app.reporting.excel_builder import build_excel_report
from backend.app.reporting.json_exporter import export_json_report
from backend.app.metrics.time_utils import format_time_12h, format_datetime_12h, hour_index_to_12h
from backend.app.aggregation.historical import (
    calculate_daily_summaries,
    calculate_weekly_summaries,
    calculate_monthly_summaries,
    calculate_averages_comparison
)
from backend.app.aggregation.hour_of_day import (
    calculate_hour_of_day_profiles,
    calculate_hour_date_heatmap
)
from backend.app.aggregation.comparisons import (
    compare_periods,
    compare_weekdays_vs_weekends
)

router = APIRouter()

dataset_cache: Dict[str, List[CanonicalRecord]] = {}

class SystemSettingsModel(BaseModel):
    pv_capacity_kwp: float = 5.0
    num_modules: int = 10
    module_wattage: float = 500.0
    inverter_power_kw: float = 5.0
    battery_chemistry: str = "LFP"
    battery_voltage: float = 51.2
    battery_capacity_kwh: float = 15.0
    usable_capacity_kwh: float = 11.25
    reserve_soc: float = 25.0
    max_charge_kw: float = 3.0
    max_discharge_kw: float = 3.0
    battery_efficiency: float = 0.95
    import_tariff: float = 11.50
    export_tariff: float = 0.0
    currency: str = "PHP"
    timezone: str = "Asia/Manila"

class ScenarioRequest(BaseModel):
    add_battery_kwh: float = 5.0
    add_pv_kwp: float = 2.0
    new_reserve_soc: float = 20.0
    shift_load_kwh: float = 2.0

class ReportGenRequest(BaseModel):
    report_type: str = "pdf"

class UpdateSourceModel(BaseModel):
    is_included: Optional[bool] = None
    sheet_name: Optional[str] = None

@router.get("/health")
def get_health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "timezone": settings.default_timezone,
        "currency": settings.default_currency,
        "time_format": "12-hour"
    }

@router.get("/settings")
def get_settings():
    conn = get_connection()
    row = conn.execute("SELECT * FROM system_settings WHERE project_id = 'default'").fetchone()
    conn.close()
    if row:
        return dict(row)
    return SystemSettingsModel().model_dump()

@router.put("/settings")
def update_settings(payload: SystemSettingsModel):
    conn = get_connection()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """UPDATE system_settings SET
            pv_capacity_kwp = ?, num_modules = ?, module_wattage = ?, inverter_power_kw = ?,
            battery_chemistry = ?, battery_voltage = ?, battery_capacity_kwh = ?,
            usable_capacity_kwh = ?, reserve_soc = ?, max_charge_kw = ?, max_discharge_kw = ?,
            battery_efficiency = ?, import_tariff = ?, export_tariff = ?, currency = ?,
            timezone = ?, updated_at = ?
        WHERE project_id = 'default'""",
        (
            payload.pv_capacity_kwp, payload.num_modules, payload.module_wattage,
            payload.inverter_power_kw, payload.battery_chemistry, payload.battery_voltage,
            payload.battery_capacity_kwh, payload.usable_capacity_kwh, payload.reserve_soc,
            payload.max_charge_kw, payload.max_discharge_kw, payload.battery_efficiency,
            payload.import_tariff, payload.export_tariff, payload.currency,
            payload.timezone, now
        )
    )
    conn.commit()
    conn.close()
    return {"status": "updated", "settings": payload.model_dump()}

@router.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):
    filename = file.filename or "upload.xlsx"
    contents = await file.read()
    
    file_hash = compute_file_hash(contents)
    file_format = "CSV" if filename.lower().endswith(".csv") else ("XLSM" if filename.lower().endswith(".xlsm") else "XLSX")

    conn = get_connection()
    existing = conn.execute("SELECT id FROM datasets WHERE file_hash = ?", (file_hash,)).fetchone()
    is_duplicate = existing is not None
    duplicate_of = existing["id"] if existing else None

    file_id, target_path = save_uploaded_file(filename, contents)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    sheets: List[str] = []
    if filename.lower().endswith((".xlsx", ".xlsm")):
        sheets = list_excel_sheets(target_path)

    conn.execute(
        """INSERT INTO datasets (id, project_id, filename, file_hash, file_format, filepath, sheet_name, is_active, is_included, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?)""",
        (file_id, "default", filename, file_hash, file_format, str(target_path), sheets[0] if sheets else None, now)
    )
    conn.commit()
    conn.close()

    return {
        "dataset_id": file_id,
        "filename": filename,
        "file_hash": file_hash,
        "is_duplicate": is_duplicate,
        "duplicate_of": duplicate_of,
        "available_sheets": sheets,
        "selected_sheet": sheets[0] if sheets else None
    }

def _auto_commit_dataset_core(dataset_id: str, conn: Any) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Dataset not found")

    filepath = Path(row["filepath"])
    filename = row["filename"]

    if filename.lower().endswith((".xlsx", ".xlsm")):
        sheets = list_excel_sheets(filepath)
        sel_sheet = row["sheet_name"] or (sheets[0] if sheets else None)
        headers, sample_records, total_count = read_excel_sheet(filepath, sheet_name=sel_sheet, max_rows=100)
    else:
        sheets = []
        sel_sheet = "CSV"
        headers, sample_records, total_count = read_csv_file(filepath, max_rows=100)

    mapping_items = build_column_mapping_preview(headers, sample_records)
    mappings: Dict[str, str] = {}
    sign_conventions: Dict[str, str] = {}
    for item in mapping_items:
        if item.is_duplicate:
            mappings[item.original_name] = "ignore"
        elif item.canonical_name:
            mappings[item.original_name] = item.canonical_name
        if item.sign_convention:
            sign_conventions[item.canonical_name or item.original_name] = item.sign_convention

    if filename.lower().endswith((".xlsx", ".xlsm")):
        _, all_records, total_count = read_excel_sheet(filepath, sheet_name=sel_sheet)
    else:
        _, all_records, total_count = read_csv_file(filepath)

    canonical_records = normalize_dataset(all_records, mappings, sign_conventions)
    dataset_cache[dataset_id] = canonical_records

    quality_rep = calculate_data_quality_report(canonical_records)
    quality_score = quality_rep["quality_score"]

    start_time = canonical_records[0].timestamp if canonical_records else None
    end_time = canonical_records[-1].timestamp if canonical_records else None

    mapping_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO column_mappings (id, dataset_id, raw_headers_json, mapping_json, sign_conventions_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (mapping_id, dataset_id, json.dumps(headers), json.dumps(mappings), json.dumps(sign_conventions), now)
    )
    conn.execute(
        """UPDATE datasets SET total_rows = ?, start_time = ?, end_time = ?, quality_score = ?, sheet_name = ?, is_included = 1
           WHERE id = ?""",
        (len(canonical_records), start_time, end_time, quality_score, sel_sheet, dataset_id)
    )

    return {
        "status": "committed",
        "dataset_id": dataset_id,
        "filename": filename,
        "total_records": len(canonical_records),
        "quality_score": quality_score,
        "quality_status": quality_rep["status"],
        "start_time_12h": format_datetime_12h(start_time),
        "end_time_12h": format_datetime_12h(end_time)
    }

@router.post("/datasets/{dataset_id}/auto_commit")
def auto_commit_single_dataset(dataset_id: str):
    conn = get_connection()
    try:
        res = _auto_commit_dataset_core(dataset_id, conn)
        conn.commit()
        return res
    finally:
        conn.close()

@router.post("/datasets/auto_commit_all")
def auto_commit_all_datasets():
    conn = get_connection()
    rows = conn.execute("SELECT id, filename FROM datasets WHERE total_rows = 0 OR total_rows IS NULL OR start_time IS NULL").fetchall()
    results = []
    for r in rows:
        try:
            res = _auto_commit_dataset_core(r["id"], conn)
            results.append(res)
        except Exception as e:
            results.append({"status": "error", "dataset_id": r["id"], "filename": r["filename"], "error": str(e)})
    conn.commit()
    conn.close()
    return {"total_processed": len(results), "committed": results}

@router.post("/datasets/upload_batch")
async def upload_datasets_batch(files: List[UploadFile] = File(...)):
    results = []
    conn = get_connection()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for file in files:
        filename = file.filename or "upload.xlsx"
        contents = await file.read()
        file_hash = compute_file_hash(contents)
        file_format = "CSV" if filename.lower().endswith(".csv") else ("XLSM" if filename.lower().endswith(".xlsm") else "XLSX")

        existing = conn.execute("SELECT id, total_rows FROM datasets WHERE file_hash = ?", (file_hash,)).fetchone()
        if existing and existing["total_rows"] and existing["total_rows"] > 0:
            results.append({
                "dataset_id": existing["id"],
                "filename": filename,
                "file_hash": file_hash,
                "file_format": file_format,
                "is_duplicate": True,
                "duplicate_of": existing["id"],
                "status": "already_committed"
            })
            continue

        if existing and (not existing["total_rows"] or existing["total_rows"] == 0):
            try:
                commit_info = _auto_commit_dataset_core(existing["id"], conn)
                results.append({
                    "dataset_id": existing["id"],
                    "filename": filename,
                    "file_hash": file_hash,
                    "file_format": file_format,
                    "is_duplicate": False,
                    "duplicate_of": None,
                    "status": "committed",
                    "total_records": commit_info["total_records"],
                    "quality_score": commit_info["quality_score"],
                    "start_time_12h": commit_info["start_time_12h"],
                    "end_time_12h": commit_info["end_time_12h"]
                })
                continue
            except Exception:
                pass

        file_id, target_path = save_uploaded_file(filename, contents)
        sheets: List[str] = []
        if filename.lower().endswith((".xlsx", ".xlsm")):
            sheets = list_excel_sheets(target_path)

        conn.execute(
            """INSERT INTO datasets (id, project_id, filename, file_hash, file_format, filepath, sheet_name, is_active, is_included, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?)""",
            (file_id, "default", filename, file_hash, file_format, str(target_path), sheets[0] if sheets else None, now)
        )

        try:
            commit_info = _auto_commit_dataset_core(file_id, conn)
            results.append({
                "dataset_id": file_id,
                "filename": filename,
                "file_hash": file_hash,
                "file_format": file_format,
                "is_duplicate": False,
                "duplicate_of": None,
                "status": "committed",
                "total_records": commit_info["total_records"],
                "quality_score": commit_info["quality_score"],
                "start_time_12h": commit_info["start_time_12h"],
                "end_time_12h": commit_info["end_time_12h"]
            })
        except Exception as e:
            results.append({
                "dataset_id": file_id,
                "filename": filename,
                "file_hash": file_hash,
                "file_format": file_format,
                "is_duplicate": False,
                "duplicate_of": None,
                "status": "pending",
                "error": str(e)
            })

    conn.commit()
    conn.close()
    return {"total_uploaded": len(results), "files": results}

@router.get("/sources")
def list_sources():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM datasets ORDER BY created_at DESC").fetchall()
    conn.close()

    items = []
    for r in rows:
        d = dict(r)
        d["start_time_12h"] = format_datetime_12h(d.get("start_time"))
        d["end_time_12h"] = format_datetime_12h(d.get("end_time"))
        items.append(d)
    return items

@router.patch("/sources/{source_id}")
def update_source(source_id: str, payload: UpdateSourceModel):
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ?", (source_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Source dataset not found")

    if payload.is_included is not None:
        val = 1 if payload.is_included else 0
        conn.execute("UPDATE datasets SET is_included = ? WHERE id = ?", (val, source_id))
    if payload.sheet_name is not None:
        conn.execute("UPDATE datasets SET sheet_name = ? WHERE id = ?", (payload.sheet_name, source_id))

    conn.commit()
    conn.close()
    return {"status": "updated", "source_id": source_id}

@router.delete("/sources/{source_id}")
def delete_source(source_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ?", (source_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Source dataset not found")

    filepath = Path(row["filepath"])
    if filepath.exists():
        try:
            filepath.unlink()
        except Exception:
            pass

    conn.execute("DELETE FROM column_mappings WHERE dataset_id = ?", (source_id,))
    conn.execute("DELETE FROM datasets WHERE id = ?", (source_id,))
    conn.commit()
    conn.close()

    if source_id in dataset_cache:
        del dataset_cache[source_id]

    return {"status": "deleted", "source_id": source_id}

@router.post("/datasets/load_sample")
def load_sample_dataset():
    sample_file = settings.sample_dir / "Oct 21.xlsx"
    if not sample_file.exists():
        fallback_path = Path("C:/Users/jahnm/Documents/solar/Oct 21.xlsx")
        if fallback_path.exists():
            import shutil
            shutil.copy(str(fallback_path), str(sample_file))
        else:
            raise HTTPException(status_code=404, detail="Sample dataset Oct 21.xlsx not found.")

    with open(sample_file, "rb") as f:
        contents = f.read()
    file_id, target_path = save_uploaded_file("Oct 21.xlsx", contents)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sheets = list_excel_sheets(target_path)
    file_hash = compute_file_hash(contents)

    conn = get_connection()
    conn.execute(
        """INSERT INTO datasets (id, project_id, filename, file_hash, file_format, filepath, sheet_name, is_active, is_included, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?)""",
        (file_id, "default", "Oct 21.xlsx", file_hash, "XLSX", str(target_path), sheets[0] if sheets else "2026-10-21", now)
    )
    conn.commit()
    conn.close()

    return {
        "dataset_id": file_id,
        "filename": "Oct 21.xlsx",
        "file_hash": file_hash,
        "available_sheets": sheets,
        "selected_sheet": sheets[0] if sheets else "2026-10-21"
    }

@router.get("/datasets/{dataset_id}/preview")
def preview_dataset(dataset_id: str, sheet_name: Optional[str] = None):
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    if not row and dataset_id in ["all", "historical"]:
        row = conn.execute("SELECT * FROM datasets WHERE is_included = 1 ORDER BY start_time DESC LIMIT 1").fetchone()
    if not row:
        row = conn.execute("SELECT * FROM datasets ORDER BY created_at DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="No datasets available for preview. Please upload a file first.")

    filepath = Path(row["filepath"])
    filename = row["filename"]
    actual_id = row["id"]
    
    if filename.lower().endswith((".xlsx", ".xlsm")):
        sheets = list_excel_sheets(filepath)
        sel_sheet = sheet_name or row["sheet_name"] or (sheets[0] if sheets else None)
        headers, sample_records, total_rows = read_excel_sheet(filepath, sheet_name=sel_sheet, max_rows=100)
    else:
        sheets = []
        sel_sheet = "CSV"
        headers, sample_records, total_rows = read_csv_file(filepath, max_rows=100)

    mapping_items = build_column_mapping_preview(headers, sample_records)
    
    time_item = next((item for item in mapping_items if item.canonical_name == "timestamp"), None)
    detected_start = None
    detected_end = None
    if time_item and sample_records:
        detected_start = str(sample_records[0].get(time_item.original_name, ""))
        detected_end = str(sample_records[-1].get(time_item.original_name, ""))

    return {
        "dataset_id": actual_id,
        "filename": filename,
        "available_sheets": sheets,
        "selected_sheet": sel_sheet,
        "total_rows": total_rows,
        "columns": [item.model_dump() for item in mapping_items],
        "detected_start_time": detected_start,
        "detected_start_time_12h": format_datetime_12h(detected_start),
        "detected_end_time": detected_end,
        "detected_end_time_12h": format_datetime_12h(detected_end),
        "preview_rows": sample_records[:10]
    }

@router.post("/datasets/{dataset_id}/commit")
def commit_dataset_mapping(dataset_id: str, payload: CommitMappingRequest):
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Dataset not found")

    filepath = Path(row["filepath"])
    filename = row["filename"]

    if filename.lower().endswith((".xlsx", ".xlsm")):
        headers, all_records, total_count = read_excel_sheet(filepath, sheet_name=payload.selected_sheet)
    else:
        headers, all_records, total_count = read_csv_file(filepath)

    canonical_records = normalize_dataset(all_records, payload.mappings, payload.sign_conventions)
    dataset_cache[dataset_id] = canonical_records

    quality_rep = calculate_data_quality_report(canonical_records)
    quality_score = quality_rep["quality_score"]

    start_time = canonical_records[0].timestamp if canonical_records else None
    end_time = canonical_records[-1].timestamp if canonical_records else None

    mapping_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO column_mappings (id, dataset_id, raw_headers_json, mapping_json, sign_conventions_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (mapping_id, dataset_id, json.dumps(headers), json.dumps(payload.mappings), json.dumps(payload.sign_conventions), now)
    )
    conn.execute(
        """UPDATE datasets SET total_rows = ?, start_time = ?, end_time = ?, quality_score = ?, sheet_name = ?, is_included = 1
           WHERE id = ?""",
        (total_count, start_time, end_time, quality_score, payload.selected_sheet, dataset_id)
    )
    conn.commit()
    conn.close()

    return {
        "status": "committed",
        "dataset_id": dataset_id,
        "total_records": len(canonical_records),
        "quality_score": quality_score,
        "quality_status": quality_rep["status"],
        "start_time_12h": format_datetime_12h(start_time),
        "end_time_12h": format_datetime_12h(end_time)
    }

def _get_records(dataset_id: str) -> List[CanonicalRecord]:
    if dataset_id in ["all", "historical"]:
        return _get_historical_records()

    if dataset_id in dataset_cache:
        return dataset_cache[dataset_id]
        
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    mapping_row = conn.execute("SELECT * FROM column_mappings WHERE dataset_id = ?", (dataset_id,)).fetchone()
    conn.close()
    
    if not row:
        return _get_historical_records()
        
    filepath = Path(row["filepath"])
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Dataset file missing on disk.")
        
    if mapping_row:
        mappings = json.loads(mapping_row["mapping_json"])
        sign_conventions = json.loads(mapping_row["sign_conventions_json"])
        sheet_name = row["sheet_name"]
    else:
        if row["filename"].lower().endswith((".xlsx", ".xlsm")):
            headers, sample_records, _ = read_excel_sheet(filepath, sheet_name=row["sheet_name"], max_rows=10)
        else:
            headers, sample_records, _ = read_csv_file(filepath, max_rows=10)
        preview = build_column_mapping_preview(headers, sample_records)
        mappings = {item.original_name: item.canonical_name for item in preview if item.canonical_name}
        sign_conventions = {item.canonical_name: item.sign_convention for item in preview if item.canonical_name}
        sheet_name = row["sheet_name"]

    if row["filename"].lower().endswith((".xlsx", ".xlsm")):
        _, all_records, _ = read_excel_sheet(filepath, sheet_name=sheet_name)
    else:
        _, all_records, _ = read_csv_file(filepath)

    records = normalize_dataset(all_records, mappings, sign_conventions)
    dataset_cache[dataset_id] = records
    return records

def _get_historical_records() -> List[CanonicalRecord]:
    conn = get_connection()
    rows = conn.execute("SELECT id FROM datasets WHERE is_included = 1 ORDER BY start_time ASC").fetchall()
    conn.close()

    if not rows:
        conn = get_connection()
        rows = conn.execute("SELECT id FROM datasets ORDER BY created_at DESC LIMIT 1").fetchall()
        conn.close()

    if not rows:
        return []

    merged: List[CanonicalRecord] = []
    for r in rows:
        d_id = r["id"]
        try:
            recs = _get_records(d_id)
            merged = resolve_and_merge_records(merged, recs, policy="KEEP_EXISTING")
        except Exception:
            continue
    return merged

@router.get("/datasets/{dataset_id}/summary")
def get_executive_summary(dataset_id: str):
    records = _get_records(dataset_id)
    settings_dict = get_settings()

    solar = calculate_solar_metrics(records, pv_capacity_kwp=settings_dict["pv_capacity_kwp"])
    consumption = calculate_consumption_metrics(records)
    battery = calculate_battery_metrics(records, nominal_capacity_kwh=settings_dict["battery_capacity_kwh"], reserve_soc=settings_dict["reserve_soc"])
    grid = calculate_grid_metrics(records, reserve_soc=settings_dict["reserve_soc"])
    balance = reconcile_energy_balance(records)
    quality = calculate_data_quality_report(records)

    tariff_conf = TariffConfig(
        flat_rate=settings_dict["import_tariff"],
        export_rate=settings_dict["export_tariff"],
        currency=settings_dict["currency"]
    )
    finance = calculate_financial_performance(records, tariff_conf)

    start_t = records[0].timestamp if records else ""
    end_t = records[-1].timestamp if records else ""

    return {
        "dataset_id": dataset_id,
        "date_range": f"{start_t[:10]} to {end_t[:10]}" if records else "",
        "start_time_12h": format_datetime_12h(start_t),
        "end_time_12h": format_datetime_12h(end_t),
        "quality": quality,
        "solar": solar,
        "consumption": consumption,
        "battery": battery,
        "grid": grid,
        "balance": balance,
        "finance": finance
    }

@router.get("/datasets/{dataset_id}/timeline")
def get_timeline_data(dataset_id: str):
    records = _get_records(dataset_id)
    return {
        "timestamps": [r.timestamp for r in records],
        "timestamps_12h": [format_datetime_12h(r.timestamp) for r in records],
        "pv_power_kw": [r.pv_power_kw for r in records],
        "load_power_kw": [r.load_power_kw for r in records],
        "grid_power_kw": [r.grid_power_kw for r in records],
        "battery_power_kw": [r.battery_power_kw for r in records],
        "soc_percent": [r.soc_percent for r in records],
        "residual_power_kw": [r.residual_power_kw for r in records]
    }

@router.get("/datasets/{dataset_id}/solar")
def get_solar_analysis(dataset_id: str):
    records = _get_records(dataset_id)
    settings_dict = get_settings()
    return calculate_solar_metrics(records, pv_capacity_kwp=settings_dict["pv_capacity_kwp"])

@router.get("/datasets/{dataset_id}/consumption")
def get_consumption_analysis(dataset_id: str):
    records = _get_records(dataset_id)
    return calculate_consumption_metrics(records)

@router.get("/datasets/{dataset_id}/battery")
def get_battery_analysis(dataset_id: str):
    records = _get_records(dataset_id)
    settings_dict = get_settings()
    return calculate_battery_metrics(records, nominal_capacity_kwh=settings_dict["battery_capacity_kwh"], reserve_soc=settings_dict["reserve_soc"])

@router.get("/datasets/{dataset_id}/grid")
def get_grid_analysis(dataset_id: str):
    records = _get_records(dataset_id)
    settings_dict = get_settings()
    return calculate_grid_metrics(records, reserve_soc=settings_dict["reserve_soc"])

@router.get("/datasets/{dataset_id}/balance")
def get_balance_analysis(dataset_id: str):
    records = _get_records(dataset_id)
    settings_dict = get_settings()
    return reconcile_energy_balance(records, inverter_efficiency=settings_dict["battery_efficiency"])

@router.get("/datasets/{dataset_id}/events")
def get_operating_states(dataset_id: str):
    records = _get_records(dataset_id)
    settings_dict = get_settings()
    return build_operating_state_timeline(records, reserve_soc=settings_dict["reserve_soc"])

@router.get("/datasets/{dataset_id}/statistics")
def get_statistical_analysis(dataset_id: str):
    records = _get_records(dataset_id)
    profiles = get_complete_statistical_profile(records)
    correlations = calculate_correlation_matrices(records)
    return {
        "profiles": profiles,
        "correlations": correlations
    }

@router.get("/datasets/{dataset_id}/anomalies")
def get_anomalies(dataset_id: str):
    records = _get_records(dataset_id)
    return detect_system_anomalies(records)

@router.post("/datasets/{dataset_id}/scenarios")
def run_scenario(dataset_id: str, payload: ScenarioRequest):
    records = _get_records(dataset_id)
    settings_dict = get_settings()
    return simulate_system_scenarios(
        records=records,
        baseline_battery_kwh=settings_dict["battery_capacity_kwh"],
        add_battery_kwh=payload.add_battery_kwh,
        baseline_pv_kwp=settings_dict["pv_capacity_kwp"],
        add_pv_kwp=payload.add_pv_kwp,
        new_reserve_soc=payload.new_reserve_soc,
        shift_load_kwh=payload.shift_load_kwh,
        tariff_rate=settings_dict["import_tariff"]
    )

@router.get("/datasets/{dataset_id}/finance")
def get_finance_analysis(
    dataset_id: str,
    tariff_type: str = "flat",
    flat_rate: Optional[float] = None,
    peak_rate: float = 14.50,
    off_peak_rate: float = 9.00
):
    records = _get_records(dataset_id)
    settings_dict = get_settings()
    rate = flat_rate or settings_dict["import_tariff"]
    conf = TariffConfig(
        tariff_type=tariff_type,
        flat_rate=rate,
        peak_rate=peak_rate,
        off_peak_rate=off_peak_rate,
        export_rate=settings_dict["export_tariff"],
        currency=settings_dict["currency"]
    )
    return calculate_financial_performance(records, conf)

@router.get("/historical/daily")
def get_historical_daily(dataset_id: Optional[str] = None):
    records = _get_records(dataset_id or "historical")
    settings_dict = get_settings()
    return calculate_daily_summaries(
        records=records,
        pv_capacity_kwp=settings_dict["pv_capacity_kwp"],
        nominal_battery_kwh=settings_dict["battery_capacity_kwh"],
        reserve_soc=settings_dict["reserve_soc"]
    )

@router.get("/historical/weekly")
def get_historical_weekly(dataset_id: Optional[str] = None):
    records = _get_records(dataset_id or "historical")
    settings_dict = get_settings()
    daily = calculate_daily_summaries(
        records=records,
        pv_capacity_kwp=settings_dict["pv_capacity_kwp"],
        nominal_battery_kwh=settings_dict["battery_capacity_kwh"],
        reserve_soc=settings_dict["reserve_soc"]
    )
    return calculate_weekly_summaries(daily)

@router.get("/historical/monthly")
def get_historical_monthly(dataset_id: Optional[str] = None):
    records = _get_records(dataset_id or "historical")
    settings_dict = get_settings()
    daily = calculate_daily_summaries(
        records=records,
        pv_capacity_kwp=settings_dict["pv_capacity_kwp"],
        nominal_battery_kwh=settings_dict["battery_capacity_kwh"],
        reserve_soc=settings_dict["reserve_soc"]
    )
    return calculate_monthly_summaries(daily)

@router.get("/historical/hourly_profile")
def get_historical_hourly_profile(dataset_id: Optional[str] = None):
    records = _get_records(dataset_id or "historical")
    return calculate_hour_of_day_profiles(records)

@router.get("/historical/heatmap")
def get_historical_heatmap(metric: str = "pv_power_kw", dataset_id: Optional[str] = None):
    records = _get_records(dataset_id or "historical")
    return calculate_hour_date_heatmap(records, metric=metric)

@router.get("/historical/averages")
def get_historical_averages(dataset_id: Optional[str] = None):
    records = _get_records(dataset_id or "historical")
    settings_dict = get_settings()
    daily = calculate_daily_summaries(
        records=records,
        pv_capacity_kwp=settings_dict["pv_capacity_kwp"],
        nominal_battery_kwh=settings_dict["battery_capacity_kwh"],
        reserve_soc=settings_dict["reserve_soc"]
    )
    return calculate_averages_comparison(records, daily)

@router.get("/historical/compare")
def compare_historical_periods(
    date_a_start: str,
    date_a_end: str,
    date_b_start: str,
    date_b_end: str,
    dataset_id: Optional[str] = None
):
    records = _get_records(dataset_id or "historical")
    recs_a = [r for r in records if date_a_start <= r.timestamp[:10] <= date_a_end]
    recs_b = [r for r in records if date_b_start <= r.timestamp[:10] <= date_b_end]
    return compare_periods(recs_a, recs_b, label_a=f"{date_a_start} to {date_a_end}", label_b=f"{date_b_start} to {date_b_end}")

@router.get("/historical/weekdays_vs_weekends")
def get_weekdays_vs_weekends(dataset_id: Optional[str] = None):
    records = _get_records(dataset_id or "historical")
    return compare_weekdays_vs_weekends(records)

@router.post("/datasets/{dataset_id}/reports/generate")
def generate_report(dataset_id: str, payload: ReportGenRequest):
    records = _get_records(dataset_id)
    settings_dict = get_settings()

    solar = calculate_solar_metrics(records, pv_capacity_kwp=settings_dict["pv_capacity_kwp"])
    consumption = calculate_consumption_metrics(records)
    battery = calculate_battery_metrics(records, nominal_capacity_kwh=settings_dict["battery_capacity_kwh"], reserve_soc=settings_dict["reserve_soc"])
    grid = calculate_grid_metrics(records, reserve_soc=settings_dict["reserve_soc"])
    balance = reconcile_energy_balance(records)
    quality = calculate_data_quality_report(records)
    operating_states = build_operating_state_timeline(records, reserve_soc=settings_dict["reserve_soc"])

    start_t = records[0].timestamp if records else ""
    end_t = records[-1].timestamp if records else ""

    summary_data = {
        "report_date": datetime.date.today().isoformat(),
        "filename": "SolarScope_Dataset",
        "sheet_name": "Audited",
        "start_time": start_t,
        "start_time_12h": format_datetime_12h(start_t),
        "end_time": end_t,
        "end_time_12h": format_datetime_12h(end_t),
        "quality_score": quality["quality_score"],
        "quality_status": quality["status"],
        "pv_kwh": balance["pv_kwh"],
        "load_kwh": balance["household_demand_kwh"],
        "grid_import_kwh": balance["grid_imported_kwh"],
        "grid_export_kwh": balance["grid_exported_kwh"],
        "batt_disch_kwh": balance["battery_discharged_kwh"],
        "batt_chg_kwh": balance["battery_charged_kwh"],
        "residual_kwh": balance["residual_kwh"],
        "self_consumption": balance["solar_self_consumption_ratio"],
        "self_sufficiency": balance["solar_self_sufficiency_ratio"],
        "grid_dependence": grid["grid_dependence_ratio"],
        "peak_pv_kw": solar["peak_power_kw"],
        "peak_pv_time_12h": solar.get("peak_power_time_12h", ""),
        "peak_load_kw": consumption["peak_load_kw"],
        "peak_load_time_12h": consumption.get("peak_load_time_12h", ""),
        "base_load_kw": consumption["base_load_estimate_kw"],
        "total_sources_kwh": balance["total_sources_kwh"],
        "total_sinks_kwh": balance["total_sinks_kwh"]
    }

    report_id = str(uuid.uuid4())
    rep_type = payload.report_type.lower()
    
    if rep_type == "pdf":
        out_filename = f"SolarScope_Audit_{dataset_id[:8]}.pdf"
        out_path = settings.reports_dir / out_filename
        build_pdf_report(summary_data, out_path)
    elif rep_type == "excel" or rep_type == "xlsx":
        out_filename = f"SolarScope_Audit_{dataset_id[:8]}.xlsx"
        out_path = settings.reports_dir / out_filename
        hourly = []
        for h in range(24):
            hourly.append({
                "hour": h,
                "hour_label_12h": hour_index_to_12h(h),
                "pv_kwh": solar["hourly_breakdown"][h]["energy_kwh"],
                "load_kwh": consumption["hourly_breakdown"][h]["energy_kwh"],
                "grid_kwh": grid["hourly_breakdown"][h]["energy_kwh"]
            })
        build_excel_report(records, summary_data, hourly, operating_states, out_path)
    else:
        out_filename = f"SolarScope_Audit_{dataset_id[:8]}.json"
        out_path = settings.reports_dir / out_filename
        export_json_report({
            "summary": summary_data,
            "solar": solar,
            "consumption": consumption,
            "battery": battery,
            "grid": grid,
            "balance": balance,
            "quality": quality,
            "operating_states": operating_states
        }, out_path)

    conn = get_connection()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    filesize = out_path.stat().st_size if out_path.exists() else 0
    conn.execute(
        """INSERT INTO audit_reports (id, dataset_id, report_type, filepath, filesize, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (report_id, dataset_id, rep_type, str(out_path), filesize, now)
    )
    conn.commit()
    conn.close()

    return {
        "report_id": report_id,
        "filename": out_filename,
        "report_type": rep_type,
        "filesize_bytes": filesize,
        "download_url": f"/api/reports/{report_id}/download"
    }

@router.get("/reports/{report_id}/download")
def download_report(report_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM audit_reports WHERE id = ?", (report_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Report record not found.")
    path = Path(row["filepath"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file not found on disk.")
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/octet-stream"
    )
