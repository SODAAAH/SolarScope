import os
import uuid
import json
import urllib.parse
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Body, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.storage.db import get_connection
from backend.app.storage.file_store import save_uploaded_file, get_file_path, resolve_dataset_path, extract_basename, delete_file
from backend.app.storage.blob_sync import ensure_hydrated, persist_state
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
from backend.app.billing import (
    TEIRateComponent,
    TEIRateSchedule,
    TEIBillingProfile,
    BillLineItem,
    StatementOfAccount,
    BillForecastScenario,
    BillForecastResponse,
    calculate_statement_of_account,
    get_active_rate_schedule,
    save_rate_schedule,
    get_rate_history,
    check_official_tei_rates,
    get_billing_profile,
    save_billing_profile,
    forecast_tei_bill,
    calculate_billing_progress_series,
    calculate_solar_bill_savings,
    simulate_rate_sensitivity,
    get_historical_bills_summary,
    insert_historical_bill,
    remove_historical_bill
)
from backend.app.billing.billing_profile import compute_cycle_dates
from backend.app.integrations.deye_cloud import DeyeCloudClient
from backend.app.integrations.weather import get_weather_intelligence
from backend.app.ingestion.multi_preview import inspect_file_for_preview
from backend.app.analyst.analyst_service import (
    analyze_energy_query,
    get_preset_diagnostic_queries,
    stream_analyst_response,
    get_performance_overview
)

router = APIRouter()

dataset_cache: Dict[str, List[CanonicalRecord]] = {}
_historical_records_cache: Optional[List[CanonicalRecord]] = None
_summary_cache: Dict[str, Any] = {}
_daily_summaries_cache: Dict[str, Any] = {}
_timeline_cache: Dict[str, Any] = {}

def invalidate_all_caches():
    global _historical_records_cache
    _historical_records_cache = None
    _summary_cache.clear()
    _daily_summaries_cache.clear()
    _timeline_cache.clear()

def _hydrate_state(force: bool = False) -> bool:
    updated = ensure_hydrated(force=force)
    if updated:
        dataset_cache.clear()
        invalidate_all_caches()
        try:
            from backend.app.integrations.deye_mcp import deye_mcp_client
            deye_mcp_client.invalidate_cache(clear_last_real=False)
        except Exception:
            pass
    return updated

def _persist_state(
    upload_files: Optional[List[Path]] = None,
    deleted_filenames: Optional[List[str]] = None,
) -> bool:
    return persist_state(upload_files=upload_files, deleted_filenames=deleted_filenames)

last_rate_check_cache: Dict[str, Any] = {
    "status": "verified_current",
    "message": "Using verified October 2026 schedule",
    "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "rate_change_alert": None
}

class SensitivityRequest(BaseModel):
    delta_gen_rate: float = 0.0
    delta_usage_pct: float = 0.0
    custom_kwh: Optional[float] = None

class AddHistoricalBillRequest(BaseModel):
    billing_period_start: str
    billing_period_end: str
    billed_kwh: float
    actual_amount_due: float
    predicted_amount_due: Optional[float] = None
    notes: Optional[str] = ""

class ManualRateScheduleRequest(BaseModel):
    effective_month: str
    customer_class: str = "Residential"
    generation_charge: float
    generation_vat: float = 0.71120
    distribution_charge: float = 1.45200
    transmission_charge: float = 0.85240
    system_loss_charge: float = 0.54120

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
    _hydrate_state()
    conn = get_connection()
    row = conn.execute("SELECT * FROM system_settings WHERE project_id = 'default'").fetchone()
    conn.close()
    if row:
        return dict(row)
    return SystemSettingsModel().model_dump()

@router.put("/settings")
def update_settings(payload: SystemSettingsModel):
    _hydrate_state(force=True)
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
    invalidate_all_caches()
    _persist_state()
    return {"status": "updated", "settings": payload.model_dump()}

@router.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):
    _hydrate_state(force=True)
    filename = file.filename or "upload.xlsx"
    contents = await file.read()
    
    file_hash = compute_file_hash(contents)
    file_format = "CSV" if filename.lower().endswith(".csv") else ("XLSM" if filename.lower().endswith(".xlsm") else "XLSX")

    conn = get_connection()
    existing_rows = conn.execute("SELECT id, filepath FROM datasets WHERE file_hash = ? OR filename = ?", (file_hash, filename)).fetchall()
    is_duplicate = len(existing_rows) > 0
    duplicate_of = existing_rows[0]["id"] if is_duplicate else None
    deleted_names: List[str] = []

    for row in existing_rows:
        if row["filepath"]:
            old_name = extract_basename(row["filepath"])
            if old_name:
                deleted_names.append(old_name)
            delete_file(row["filepath"], remove_remote=False)
        conn.execute("DELETE FROM column_mappings WHERE dataset_id = ?", (row["id"],))
        conn.execute("DELETE FROM datasets WHERE id = ?", (row["id"],))
        dataset_cache.pop(row["id"], None)

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
    invalidate_all_caches()
    filtered_deleted = [n for n in deleted_names if n != target_path.name]
    _persist_state(upload_files=[target_path], deleted_filenames=filtered_deleted or None)

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

    filepath = resolve_dataset_path(row["filepath"])
    filename = row["filename"]
    if not filepath or not filepath.exists():
        raise HTTPException(status_code=404, detail="Dataset file not found on disk.")

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
    _hydrate_state(force=True)
    conn = get_connection()
    try:
        res = _auto_commit_dataset_core(dataset_id, conn)
        conn.commit()
        invalidate_all_caches()
        _persist_state()
        return res
    finally:
        conn.close()

@router.post("/datasets/auto_commit_all")
def auto_commit_all_datasets():
    _hydrate_state(force=True)
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
    invalidate_all_caches()
    if results:
        _persist_state()
    return {"total_processed": len(results), "committed": results}

@router.post("/datasets/upload_batch")
async def upload_datasets_batch(files: List[UploadFile] = File(...)):
    _hydrate_state(force=True)
    results = []
    conn = get_connection()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    seen_hashes = set()
    uploaded_paths: List[Path] = []
    deleted_names: List[str] = []

    for file in files:
        filename = file.filename or "upload.xlsx"
        contents = await file.read()
        file_hash = compute_file_hash(contents)
        file_format = "CSV" if filename.lower().endswith(".csv") else ("XLSM" if filename.lower().endswith(".xlsm") else "XLSX")

        if file_hash in seen_hashes:
            continue
        seen_hashes.add(file_hash)

        existing_rows = conn.execute("SELECT id, filepath FROM datasets WHERE file_hash = ? OR filename = ?", (file_hash, filename)).fetchall()
        for row in existing_rows:
            if row["filepath"]:
                old_name = extract_basename(row["filepath"])
                if old_name:
                    deleted_names.append(old_name)
                delete_file(row["filepath"], remove_remote=False)
            conn.execute("DELETE FROM column_mappings WHERE dataset_id = ?", (row["id"],))
            conn.execute("DELETE FROM datasets WHERE id = ?", (row["id"],))
            dataset_cache.pop(row["id"], None)

        file_id, target_path = save_uploaded_file(filename, contents)
        uploaded_paths.append(target_path)
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
                "is_duplicate": len(existing_rows) > 0,
                "duplicate_of": existing_rows[0]["id"] if existing_rows else None,
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
                "is_duplicate": len(existing_rows) > 0,
                "duplicate_of": existing_rows[0]["id"] if existing_rows else None,
                "status": "pending",
                "error": str(e)
            })

    conn.commit()
    conn.close()
    invalidate_all_caches()
    uploaded_basenames = {p.name for p in uploaded_paths}
    filtered_deleted = [n for n in deleted_names if n not in uploaded_basenames]
    _persist_state(upload_files=uploaded_paths or None, deleted_filenames=filtered_deleted or None)
    return {"total_uploaded": len(results), "files": results}

@router.get("/sources")
def list_sources():
    _hydrate_state()
    conn = get_connection()
    rows = conn.execute("SELECT * FROM datasets ORDER BY COALESCE(start_time, created_at) ASC, filename ASC").fetchall()
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
    _hydrate_state(force=True)
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
    invalidate_all_caches()
    _persist_state()
    return {"status": "updated", "source_id": source_id}

@router.delete("/sources/{source_id}")
def delete_source(source_id: str):
    _hydrate_state(force=True)
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ?", (source_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Source dataset not found")

    deleted_name = extract_basename(row["filepath"]) if row["filepath"] else ""
    delete_file(row["filepath"], remove_remote=False)

    conn.execute("DELETE FROM column_mappings WHERE dataset_id = ?", (source_id,))
    conn.execute("DELETE FROM datasets WHERE id = ?", (source_id,))
    conn.commit()
    conn.close()
    dataset_cache.pop(source_id, None)
    invalidate_all_caches()
    _persist_state(deleted_filenames=[deleted_name] if deleted_name else None)
    return {"status": "deleted", "source_id": source_id}

@router.post("/datasets/load_sample")
def load_sample_dataset():
    _hydrate_state(force=True)
    sample_file = settings.sample_dir / "Oct 21.xlsx"
    if not sample_file.exists():
        static_sample = settings.base_dir / "data" / "sample" / "Oct 21.xlsx"
        fallback_path = Path("C:/Users/jahnm/Documents/solar/Oct 21.xlsx")
        src_sample = static_sample if static_sample.exists() else (fallback_path if fallback_path.exists() else None)
        if src_sample is not None:
            import shutil
            sample_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(str(src_sample), str(sample_file))
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
    invalidate_all_caches()
    _persist_state(upload_files=[target_path])

    return {
        "dataset_id": file_id,
        "filename": "Oct 21.xlsx",
        "file_hash": file_hash,
        "available_sheets": sheets,
        "selected_sheet": sheets[0] if sheets else "2026-10-21"
    }

@router.get("/datasets/{dataset_id}/preview")
def preview_dataset(dataset_id: str, sheet_name: Optional[str] = None):
    _hydrate_state()
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    if not row and dataset_id in ["all", "historical"]:
        row = conn.execute("SELECT * FROM datasets WHERE is_included = 1 ORDER BY start_time DESC LIMIT 1").fetchone()
    if not row:
        row = conn.execute("SELECT * FROM datasets ORDER BY created_at DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        return {
            "dataset_id": "",
            "filename": "",
            "available_sheets": [],
            "selected_sheet": "",
            "total_rows": 0,
            "columns": [],
            "preview_rows": [],
            "detected_start_time_12h": None,
            "detected_end_time_12h": None
        }

    filepath = resolve_dataset_path(row["filepath"])
    filename = row["filename"]
    actual_id = row["id"]

    if not filepath or not filepath.exists():
        return {
            "dataset_id": actual_id,
            "filename": filename,
            "available_sheets": [],
            "selected_sheet": "",
            "total_rows": 0,
            "columns": [],
            "preview_rows": [],
            "detected_start_time_12h": None,
            "detected_end_time_12h": None
        }
    
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
    _hydrate_state(force=True)
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Dataset not found")

    filepath = resolve_dataset_path(row["filepath"])
    filename = row["filename"]
    if not filepath or not filepath.exists():
        conn.close()
        raise HTTPException(status_code=404, detail="Dataset file not found on disk.")

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
    invalidate_all_caches()
    _persist_state()

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
    _hydrate_state()
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
        
    filepath = resolve_dataset_path(row["filepath"])
    if not filepath or not filepath.exists():
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
    global _historical_records_cache
    _hydrate_state()
    if _historical_records_cache is not None:
        return _historical_records_cache

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
    _historical_records_cache = merged
    return merged

@router.get("/datasets/{dataset_id}/summary")
def get_executive_summary(dataset_id: str):
    _hydrate_state()
    if dataset_id in _summary_cache:
        return _summary_cache[dataset_id]
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

    result = {
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
    _summary_cache[dataset_id] = result
    return result

@router.get("/datasets/{dataset_id}/timeline")
def get_timeline_data(dataset_id: str, date: Optional[str] = Query(None)):
    _hydrate_state()
    cache_key = f"{dataset_id}_{date or ''}"
    if cache_key in _timeline_cache:
        return _timeline_cache[cache_key]
    records = _get_records(dataset_id)
    if not records:
        return {
            "timestamps": [],
            "timestamps_12h": [],
            "timestamps_24h": [],
            "pv_power_kw": [],
            "load_power_kw": [],
            "grid_power_kw": [],
            "battery_power_kw": [],
            "soc_percent": [],
            "residual_power_kw": [],
            "is_24h": True,
            "selected_date": date or ""
        }

    target_date = date
    if not target_date:
        if dataset_id not in ["all", "historical"]:
            target_date = records[0].timestamp[:10]
        else:
            target_date = records[-1].timestamp[:10]

    target_date_clean = target_date.strip().split(" ")[0].split("T")[0]
    day_recs_map = {}
    for r in records:
        if r.timestamp.startswith(target_date_clean):
            t_key = r.timestamp.split(" ")[1][:5] if " " in r.timestamp else r.timestamp[:5]
            day_recs_map[t_key] = r

    slots_24h = [f"{h:02d}:{m:02d}" for h in range(24) for m in range(0, 60, 5)] + ["24:00"]
    timestamps_full = [f"{target_date_clean} {s}:00" if s != "24:00" else f"{target_date_clean} 23:59:59" for s in slots_24h]
    timestamps_12h = [format_datetime_12h(ts) for ts in timestamps_full]

    pv_kw = []
    load_kw = []
    grid_kw = []
    battery_kw = []
    soc_pct = []
    residual_kw = []

    for s in slots_24h:
        lookup_key = s if s != "24:00" else "23:55"
        if lookup_key in day_recs_map:
            rec = day_recs_map[lookup_key]
            pv_kw.append(round(rec.pv_power_kw, 3))
            load_kw.append(round(rec.load_power_kw, 3))
            grid_kw.append(round(rec.grid_power_kw, 3))
            battery_kw.append(round(rec.battery_power_kw, 3))
            soc_pct.append(round(rec.soc_percent, 1))
            residual_kw.append(round(rec.residual_power_kw, 3))
        else:
            pv_kw.append(None)
            load_kw.append(None)
            grid_kw.append(None)
            battery_kw.append(None)
            soc_pct.append(None)
            residual_kw.append(None)

    timeline_res = {
        "timestamps": timestamps_full,
        "timestamps_12h": timestamps_12h,
        "timestamps_24h": slots_24h,
        "pv_power_kw": pv_kw,
        "load_power_kw": load_kw,
        "grid_power_kw": grid_kw,
        "battery_power_kw": battery_kw,
        "soc_percent": soc_pct,
        "residual_power_kw": residual_kw,
        "is_24h": True,
        "selected_date": target_date_clean
    }
    _timeline_cache[cache_key] = timeline_res
    return timeline_res

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
    off_peak_rate: float = 9.00,
    system_capex: float = 250000.0
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
    return calculate_financial_performance(records, conf, system_capex=system_capex)

@router.get("/historical/daily")
def get_historical_daily(dataset_id: Optional[str] = None):
    _hydrate_state()
    cache_key = dataset_id or "historical"
    if cache_key in _daily_summaries_cache:
        return _daily_summaries_cache[cache_key]
    records = _get_records(cache_key)
    settings_dict = get_settings()
    res = calculate_daily_summaries(
        records=records,
        pv_capacity_kwp=settings_dict["pv_capacity_kwp"],
        nominal_battery_kwh=settings_dict["battery_capacity_kwh"],
        reserve_soc=settings_dict["reserve_soc"]
    )
    _daily_summaries_cache[cache_key] = res
    return res

@router.get("/historical/weekly")
def get_historical_weekly(dataset_id: Optional[str] = None):
    daily = get_historical_daily(dataset_id)
    return calculate_weekly_summaries(daily)

@router.get("/historical/monthly")
def get_historical_monthly(dataset_id: Optional[str] = None):
    daily = get_historical_daily(dataset_id)
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
    records = _get_historical_records()
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

def _resolve_billing_profile(conn: Any, request: Optional[Request] = None) -> TEIBillingProfile:
    current = get_billing_profile(conn)
    raw_profile = None
    if request is not None:
        raw_profile = request.headers.get("X-Billing-Profile") or request.cookies.get("solarscope_billing_profile")
    if raw_profile:
        try:
            decoded = urllib.parse.unquote(raw_profile)
            parsed = json.loads(decoded)
            if isinstance(parsed, dict):
                incoming_ts = parsed.get("updated_at") or ""
                current_ts = current.updated_at or ""
                if isinstance(incoming_ts, str) and incoming_ts > current_ts:
                    profile = TEIBillingProfile(**parsed)
                    cycle_day = max(1, min(31, int(profile.billing_cycle_day or 25)))
                    start_dt, end_dt = compute_cycle_dates(cycle_day)
                    profile.billing_cycle_day = cycle_day
                    profile.cycle_start_date = start_dt.strftime("%Y-%m-%d")
                    profile.cycle_end_date = end_dt.strftime("%Y-%m-%d")
                    save_billing_profile(profile, conn)
                    conn.commit()
                    _persist_state()
                    return get_billing_profile(conn)
        except Exception:
            pass
    return current

@router.get("/billing/overview")
def get_billing_overview(request: Request, response: Response, dataset_id: Optional[str] = None):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    sched = get_active_rate_schedule(conn)
    profile = _resolve_billing_profile(conn, request)
    conn.close()
    records = _get_records("all")
    return forecast_tei_bill(records, sched, profile, last_rate_check_cache)

@router.get("/billing/progress")
def get_billing_progress(request: Request, response: Response, dataset_id: Optional[str] = None):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    sched = get_active_rate_schedule(conn)
    profile = _resolve_billing_profile(conn, request)
    conn.close()
    records = _get_records("all")
    return calculate_billing_progress_series(records, sched, profile)

@router.get("/billing/statement")
def get_billing_statement(request: Request, response: Response, mode: str = "expected", dataset_id: Optional[str] = None):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    sched = get_active_rate_schedule(conn)
    profile = _resolve_billing_profile(conn, request)
    conn.close()
    records = _get_records("all")
    forecast = forecast_tei_bill(records, sched, profile, last_rate_check_cache)
    if mode == "actual":
        return forecast.current_so_far_statement
    elif mode == "lower":
        return forecast.lower_estimate.statement
    elif mode == "higher":
        return forecast.higher_estimate.statement
    return forecast.expected_estimate.statement

@router.get("/billing/profile")
def get_billing_profile_endpoint(request: Request, response: Response):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    prof = _resolve_billing_profile(conn, request)
    conn.close()
    return prof.model_dump()

@router.put("/billing/profile")
def update_billing_profile_endpoint(profile: TEIBillingProfile, response: Response):
    _hydrate_state(force=True)
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    save_billing_profile(profile, conn)
    conn.commit()
    saved = get_billing_profile(conn)
    conn.close()
    _persist_state()
    encoded = urllib.parse.quote(json.dumps(saved.model_dump()))
    response.set_cookie(
        key="solarscope_billing_profile",
        value=encoded,
        max_age=31536000,
        path="/",
        samesite="lax"
    )
    return {"status": "updated", "profile": saved.model_dump()}

@router.get("/billing/rates")
def get_billing_rates(response: Response):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    rates = get_rate_history(conn)
    conn.close()
    return rates

@router.post("/billing/rates/check_now")
def check_billing_rates_now():
    global last_rate_check_cache
    _hydrate_state(force=True)
    conn = get_connection()
    res = check_official_tei_rates(conn, force_fetch=True)
    conn.commit()
    conn.close()
    _persist_state()
    last_rate_check_cache = res
    return {
        "status": res["status"],
        "message": res["message"],
        "checked_at": res["checked_at"],
        "rate_change_alert": res["rate_change_alert"],
        "effective_month": res["active_schedule"].effective_month if res.get("active_schedule") else "2026-10"
    }

@router.post("/billing/rates/manual")
def add_manual_billing_rate(payload: ManualRateScheduleRequest):
    global last_rate_check_cache
    import hashlib
    _hydrate_state(force=True)
    conn = get_connection()
    active_sched = get_active_rate_schedule(conn)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_comps = []
    for comp in active_sched.components:
        c_copy = comp.model_copy()
        if c_copy.component_id == "gen_charge":
            c_copy.rate_per_kwh = payload.generation_charge
            c_copy.vat_rate_per_kwh = payload.generation_vat
        elif c_copy.component_id == "dist_charge":
            c_copy.rate_per_kwh = payload.distribution_charge
        elif c_copy.component_id == "trans_charge":
            c_copy.rate_per_kwh = payload.transmission_charge
        elif c_copy.component_id == "system_loss_charge":
            c_copy.rate_per_kwh = payload.system_loss_charge
        new_comps.append(c_copy)
    new_sched = TEIRateSchedule(
        id=f"tei-rate-{payload.effective_month}-{payload.customer_class.lower()}-manual",
        effective_month=payload.effective_month,
        customer_class=payload.customer_class,
        publication_date=datetime.datetime.now().strftime("%Y-%m-%d"),
        source_url="Manual User Entry",
        document_hash=hashlib.sha256(f"{payload.effective_month}-{payload.generation_charge}".encode()).hexdigest(),
        verification_status="manual",
        components=new_comps,
        created_at=now_iso
    )
    save_rate_schedule(new_sched, conn)
    conn.commit()
    conn.close()
    _persist_state()
    last_rate_check_cache = {
        "status": "manual_applied",
        "message": f"Manual rate schedule for {payload.effective_month} activated.",
        "checked_at": now_iso,
        "rate_change_alert": None
    }
    return {"status": "created", "schedule_id": new_sched.id}

@router.post("/billing/sensitivity")
def calculate_sensitivity_endpoint(request: Request, response: Response, payload: SensitivityRequest, dataset_id: Optional[str] = None):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    sched = get_active_rate_schedule(conn)
    profile = _resolve_billing_profile(conn, request)
    conn.close()
    records = _get_records(dataset_id or "all")
    forecast = forecast_tei_bill(records, sched, profile, last_rate_check_cache)
    base_kwh = forecast.expected_estimate.total_projected_kwh
    return simulate_rate_sensitivity(
        base_kwh=base_kwh,
        schedule=sched,
        profile=profile,
        billing_start=forecast.billing_cycle_start,
        billing_end=forecast.billing_cycle_end,
        delta_gen_rate=payload.delta_gen_rate,
        delta_usage_pct=payload.delta_usage_pct,
        custom_kwh=payload.custom_kwh
    )

@router.get("/billing/history")
def get_historical_bills_endpoint(response: Response):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    bills = get_historical_bills_summary(conn)
    conn.close()
    return bills

@router.post("/billing/history")
def add_historical_bill_endpoint(payload: AddHistoricalBillRequest):
    _hydrate_state(force=True)
    conn = get_connection()
    res = insert_historical_bill(
        billing_period_start=payload.billing_period_start,
        billing_period_end=payload.billing_period_end,
        billed_kwh=payload.billed_kwh,
        actual_amount_due=payload.actual_amount_due,
        predicted_amount_due=payload.predicted_amount_due,
        notes=payload.notes or "",
        conn=conn
    )
    conn.commit()
    conn.close()
    _persist_state()
    return res

@router.delete("/billing/history/{bill_id}")
def delete_historical_bill_endpoint(bill_id: str):
    _hydrate_state(force=True)
    conn = get_connection()
    success = remove_historical_bill(bill_id, conn)
    conn.commit()
    conn.close()
    if not success:
        raise HTTPException(status_code=404, detail="Historical bill not found")
    _persist_state()
    return {"status": "deleted", "id": bill_id}

class DeyeConfigPayload(BaseModel):
    station_id: Optional[str] = ""
    app_id: Optional[str] = ""
    app_secret: Optional[str] = ""
    username: Optional[str] = ""
    password: Optional[str] = ""
    auto_sync: Optional[bool] = False
    sync_interval_min: Optional[int] = 5
    reconciliation_policy: Optional[str] = "MERGE"

@router.get("/deye/status")
def get_deye_status_endpoint(response: Response):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    client = DeyeCloudClient()
    status = client.get_status()
    status["is_demo"] = status.get("app_id") == "demo" or status.get("username") == "demo"
    return status

@router.post("/deye/config")
def save_deye_config_endpoint(payload: DeyeConfigPayload, response: Response):
    response.headers["Cache-Control"] = "no-store"
    client = DeyeCloudClient()
    client.save_config(payload.model_dump())
    status = client.get_status()
    status["is_demo"] = status.get("app_id") == "demo" or status.get("username") == "demo"
    return status

@router.post("/deye/test")
def test_deye_connection_endpoint(response: Response, payload: Optional[DeyeConfigPayload] = Body(default=None)):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    client = DeyeCloudClient()
    if payload and any([payload.station_id, payload.app_id, payload.app_secret, payload.username, payload.password]):
        client.save_config(payload.model_dump())
    return client.test_connection()

class DeyeSyncRangePayload(BaseModel):
    start_date: str
    end_date: str
    credentials: Optional[DeyeConfigPayload] = None

@router.post("/deye/sync")
def sync_deye_endpoint(payload: Optional[DeyeConfigPayload] = Body(default=None)):
    try:
        _hydrate_state(force=True)
        client = DeyeCloudClient()
        if payload and any([payload.station_id, payload.app_id, payload.app_secret, payload.username, payload.password]):
            client.save_config(payload.model_dump())
        res = client.sync_now()
        dataset_cache.clear()
        invalidate_all_caches()
        return res
    except Exception as e:
        return {"status": "FAILED", "message": str(e), "records_inserted": 0}

@router.post("/deye/sync_range")
def sync_deye_range_endpoint(payload: DeyeSyncRangePayload):
    try:
        _hydrate_state(force=True)
        client = DeyeCloudClient()
        if payload.credentials and any([payload.credentials.station_id, payload.credentials.app_id, payload.credentials.app_secret, payload.credentials.username, payload.credentials.password]):
            client.save_config(payload.credentials.model_dump())
        res = client.sync_range(payload.start_date, payload.end_date)
        dataset_cache.clear()
        invalidate_all_caches()
        return res
    except Exception as e:
        return {"status": "FAILED", "message": str(e), "records_inserted": 0}

@router.get("/deye/missing_dates")
def get_deye_missing_dates_endpoint():
    _hydrate_state()
    client = DeyeCloudClient()
    missing = client.get_missing_dates()
    return {"missing_dates": missing, "count": len(missing)}

@router.post("/deye/sync_missing")
def sync_deye_missing_endpoint():
    _hydrate_state(force=True)
    client = DeyeCloudClient()
    res = client.sync_missing_dates()
    dataset_cache.clear()
    invalidate_all_caches()
    return res

@router.get("/deye/live_flow")
def get_deye_live_flow_endpoint(response: Response):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    from backend.app.integrations.deye_mcp import deye_mcp_client
    return deye_mcp_client.get_live_flow()

@router.get("/deye/health")
def get_deye_health_endpoint(response: Response):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    from backend.app.integrations.deye_mcp import deye_mcp_client
    return deye_mcp_client.get_station_health()

@router.get("/weather/intelligence")
def get_weather_endpoint():
    _hydrate_state()
    conn = get_connection()
    sys_row = conn.execute("SELECT pv_capacity_kwp, battery_capacity_kwh, reserve_soc FROM system_settings WHERE project_id = 'default'").fetchone()
    conn.close()
    kwp = sys_row["pv_capacity_kwp"] if sys_row else 6.2
    batt = sys_row["battery_capacity_kwh"] if sys_row else 16.08
    res_soc = sys_row["reserve_soc"] if sys_row else 20.0
    return get_weather_intelligence(installed_kwp=kwp, battery_capacity_kwh=batt, reserve_soc=res_soc)

@router.post("/ingestion/preview")
async def preview_uploaded_files(file: UploadFile = File(...)):
    temp_dir = settings.data_dir / "temp_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"preview_{uuid.uuid4().hex}_{file.filename}"
    content = await file.read()
    temp_path.write_bytes(content)
    try:
        preview = inspect_file_for_preview(temp_path, file.filename)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return preview

@router.get("/datasets/{dataset_id}/grid_classification")
def get_grid_classification_endpoint(dataset_id: str):
    records = _get_records(dataset_id)
    settings_dict = get_settings()
    return calculate_grid_metrics(
        records,
        reserve_soc=settings_dict["reserve_soc"],
        inverter_power_kw=settings_dict["inverter_power_kw"],
        import_tariff=settings_dict["import_tariff"]
    )

class UpgradeSimulationRequest(BaseModel):
    add_battery_kwh: float = 5.0
    add_pv_kwp: float = 1.24
    new_reserve_soc: float = 20.0
    shift_load_kwh: float = 2.0

@router.post("/datasets/{dataset_id}/simulation_upgrade")
def simulate_upgrade_endpoint(dataset_id: str, payload: UpgradeSimulationRequest):
    records = _get_records(dataset_id)
    settings_dict = get_settings()
    return simulate_system_scenarios(
        records,
        baseline_battery_kwh=settings_dict["battery_capacity_kwh"],
        add_battery_kwh=payload.add_battery_kwh,
        baseline_pv_kwp=settings_dict["pv_capacity_kwp"],
        add_pv_kwp=payload.add_pv_kwp,
        new_reserve_soc=payload.new_reserve_soc,
        shift_load_kwh=payload.shift_load_kwh,
        tariff_rate=settings_dict["import_tariff"],
        inverter_rated_kw=settings_dict["inverter_power_kw"],
        inverter_max_current_a=settings_dict.get("inverter_max_battery_current_a", 135.0),
        bms_max_current_a=settings_dict.get("bms_max_charge_a", 100.0),
        battery_voltage=settings_dict.get("battery_voltage", 51.2)
    )

class AnalystQueryRequest(BaseModel):
    query_key: str
    query_text: Optional[str] = ""

@router.get("/analyst/presets")
def get_analyst_presets_endpoint():
    return get_preset_diagnostic_queries()

@router.post("/datasets/{dataset_id}/analyst/query")
def run_analyst_query_endpoint(dataset_id: str, payload: AnalystQueryRequest):
    records = _get_records(dataset_id)
    return analyze_energy_query(
        records,
        query_key=payload.query_key,
        query_text=payload.query_text or ""
    )

class AnalystStreamRequest(BaseModel):
    query_text: str

@router.post("/datasets/{dataset_id}/analyst/stream")
def stream_analyst_endpoint(dataset_id: str, payload: AnalystStreamRequest):
    records = _get_records(dataset_id)

    def event_generator():
        for chunk in stream_analyst_response(payload.query_text, records):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/analyst/performance")
def get_analyst_performance_endpoint():
    return get_performance_overview()

@router.get("/analyst/mcp/status")
def get_analyst_mcp_status_endpoint():
    return get_performance_overview()
