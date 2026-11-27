import uuid
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Body, Request, Response, Depends
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from backend.app.config import settings, is_hosted_mode
from backend.app.storage.db import get_connection, create_project_for_user, is_postgres
from backend.app.storage.file_store import (
    save_uploaded_file,
    save_dataset_file_record,
    resolve_dataset_path,
    extract_basename,
    delete_file,
)
from backend.app.storage.blob_sync import ensure_hydrated, persist_state
from backend.app.security.auth import (
    AuthContext,
    get_auth_context,
    get_optional_auth_state,
    register_user_account,
    authenticate_user_account,
    authenticate_demo_account,
    revoke_session,
    set_session_cookies,
    clear_session_cookies,
    list_user_projects,
    _extract_raw_token,
)
from backend.app.ingestion.excel_reader import list_excel_sheets, read_excel_sheet
from backend.app.ingestion.csv_reader import read_csv_file
from backend.app.ingestion.column_mapper import build_column_mapping_preview
from backend.app.ingestion.normalizer import normalize_dataset
from backend.app.ingestion.models import CommitMappingRequest, CanonicalRecord
from backend.app.ingestion.file_hasher import compute_file_hash
from backend.app.ingestion.conflict_detector import resolve_and_merge_records
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
from backend.app.finance.tariff_engine import TariffConfig
from backend.app.finance.cost_model import calculate_financial_performance
from backend.app.simulation.scenarios import simulate_system_scenarios
from backend.app.reporting.pdf_builder import build_pdf_report
from backend.app.reporting.excel_builder import build_excel_report
from backend.app.reporting.json_exporter import export_json_report
from backend.app.metrics.time_utils import format_datetime_12h, hour_index_to_12h
from backend.app.aggregation.historical import (
    calculate_daily_summaries,
    calculate_weekly_summaries,
    calculate_monthly_summaries,
    calculate_averages_comparison,
)
from backend.app.aggregation.hour_of_day import (
    calculate_hour_of_day_profiles,
    calculate_hour_date_heatmap,
)
from backend.app.aggregation.comparisons import (
    compare_periods,
    compare_weekdays_vs_weekends,
)
from backend.app.billing import (
    TEIRateSchedule,
    TEIBillingProfile,
    calculate_statement_of_account,
    get_active_rate_schedule,
    get_rate_schedule_for_month,
    activate_rate_schedule,
    set_project_active_schedule,
    save_rate_schedule,
    get_rate_history,
    check_official_tei_rates,
    get_rate_check_state,
    save_rate_check_state,
    get_billing_profile,
    save_billing_profile,
    forecast_tei_bill,
    calculate_billing_progress_series,
    simulate_rate_sensitivity,
    get_historical_bills_summary,
    insert_historical_bill,
    remove_historical_bill,
    upsert_monthly_estimate,
    sync_past_monthly_estimates,
    get_monthly_estimates,
    delete_monthly_estimate,
)
from backend.app.integrations.deye_cloud import DeyeCloudClient
from backend.app.integrations.deye_mcp import get_deye_mcp_client
from backend.app.integrations.weather import get_weather_intelligence
from backend.app.ingestion.multi_preview import inspect_file_for_preview
from backend.app.analyst.analyst_service import (
    analyze_energy_query,
    get_preset_diagnostic_queries,
    stream_analyst_response,
    get_performance_overview,
)

router = APIRouter()

dataset_cache: Dict[str, List[CanonicalRecord]] = {}
_historical_records_cache: Dict[str, List[CanonicalRecord]] = {}
_summary_cache: Dict[str, Any] = {}
_daily_summaries_cache: Dict[str, Any] = {}
_timeline_cache: Dict[str, Any] = {}
_metrics_cache: Dict[str, Any] = {}
_settings_cache: Dict[str, Dict[str, Any]] = {}
_past_estimates_sync_key: Dict[str, str] = {}

def invalidate_all_caches(project_id: Optional[str] = None):
    if project_id is None:
        dataset_cache.clear()
        _historical_records_cache.clear()
        _summary_cache.clear()
        _daily_summaries_cache.clear()
        _timeline_cache.clear()
        _metrics_cache.clear()
        _settings_cache.clear()
        _past_estimates_sync_key.clear()
        return

    _historical_records_cache.pop(project_id, None)
    _settings_cache.pop(project_id, None)
    _past_estimates_sync_key.pop(project_id, None)
    prefix = f"{project_id}:"
    for store in (dataset_cache, _summary_cache, _daily_summaries_cache, _timeline_cache, _metrics_cache):
        for k in [key for key in list(store.keys()) if key.startswith(prefix)]:
            store.pop(k, None)

def _hydrate_state(force: bool = False) -> bool:
    if is_postgres():
        return False
    updated = ensure_hydrated(force=force)
    if updated:
        from backend.app.storage.db import init_db
        init_db(hydrate=False)
        invalidate_all_caches()
    return updated

def _persist_state(
    upload_files: Optional[List[Path]] = None,
    deleted_filenames: Optional[List[str]] = None,
) -> bool:
    return persist_state(upload_files=upload_files, deleted_filenames=deleted_filenames)

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""
    installation_name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    installation_type: str = "residential"

class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    installation_type: Optional[str] = None

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
    generation_vat: float = 0.0
    distribution_charge: float = 0.0
    transmission_charge: float = 0.0
    system_loss_charge: float = 0.0

class SystemSettingsModel(BaseModel):
    station_name: str = ""
    location_name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    pv_capacity_kwp: float = 0.0
    num_modules: int = 0
    module_wattage: float = 0.0
    panel_model: str = ""
    panel_tech: str = ""
    inverter_model: str = ""
    inverter_power_kw: float = 0.0
    inverter_serial: str = ""
    inverter_max_apparent_va: float = 0.0
    inverter_max_battery_current_a: float = 0.0
    mppt_voltage_min_v: float = 0.0
    mppt_voltage_max_v: float = 0.0
    pv_voltage_max_v: float = 0.0
    mppt_max_current_a: float = 0.0
    logger_serial: str = ""
    logger_firmware: str = ""
    logger_interval_min: int = 5
    battery_model: str = ""
    battery_chemistry: str = "LFP"
    battery_voltage: float = 0.0
    battery_ah: float = 0.0
    battery_capacity_kwh: float = 0.0
    usable_capacity_kwh: float = 0.0
    reserve_soc: float = 20.0
    bms_max_charge_a: float = 0.0
    bms_max_discharge_a: float = 0.0
    max_charge_kw: float = 0.0
    max_discharge_kw: float = 0.0
    battery_efficiency: float = 0.95
    import_tariff: float = 0.0
    export_tariff: float = 0.0
    currency: str = "PHP"
    timezone: str = "Asia/Manila"

class ScenarioRequest(BaseModel):
    add_battery_kwh: float = 0.0
    add_pv_kwp: float = 0.0
    new_reserve_soc: float = 20.0
    shift_load_kwh: float = 0.0

class ReportGenRequest(BaseModel):
    report_type: str = "pdf"

class UpdateSourceModel(BaseModel):
    is_included: Optional[bool] = None
    sheet_name: Optional[str] = None

class DeyeConfigPayload(BaseModel):
    station_id: Optional[str] = ""
    data_center: Optional[str] = "eu"
    app_id: Optional[str] = ""
    app_secret: Optional[str] = ""
    username: Optional[str] = ""
    password: Optional[str] = ""
    auto_sync: Optional[bool] = False
    sync_interval_min: Optional[int] = 5
    reconciliation_policy: Optional[str] = "MERGE"

class DeyeSyncRangePayload(BaseModel):
    start_date: str
    end_date: str
    credentials: Optional[DeyeConfigPayload] = None

class UpgradeSimulationRequest(BaseModel):
    add_battery_kwh: float = 0.0
    add_pv_kwp: float = 0.0
    new_reserve_soc: float = 20.0
    shift_load_kwh: float = 0.0

class AnalystQueryRequest(BaseModel):
    query_key: str
    query_text: Optional[str] = ""

class AnalystStreamRequest(BaseModel):
    query_text: str

@router.get("/health")
def get_health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "timezone": settings.default_timezone,
        "currency": settings.default_currency,
        "time_format": "12-hour",
        "hosted_mode": is_hosted_mode(),
        "database_engine": "postgresql" if is_postgres() else "sqlite"
    }

@router.get("/auth/me")
def get_auth_status(request: Request, response: Response):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    hosted = is_hosted_mode()
    ctx = get_optional_auth_state(request)
    if ctx is None:
        return {
            "authenticated": False,
            "auth_required": hosted,
            "hosted_mode": hosted,
            "user": None,
            "projects": [],
            "active_project_id": None,
            "csrf_token": ""
        }
    projects = list_user_projects(ctx.user_id)
    return {
        "authenticated": True,
        "auth_required": hosted,
        "hosted_mode": hosted,
        "is_local_mode": ctx.is_local_fallback,
        "user": {
            "id": ctx.user_id,
            "email": ctx.email,
            "display_name": ctx.display_name,
            "role": ctx.role,
        },
        "projects": projects,
        "active_project_id": ctx.project_id,
        "csrf_token": ctx.csrf_token,
    }

@router.post("/auth/register")
def register_endpoint(payload: RegisterRequest, request: Request, response: Response):
    _hydrate_state(force=True)
    response.headers["Cache-Control"] = "no-store"
    res = register_user_account(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        installation_name=payload.installation_name,
    )
    set_session_cookies(response, res["raw_token"], res["csrf_token"], request=request)
    _persist_state()
    return {
        "authenticated": True,
        "user": res["user"],
        "projects": res["projects"],
        "active_project_id": res["active_project_id"],
        "csrf_token": res["csrf_token"],
        "session_token": res["raw_token"],
    }

@router.post("/auth/login")
def login_endpoint(payload: LoginRequest, request: Request, response: Response):
    _hydrate_state(force=True)
    response.headers["Cache-Control"] = "no-store"
    ua = request.headers.get("User-Agent", "")
    res = authenticate_user_account(payload.email, payload.password, user_agent=ua)
    set_session_cookies(response, res["raw_token"], res["csrf_token"], request=request)
    _persist_state()
    return {
        "authenticated": True,
        "user": res["user"],
        "projects": res["projects"],
        "active_project_id": res["active_project_id"],
        "csrf_token": res["csrf_token"],
        "session_token": res["raw_token"],
    }

@router.post("/auth/demo")
def demo_login_endpoint(request: Request, response: Response):
    _hydrate_state(force=True)
    response.headers["Cache-Control"] = "no-store"
    ua = request.headers.get("User-Agent", "")
    res = authenticate_demo_account(user_agent=ua)
    set_session_cookies(response, res["raw_token"], res["csrf_token"], request=request)
    _persist_state()
    return {
        "authenticated": True,
        "user": res["user"],
        "projects": res["projects"],
        "active_project_id": res["active_project_id"],
        "csrf_token": res["csrf_token"],
        "session_token": res["raw_token"],
    }

@router.post("/auth/logout")
def logout_endpoint(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    raw_token = _extract_raw_token(request)
    revoke_session(raw_token)
    clear_session_cookies(response)
    _persist_state()
    return {"status": "logged_out"}

@router.get("/projects")
def list_projects_endpoint(response: Response, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    return {
        "active_project_id": auth.project_id,
        "projects": list_user_projects(auth.user_id),
    }

@router.post("/projects")
def create_project_endpoint(payload: CreateProjectRequest, response: Response, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    response.headers["Cache-Control"] = "no-store"
    proj = create_project_for_user(
        user_id=auth.user_id,
        name=payload.name,
        description=payload.description,
        installation_type=payload.installation_type,
        is_default=False,
    )
    _persist_state()
    return {"status": "created", "project": proj}

@router.patch("/projects/{target_project_id}")
def update_project_endpoint(
    target_project_id: str,
    payload: UpdateProjectRequest,
    response: Response,
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state(force=True)
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM projects WHERE id = ? AND owner_user_id = ?",
        (target_project_id, auth.user_id)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Installation not found.")
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_name = payload.name.strip() if payload.name is not None else row["name"]
    new_desc = payload.description if payload.description is not None else (row["description"] or "")
    new_type = payload.installation_type if payload.installation_type is not None else (row["installation_type"] or "residential")
    conn.execute(
        "UPDATE projects SET name = ?, description = ?, installation_type = ?, updated_at = ? WHERE id = ? AND owner_user_id = ?",
        (new_name or row["name"], new_desc, new_type, now_iso, target_project_id, auth.user_id)
    )
    conn.commit()
    updated = dict(conn.execute("SELECT * FROM projects WHERE id = ?", (target_project_id,)).fetchone())
    conn.close()
    _persist_state()
    return {"status": "updated", "project": updated}

@router.delete("/projects/{target_project_id}")
def delete_project_endpoint(
    target_project_id: str,
    response: Response,
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state(force=True)
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    owned = conn.execute(
        "SELECT id FROM projects WHERE owner_user_id = ?",
        (auth.user_id,)
    ).fetchall()
    if len(owned) <= 1:
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot delete your only solar installation.")
    row = conn.execute(
        "SELECT id FROM projects WHERE id = ? AND owner_user_id = ?",
        (target_project_id, auth.user_id)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Installation not found.")
    ds_rows = conn.execute("SELECT filepath FROM datasets WHERE project_id = ?", (target_project_id,)).fetchall()
    deleted_names = []
    for ds in ds_rows:
        if ds["filepath"]:
            bname = extract_basename(ds["filepath"])
            if bname:
                deleted_names.append(bname)
            delete_file(ds["filepath"], remove_remote=False)
    conn.execute("DELETE FROM projects WHERE id = ? AND owner_user_id = ?", (target_project_id, auth.user_id))
    conn.commit()
    conn.close()
    invalidate_all_caches(target_project_id)
    _persist_state(deleted_filenames=deleted_names or None)
    return {"status": "deleted", "project_id": target_project_id}

def get_settings(project_id: str = "default") -> Dict[str, Any]:
    if _hydrate_state() or project_id not in _settings_cache:
        conn = get_connection()
        row = conn.execute("SELECT * FROM system_settings WHERE project_id = ?", (project_id,)).fetchone()
        conn.close()
        _settings_cache[project_id] = dict(row) if row else SystemSettingsModel().model_dump()
    return _settings_cache[project_id]

def _resolve_effective_import_tariff(settings_dict: Dict[str, Any], project_id: str = "default") -> float:
    configured = float(settings_dict.get("import_tariff") or 0.0)
    if configured > 0.0:
        return configured
    try:
        conn = get_connection()
        profile = get_billing_profile(conn, project_id=project_id)
        sched = get_active_rate_schedule(conn, customer_class=profile.customer_class, project_id=project_id)
        conn.close()
        if any(c.component_id == "gen_charge" and c.rate_per_kwh > 0 for c in sched.components):
            soa = calculate_statement_of_account(
                billed_kwh=200.0,
                schedule=sched,
                profile=profile,
                billing_start=profile.cycle_start_date or "2026-01-01",
                billing_end=profile.cycle_end_date or "2026-02-01",
                is_estimate=True
            )
            if soa.effective_average_rate_per_kwh > 0:
                return float(soa.effective_average_rate_per_kwh)
    except Exception:
        pass
    return 0.0

@router.get("/settings")
def get_settings_endpoint(response: Response, auth: AuthContext = Depends(get_auth_context)):
    response.headers["Cache-Control"] = "no-store"
    return get_settings(auth.project_id)

@router.put("/settings")
def update_settings(payload: SystemSettingsModel, response: Response, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    response.headers["Cache-Control"] = "no-store"
    pid = auth.project_id
    conn = get_connection()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = conn.execute(
        """UPDATE system_settings SET
            station_name = ?, location_name = ?, latitude = ?, longitude = ?,
            pv_capacity_kwp = ?, num_modules = ?, module_wattage = ?, panel_model = ?, panel_tech = ?,
            inverter_model = ?, inverter_power_kw = ?, inverter_serial = ?,
            inverter_max_apparent_va = ?, inverter_max_battery_current_a = ?,
            mppt_voltage_min_v = ?, mppt_voltage_max_v = ?, pv_voltage_max_v = ?, mppt_max_current_a = ?,
            logger_serial = ?, logger_firmware = ?, logger_interval_min = ?,
            battery_model = ?, battery_chemistry = ?, battery_voltage = ?, battery_ah = ?,
            battery_capacity_kwh = ?, usable_capacity_kwh = ?, reserve_soc = ?,
            bms_max_charge_a = ?, bms_max_discharge_a = ?, max_charge_kw = ?, max_discharge_kw = ?,
            battery_efficiency = ?, import_tariff = ?, export_tariff = ?, currency = ?,
            timezone = ?, updated_at = ?
        WHERE project_id = ?""",
        (
            payload.station_name, payload.location_name, payload.latitude, payload.longitude,
            payload.pv_capacity_kwp, payload.num_modules, payload.module_wattage, payload.panel_model, payload.panel_tech,
            payload.inverter_model, payload.inverter_power_kw, payload.inverter_serial,
            payload.inverter_max_apparent_va, payload.inverter_max_battery_current_a,
            payload.mppt_voltage_min_v, payload.mppt_voltage_max_v, payload.pv_voltage_max_v, payload.mppt_max_current_a,
            payload.logger_serial, payload.logger_firmware, payload.logger_interval_min,
            payload.battery_model, payload.battery_chemistry, payload.battery_voltage, payload.battery_ah,
            payload.battery_capacity_kwh, payload.usable_capacity_kwh, payload.reserve_soc,
            payload.bms_max_charge_a, payload.bms_max_discharge_a, payload.max_charge_kw, payload.max_discharge_kw,
            payload.battery_efficiency, payload.import_tariff, payload.export_tariff, payload.currency,
            payload.timezone, now, pid
        )
    )
    if cur.rowcount == 0:
        conn.execute(
            """INSERT INTO system_settings (
                id, project_id, station_name, location_name, latitude, longitude,
                pv_capacity_kwp, num_modules, module_wattage, panel_model, panel_tech,
                inverter_model, inverter_power_kw, inverter_serial, inverter_max_apparent_va, inverter_max_battery_current_a,
                mppt_voltage_min_v, mppt_voltage_max_v, pv_voltage_max_v, mppt_max_current_a,
                logger_serial, logger_firmware, logger_interval_min,
                battery_model, battery_chemistry, battery_voltage, battery_ah, battery_capacity_kwh,
                usable_capacity_kwh, reserve_soc, bms_max_charge_a, bms_max_discharge_a,
                max_charge_kw, max_discharge_kw, battery_efficiency, import_tariff, export_tariff,
                currency, timezone, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"settings-{pid}", pid,
                payload.station_name, payload.location_name, payload.latitude, payload.longitude,
                payload.pv_capacity_kwp, payload.num_modules, payload.module_wattage, payload.panel_model, payload.panel_tech,
                payload.inverter_model, payload.inverter_power_kw, payload.inverter_serial,
                payload.inverter_max_apparent_va, payload.inverter_max_battery_current_a,
                payload.mppt_voltage_min_v, payload.mppt_voltage_max_v, payload.pv_voltage_max_v, payload.mppt_max_current_a,
                payload.logger_serial, payload.logger_firmware, payload.logger_interval_min,
                payload.battery_model, payload.battery_chemistry, payload.battery_voltage, payload.battery_ah,
                payload.battery_capacity_kwh, payload.usable_capacity_kwh, payload.reserve_soc,
                payload.bms_max_charge_a, payload.bms_max_discharge_a, payload.max_charge_kw, payload.max_discharge_kw,
                payload.battery_efficiency, payload.import_tariff, payload.export_tariff, payload.currency,
                payload.timezone, now
            )
        )
    conn.execute("DELETE FROM analyst_cache WHERE project_id = ?", (pid,))
    conn.commit()
    conn.close()
    invalidate_all_caches(pid)
    try:
        get_deye_mcp_client(pid).invalidate_cache(clear_last_real=False)
    except Exception:
        pass
    _persist_state()
    return {"status": "updated", "settings": get_settings(pid)}

@router.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...), auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    pid = auth.project_id
    filename = file.filename or "upload.xlsx"
    contents = await file.read()

    file_hash = compute_file_hash(contents)
    file_format = "CSV" if filename.lower().endswith(".csv") else ("XLSM" if filename.lower().endswith(".xlsm") else "XLSX")

    conn = get_connection()
    existing_rows = conn.execute(
        "SELECT id, filepath FROM datasets WHERE project_id = ? AND (file_hash = ? OR filename = ?)",
        (pid, file_hash, filename)
    ).fetchall()
    is_duplicate = len(existing_rows) > 0
    duplicate_of = existing_rows[0]["id"] if is_duplicate else None
    deleted_names: List[str] = []

    for row in existing_rows:
        if row["filepath"]:
            old_name = extract_basename(row["filepath"])
            if old_name:
                deleted_names.append(old_name)
            delete_file(row["filepath"], remove_remote=False)
        conn.execute("DELETE FROM dataset_files WHERE dataset_id = ?", (row["id"],))
        conn.execute("DELETE FROM column_mappings WHERE dataset_id = ?", (row["id"],))
        conn.execute("DELETE FROM datasets WHERE id = ? AND project_id = ?", (row["id"], pid))
        dataset_cache.pop(f"{pid}:{row['id']}", None)

    file_id, target_path = save_uploaded_file(filename, contents, project_id=pid)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    sheets: List[str] = []
    if filename.lower().endswith((".xlsx", ".xlsm")):
        sheets = list_excel_sheets(target_path)

    conn.execute(
        """INSERT INTO datasets (id, project_id, filename, file_hash, file_format, filepath, sheet_name, is_active, is_included, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?)""",
        (file_id, pid, filename, file_hash, file_format, str(target_path), sheets[0] if sheets else None, now)
    )
    save_dataset_file_record(conn, file_id, pid, filename, contents)
    conn.commit()
    conn.close()
    invalidate_all_caches(pid)
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

def _auto_commit_dataset_core(dataset_id: str, conn: Any, project_id: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM datasets WHERE id = ? AND project_id = ?",
        (dataset_id, project_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Dataset not found")

    filepath = resolve_dataset_path(row["filepath"], dataset_id=dataset_id)
    filename = row["filename"]
    if not filepath or not filepath.exists():
        raise HTTPException(status_code=404, detail="Dataset file not found on disk.")

    if filename.lower().endswith((".xlsx", ".xlsm")):
        sheets = list_excel_sheets(filepath)
        sel_sheet = row["sheet_name"] or (sheets[0] if sheets else None)
        headers, sample_records, _ = read_excel_sheet(filepath, sheet_name=sel_sheet, max_rows=100)
    else:
        sel_sheet = "CSV"
        headers, sample_records, _ = read_csv_file(filepath, max_rows=100)

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
        _, all_records, _ = read_excel_sheet(filepath, sheet_name=sel_sheet)
    else:
        _, all_records, _ = read_csv_file(filepath)

    tz_name = get_settings(project_id).get("timezone", "Asia/Manila")
    canonical_records = normalize_dataset(all_records, mappings, sign_conventions, timezone=tz_name)
    dataset_cache[f"{project_id}:{dataset_id}"] = canonical_records

    quality_rep = calculate_data_quality_report(canonical_records)
    quality_score = quality_rep["quality_score"]
    sampling_med = float((quality_rep.get("sampling_audit") or {}).get("median_interval_minutes") or 5.0)
    gap_cnt = len((quality_rep.get("sampling_audit") or {}).get("gaps") or [])

    valid_recs = [r for r in canonical_records if r.timestamp_valid]
    start_time = valid_recs[0].timestamp if valid_recs else (canonical_records[0].timestamp if canonical_records else None)
    end_time = valid_recs[-1].timestamp if valid_recs else (canonical_records[-1].timestamp if canonical_records else None)

    mapping_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO column_mappings (id, dataset_id, raw_headers_json, mapping_json, sign_conventions_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(dataset_id) DO UPDATE SET
               raw_headers_json = excluded.raw_headers_json,
               mapping_json = excluded.mapping_json,
               sign_conventions_json = excluded.sign_conventions_json,
               created_at = excluded.created_at""",
        (mapping_id, dataset_id, json.dumps(headers), json.dumps(mappings), json.dumps(sign_conventions), now)
    )
    conn.execute(
        """UPDATE datasets SET total_rows = ?, start_time = ?, end_time = ?, quality_score = ?, sampling_interval_median_min = ?, gap_count = ?, sheet_name = ?, is_included = 1
           WHERE id = ? AND project_id = ?""",
        (len(canonical_records), start_time, end_time, quality_score, sampling_med, gap_cnt, sel_sheet, dataset_id, project_id)
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
def auto_commit_single_dataset(dataset_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    pid = auth.project_id
    conn = get_connection()
    try:
        res = _auto_commit_dataset_core(dataset_id, conn, pid)
        conn.commit()
        invalidate_all_caches(pid)
        _persist_state()
        return res
    finally:
        conn.close()

@router.post("/datasets/auto_commit_all")
def auto_commit_all_datasets(auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    pid = auth.project_id
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, filename FROM datasets WHERE project_id = ? AND (total_rows = 0 OR total_rows IS NULL OR start_time IS NULL)",
        (pid,)
    ).fetchall()
    results = []
    for r in rows:
        try:
            res = _auto_commit_dataset_core(r["id"], conn, pid)
            results.append(res)
        except Exception as e:
            results.append({"status": "error", "dataset_id": r["id"], "filename": r["filename"], "error": str(e)})
    conn.commit()
    conn.close()
    invalidate_all_caches(pid)
    if results:
        _persist_state()
    return {"total_processed": len(results), "committed": results}

@router.post("/datasets/upload_batch")
async def upload_datasets_batch(files: List[UploadFile] = File(...), auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    pid = auth.project_id
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

        existing_rows = conn.execute(
            "SELECT id, filepath FROM datasets WHERE project_id = ? AND (file_hash = ? OR filename = ?)",
            (pid, file_hash, filename)
        ).fetchall()
        for row in existing_rows:
            if row["filepath"]:
                old_name = extract_basename(row["filepath"])
                if old_name:
                    deleted_names.append(old_name)
                delete_file(row["filepath"], remove_remote=False)
            conn.execute("DELETE FROM dataset_files WHERE dataset_id = ?", (row["id"],))
            conn.execute("DELETE FROM column_mappings WHERE dataset_id = ?", (row["id"],))
            conn.execute("DELETE FROM datasets WHERE id = ? AND project_id = ?", (row["id"], pid))
            dataset_cache.pop(f"{pid}:{row['id']}", None)

        file_id, target_path = save_uploaded_file(filename, contents, project_id=pid)
        uploaded_paths.append(target_path)
        sheets: List[str] = []
        if filename.lower().endswith((".xlsx", ".xlsm")):
            sheets = list_excel_sheets(target_path)

        conn.execute(
            """INSERT INTO datasets (id, project_id, filename, file_hash, file_format, filepath, sheet_name, is_active, is_included, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?)""",
            (file_id, pid, filename, file_hash, file_format, str(target_path), sheets[0] if sheets else None, now)
        )
        save_dataset_file_record(conn, file_id, pid, filename, contents)

        try:
            commit_info = _auto_commit_dataset_core(file_id, conn, pid)
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
    invalidate_all_caches(pid)
    uploaded_basenames = {p.name for p in uploaded_paths}
    filtered_deleted = [n for n in deleted_names if n not in uploaded_basenames]
    _persist_state(upload_files=uploaded_paths or None, deleted_filenames=filtered_deleted or None)
    return {"total_uploaded": len(results), "files": results}

@router.get("/sources")
def list_sources(response: Response, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM datasets WHERE project_id = ? ORDER BY COALESCE(start_time, created_at) ASC, filename ASC",
        (auth.project_id,)
    ).fetchall()
    conn.close()

    items = []
    for r in rows:
        d = dict(r)
        d["start_time_12h"] = format_datetime_12h(d.get("start_time"))
        d["end_time_12h"] = format_datetime_12h(d.get("end_time"))
        items.append(d)
    return items

@router.patch("/sources/{source_id}")
def update_source(source_id: str, payload: UpdateSourceModel, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    pid = auth.project_id
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ? AND project_id = ?", (source_id, pid)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Source dataset not found")

    if payload.is_included is not None:
        val = 1 if payload.is_included else 0
        conn.execute("UPDATE datasets SET is_included = ? WHERE id = ? AND project_id = ?", (val, source_id, pid))
    if payload.sheet_name is not None:
        conn.execute("UPDATE datasets SET sheet_name = ? WHERE id = ? AND project_id = ?", (payload.sheet_name, source_id, pid))

    conn.commit()
    conn.close()
    invalidate_all_caches(pid)
    _persist_state()
    return {"status": "updated", "source_id": source_id}

@router.delete("/sources/{source_id}")
def delete_source(source_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    pid = auth.project_id
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ? AND project_id = ?", (source_id, pid)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Source dataset not found")

    deleted_name = extract_basename(row["filepath"]) if row["filepath"] else ""
    delete_file(row["filepath"], remove_remote=False)

    conn.execute("DELETE FROM dataset_files WHERE dataset_id = ?", (source_id,))
    conn.execute("DELETE FROM column_mappings WHERE dataset_id = ?", (source_id,))
    conn.execute("DELETE FROM datasets WHERE id = ? AND project_id = ?", (source_id, pid))
    conn.commit()
    conn.close()
    dataset_cache.pop(f"{pid}:{source_id}", None)
    invalidate_all_caches(pid)
    _persist_state(deleted_filenames=[deleted_name] if deleted_name else None)
    return {"status": "deleted", "source_id": source_id}

@router.get("/datasets/{dataset_id}/preview")
def preview_dataset(dataset_id: str, sheet_name: Optional[str] = None, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ? AND project_id = ?", (dataset_id, pid)).fetchone()
    if not row and dataset_id in ["all", "historical"]:
        row = conn.execute(
            "SELECT * FROM datasets WHERE project_id = ? AND is_included = 1 ORDER BY start_time DESC LIMIT 1",
            (pid,)
        ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT * FROM datasets WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (pid,)
        ).fetchone()
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

    filepath = resolve_dataset_path(row["filepath"], dataset_id=row["id"])
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
def commit_dataset_mapping(dataset_id: str, payload: CommitMappingRequest, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    pid = auth.project_id
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ? AND project_id = ?", (dataset_id, pid)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Dataset not found")

    filepath = resolve_dataset_path(row["filepath"], dataset_id=dataset_id)
    filename = row["filename"]
    if not filepath or not filepath.exists():
        conn.close()
        raise HTTPException(status_code=404, detail="Dataset file not found on disk.")

    if filename.lower().endswith((".xlsx", ".xlsm")):
        headers, all_records, total_count = read_excel_sheet(filepath, sheet_name=payload.selected_sheet)
    else:
        headers, all_records, total_count = read_csv_file(filepath)

    tz_name = payload.timezone or get_settings(pid).get("timezone", "Asia/Manila")
    canonical_records = normalize_dataset(all_records, payload.mappings, payload.sign_conventions, timezone=tz_name)
    dataset_cache[f"{pid}:{dataset_id}"] = canonical_records

    quality_rep = calculate_data_quality_report(canonical_records)
    quality_score = quality_rep["quality_score"]
    sampling_med = float((quality_rep.get("sampling_audit") or {}).get("median_interval_minutes") or 5.0)
    gap_cnt = len((quality_rep.get("sampling_audit") or {}).get("gaps") or [])

    valid_recs = [r for r in canonical_records if r.timestamp_valid]
    start_time = valid_recs[0].timestamp if valid_recs else (canonical_records[0].timestamp if canonical_records else None)
    end_time = valid_recs[-1].timestamp if valid_recs else (canonical_records[-1].timestamp if canonical_records else None)

    mapping_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO column_mappings (id, dataset_id, raw_headers_json, mapping_json, sign_conventions_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(dataset_id) DO UPDATE SET
               raw_headers_json = excluded.raw_headers_json,
               mapping_json = excluded.mapping_json,
               sign_conventions_json = excluded.sign_conventions_json,
               created_at = excluded.created_at""",
        (mapping_id, dataset_id, json.dumps(headers), json.dumps(payload.mappings), json.dumps(payload.sign_conventions), now)
    )
    conn.execute(
        """UPDATE datasets SET total_rows = ?, start_time = ?, end_time = ?, quality_score = ?, sampling_interval_median_min = ?, gap_count = ?, sheet_name = ?, is_included = 1
           WHERE id = ? AND project_id = ?""",
        (total_count, start_time, end_time, quality_score, sampling_med, gap_cnt, payload.selected_sheet, dataset_id, pid)
    )
    conn.commit()
    conn.close()
    invalidate_all_caches(pid)
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

def _get_records(dataset_id: str, project_id: str = "default") -> List[CanonicalRecord]:
    _hydrate_state()
    if dataset_id in ["all", "historical"]:
        return _get_historical_records(project_id)

    cache_key = f"{project_id}:{dataset_id}"
    if cache_key in dataset_cache:
        return dataset_cache[cache_key]

    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id = ? AND project_id = ?", (dataset_id, project_id)).fetchone()
    mapping_row = conn.execute("SELECT * FROM column_mappings WHERE dataset_id = ?", (dataset_id,)).fetchone() if row else None
    conn.close()

    if not row:
        return _get_historical_records(project_id)

    filepath = resolve_dataset_path(row["filepath"], dataset_id=dataset_id)
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

    tz_name = get_settings(project_id).get("timezone", "Asia/Manila")
    records = normalize_dataset(all_records, mappings, sign_conventions, timezone=tz_name)
    dataset_cache[cache_key] = records
    return records

def _get_historical_records(project_id: str = "default") -> List[CanonicalRecord]:
    _hydrate_state()
    if project_id in _historical_records_cache:
        return _historical_records_cache[project_id]

    conn = get_connection()
    rows = conn.execute(
        "SELECT id FROM datasets WHERE project_id = ? AND is_included = 1 ORDER BY start_time ASC",
        (project_id,)
    ).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT id FROM datasets WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,)
        ).fetchall()
    conn.close()

    if not rows:
        return []

    merged: List[CanonicalRecord] = []
    for r in rows:
        d_id = r["id"]
        try:
            recs = _get_records(d_id, project_id=project_id)
            merged = resolve_and_merge_records(merged, recs, policy="KEEP_EXISTING")
        except Exception:
            continue
    _historical_records_cache[project_id] = merged
    return merged

@router.get("/datasets/{dataset_id}/summary")
def get_executive_summary(dataset_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    cache_key = f"{pid}:{dataset_id}"
    if cache_key in _summary_cache:
        return _summary_cache[cache_key]
    records = _get_records(dataset_id, project_id=pid)
    settings_dict = get_settings(pid)

    solar = calculate_solar_metrics(
        records,
        pv_capacity_kwp=settings_dict.get("pv_capacity_kwp", 0.0),
        inverter_rating_kw=settings_dict.get("inverter_power_kw", 0.0)
    )
    consumption = calculate_consumption_metrics(records)
    battery = calculate_battery_metrics(
        records,
        nominal_capacity_kwh=settings_dict.get("battery_capacity_kwh", 0.0),
        reserve_soc=settings_dict.get("reserve_soc", 20.0),
        bms_max_current_a=settings_dict.get("bms_max_charge_a", 0.0),
        battery_voltage=settings_dict.get("battery_voltage", 0.0)
    )
    grid = calculate_grid_metrics(
        records,
        reserve_soc=settings_dict.get("reserve_soc", 20.0),
        inverter_power_kw=settings_dict.get("inverter_power_kw", 0.0),
        import_tariff=_resolve_effective_import_tariff(settings_dict, project_id=pid)
    )
    balance = reconcile_energy_balance(
        records,
        inverter_efficiency=settings_dict.get("battery_efficiency", 0.95),
        nominal_battery_kwh=settings_dict.get("battery_capacity_kwh", 0.0)
    )
    quality = calculate_data_quality_report(records)

    tariff_conf = TariffConfig(
        flat_rate=settings_dict.get("import_tariff", 0.0),
        export_rate=settings_dict.get("export_tariff", 0.0),
        currency=settings_dict.get("currency", "PHP")
    )
    finance = calculate_financial_performance(records, tariff_conf)

    valid_recs = [r for r in records if r.timestamp_valid]
    start_t = valid_recs[0].timestamp if valid_recs else ""
    end_t = valid_recs[-1].timestamp if valid_recs else ""

    result = {
        "dataset_id": dataset_id,
        "date_range": f"{start_t[:10]} to {end_t[:10]}" if valid_recs else "",
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
    _summary_cache[cache_key] = result
    return result

@router.get("/datasets/{dataset_id}/timeline")
def get_timeline_data(dataset_id: str, date: Optional[str] = Query(None), auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    cache_key = f"{pid}:{dataset_id}_{date or ''}"
    if cache_key in _timeline_cache:
        return _timeline_cache[cache_key]
    records = [r for r in _get_records(dataset_id, project_id=pid) if r.timestamp_valid]
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
    slot_candidates: Dict[int, tuple] = {}
    for r in records:
        if not r.timestamp.startswith(target_date_clean):
            continue
        sep = "T" if "T" in r.timestamp else " "
        time_part = r.timestamp.split(sep, 1)[1] if sep in r.timestamp else r.timestamp
        hms = time_part[:8].split(":")
        if len(hms) < 2:
            continue
        try:
            hh = int(hms[0])
            mm = int(hms[1])
            ss = int(hms[2][:2]) if len(hms) >= 3 else 0
        except ValueError:
            continue
        secs = hh * 3600 + mm * 60 + ss
        slot_idx = min(288, max(0, (secs + 150) // 300))
        dist = abs(secs - slot_idx * 300)
        prev = slot_candidates.get(slot_idx)
        if prev is None or dist < prev[0]:
            slot_candidates[slot_idx] = (dist, r)

    slots_24h = [f"{h:02d}:{m:02d}" for h in range(24) for m in range(0, 60, 5)] + ["24:00"]
    timestamps_full = [f"{target_date_clean} {s}:00" if s != "24:00" else f"{target_date_clean} 23:59:59" for s in slots_24h]
    timestamps_12h = [format_datetime_12h(ts) for ts in timestamps_full]

    pv_kw = []
    load_kw = []
    grid_kw = []
    battery_kw = []
    soc_pct = []
    residual_kw = []

    for idx in range(len(slots_24h)):
        entry = slot_candidates.get(idx)
        if entry is not None:
            rec = entry[1]
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
def get_solar_analysis(dataset_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    sum_key = f"{pid}:{dataset_id}"
    if sum_key in _summary_cache:
        return _summary_cache[sum_key]["solar"]
    key = f"{pid}:solar:{dataset_id}"
    if key in _metrics_cache:
        return _metrics_cache[key]
    records = _get_records(dataset_id, project_id=pid)
    settings_dict = get_settings(pid)
    res = calculate_solar_metrics(
        records,
        pv_capacity_kwp=settings_dict.get("pv_capacity_kwp", 0.0),
        inverter_rating_kw=settings_dict.get("inverter_power_kw", 0.0)
    )
    _metrics_cache[key] = res
    return res

@router.get("/datasets/{dataset_id}/consumption")
def get_consumption_analysis(dataset_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    sum_key = f"{pid}:{dataset_id}"
    if sum_key in _summary_cache:
        return _summary_cache[sum_key]["consumption"]
    key = f"{pid}:consumption:{dataset_id}"
    if key in _metrics_cache:
        return _metrics_cache[key]
    records = _get_records(dataset_id, project_id=pid)
    res = calculate_consumption_metrics(records)
    _metrics_cache[key] = res
    return res

@router.get("/datasets/{dataset_id}/battery")
def get_battery_analysis(dataset_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    sum_key = f"{pid}:{dataset_id}"
    if sum_key in _summary_cache:
        return _summary_cache[sum_key]["battery"]
    key = f"{pid}:battery:{dataset_id}"
    if key in _metrics_cache:
        return _metrics_cache[key]
    records = _get_records(dataset_id, project_id=pid)
    settings_dict = get_settings(pid)
    res = calculate_battery_metrics(
        records,
        nominal_capacity_kwh=settings_dict.get("battery_capacity_kwh", 0.0),
        reserve_soc=settings_dict.get("reserve_soc", 20.0),
        bms_max_current_a=settings_dict.get("bms_max_charge_a", 0.0),
        battery_voltage=settings_dict.get("battery_voltage", 0.0)
    )
    _metrics_cache[key] = res
    return res

@router.get("/datasets/{dataset_id}/grid")
def get_grid_analysis(dataset_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    sum_key = f"{pid}:{dataset_id}"
    if sum_key in _summary_cache:
        return _summary_cache[sum_key]["grid"]
    key = f"{pid}:grid:{dataset_id}"
    if key in _metrics_cache:
        return _metrics_cache[key]
    records = _get_records(dataset_id, project_id=pid)
    settings_dict = get_settings(pid)
    res = calculate_grid_metrics(
        records,
        reserve_soc=settings_dict.get("reserve_soc", 20.0),
        inverter_power_kw=settings_dict.get("inverter_power_kw", 0.0),
        import_tariff=_resolve_effective_import_tariff(settings_dict, project_id=pid)
    )
    _metrics_cache[key] = res
    return res

@router.get("/datasets/{dataset_id}/balance")
def get_balance_analysis(dataset_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    sum_key = f"{pid}:{dataset_id}"
    if sum_key in _summary_cache:
        return _summary_cache[sum_key]["balance"]
    key = f"{pid}:balance:{dataset_id}"
    if key in _metrics_cache:
        return _metrics_cache[key]
    records = _get_records(dataset_id, project_id=pid)
    settings_dict = get_settings(pid)
    res = reconcile_energy_balance(
        records,
        inverter_efficiency=settings_dict.get("battery_efficiency", 0.95),
        nominal_battery_kwh=settings_dict.get("battery_capacity_kwh", 0.0)
    )
    _metrics_cache[key] = res
    return res

@router.get("/datasets/{dataset_id}/events")
def get_operating_states(dataset_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    key = f"{pid}:events:{dataset_id}"
    if key in _metrics_cache:
        return _metrics_cache[key]
    records = _get_records(dataset_id, project_id=pid)
    settings_dict = get_settings(pid)
    res = build_operating_state_timeline(records, reserve_soc=settings_dict["reserve_soc"])
    _metrics_cache[key] = res
    return res

@router.get("/datasets/{dataset_id}/statistics")
def get_statistical_analysis(dataset_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    key = f"{pid}:statistics:{dataset_id}"
    if key in _metrics_cache:
        return _metrics_cache[key]
    records = _get_records(dataset_id, project_id=pid)
    profiles = get_complete_statistical_profile(records)
    correlations = calculate_correlation_matrices(records)
    res = {
        "profiles": profiles,
        "correlations": correlations
    }
    _metrics_cache[key] = res
    return res

@router.get("/datasets/{dataset_id}/anomalies")
def get_anomalies(dataset_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    key = f"{pid}:anomalies:{dataset_id}"
    if key in _metrics_cache:
        return _metrics_cache[key]
    records = _get_records(dataset_id, project_id=pid)
    res = detect_system_anomalies(records)
    _metrics_cache[key] = res
    return res

@router.post("/datasets/{dataset_id}/scenarios")
def run_scenario(dataset_id: str, payload: ScenarioRequest, auth: AuthContext = Depends(get_auth_context)):
    pid = auth.project_id
    records = _get_records(dataset_id, project_id=pid)
    settings_dict = get_settings(pid)
    mppt_min = float(settings_dict.get("mppt_voltage_min_v") or 0.0)
    mppt_max = float(settings_dict.get("mppt_voltage_max_v") or 0.0)
    mppt_range_str = f"{mppt_min:.0f}-{mppt_max:.0f} V DC" if mppt_max > 0 else "--"
    pv_max_v = float(settings_dict.get("pv_voltage_max_v") or 0.0)
    pv_max_str = f"{pv_max_v:.0f} V DC" if pv_max_v > 0 else "--"
    return simulate_system_scenarios(
        records=records,
        baseline_battery_kwh=settings_dict.get("battery_capacity_kwh", 0.0),
        add_battery_kwh=payload.add_battery_kwh,
        baseline_pv_kwp=settings_dict.get("pv_capacity_kwp", 0.0),
        add_pv_kwp=payload.add_pv_kwp,
        new_reserve_soc=payload.new_reserve_soc,
        shift_load_kwh=payload.shift_load_kwh,
        tariff_rate=_resolve_effective_import_tariff(settings_dict, project_id=pid),
        inverter_rated_kw=settings_dict.get("inverter_power_kw", 0.0),
        inverter_peak_va=settings_dict.get("inverter_max_apparent_va", 0.0),
        inverter_max_current_a=settings_dict.get("inverter_max_battery_current_a", 0.0),
        bms_max_current_a=settings_dict.get("bms_max_charge_a", 0.0),
        battery_voltage=settings_dict.get("battery_voltage", 0.0),
        mppt_range_v=mppt_range_str,
        pv_max_voltage_v=pv_max_str,
        baseline_reserve_soc=settings_dict.get("reserve_soc", 20.0)
    )

@router.get("/datasets/{dataset_id}/finance")
def get_finance_analysis(
    dataset_id: str,
    tariff_type: str = "flat",
    flat_rate: Optional[float] = None,
    peak_rate: float = 0.0,
    off_peak_rate: float = 0.0,
    system_capex: float = 0.0,
    auth: AuthContext = Depends(get_auth_context)
):
    pid = auth.project_id
    records = _get_records(dataset_id, project_id=pid)
    settings_dict = get_settings(pid)
    rate = flat_rate if flat_rate is not None else _resolve_effective_import_tariff(settings_dict, project_id=pid)
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
def get_historical_daily(dataset_id: Optional[str] = None, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    pid = auth.project_id
    ds_key = dataset_id or "historical"
    cache_key = f"{pid}:{ds_key}"
    if cache_key in _daily_summaries_cache:
        return _daily_summaries_cache[cache_key]
    records = _get_records(ds_key, project_id=pid)
    settings_dict = get_settings(pid)
    res = calculate_daily_summaries(
        records=records,
        pv_capacity_kwp=settings_dict["pv_capacity_kwp"],
        nominal_battery_kwh=settings_dict["battery_capacity_kwh"],
        reserve_soc=settings_dict["reserve_soc"]
    )
    _daily_summaries_cache[cache_key] = res
    return res

@router.get("/historical/weekly")
def get_historical_weekly(dataset_id: Optional[str] = None, auth: AuthContext = Depends(get_auth_context)):
    daily = get_historical_daily(dataset_id, auth=auth)
    return calculate_weekly_summaries(daily)

@router.get("/historical/monthly")
def get_historical_monthly(dataset_id: Optional[str] = None, auth: AuthContext = Depends(get_auth_context)):
    daily = get_historical_daily(dataset_id, auth=auth)
    return calculate_monthly_summaries(daily)

@router.get("/historical/hourly_profile")
def get_historical_hourly_profile(dataset_id: Optional[str] = None, auth: AuthContext = Depends(get_auth_context)):
    records = _get_records(dataset_id or "historical", project_id=auth.project_id)
    return calculate_hour_of_day_profiles(records)

@router.get("/historical/heatmap")
def get_historical_heatmap(metric: str = "pv_power_kw", dataset_id: Optional[str] = None, auth: AuthContext = Depends(get_auth_context)):
    records = _get_records(dataset_id or "historical", project_id=auth.project_id)
    return calculate_hour_date_heatmap(records, metric=metric)

@router.get("/historical/averages")
def get_historical_averages(dataset_id: Optional[str] = None, auth: AuthContext = Depends(get_auth_context)):
    pid = auth.project_id
    records = _get_records(dataset_id or "historical", project_id=pid)
    settings_dict = get_settings(pid)
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
    dataset_id: Optional[str] = None,
    auth: AuthContext = Depends(get_auth_context)
):
    records = _get_historical_records(auth.project_id)
    recs_a = [r for r in records if r.timestamp_valid and date_a_start <= r.timestamp[:10] <= date_a_end]
    recs_b = [r for r in records if r.timestamp_valid and date_b_start <= r.timestamp[:10] <= date_b_end]
    return compare_periods(recs_a, recs_b, label_a=f"{date_a_start} to {date_a_end}", label_b=f"{date_b_start} to {date_b_end}")

@router.get("/historical/weekdays_vs_weekends")
def get_weekdays_vs_weekends(dataset_id: Optional[str] = None, auth: AuthContext = Depends(get_auth_context)):
    records = _get_records(dataset_id or "historical", project_id=auth.project_id)
    return compare_weekdays_vs_weekends(records)

@router.post("/datasets/{dataset_id}/reports/generate")
def generate_report(dataset_id: str, payload: ReportGenRequest, auth: AuthContext = Depends(get_auth_context)):
    pid = auth.project_id
    records = _get_records(dataset_id, project_id=pid)
    settings_dict = get_settings(pid)

    solar = calculate_solar_metrics(
        records,
        pv_capacity_kwp=settings_dict.get("pv_capacity_kwp", 0.0),
        inverter_rating_kw=settings_dict.get("inverter_power_kw", 0.0)
    )
    consumption = calculate_consumption_metrics(records)
    battery = calculate_battery_metrics(
        records,
        nominal_capacity_kwh=settings_dict.get("battery_capacity_kwh", 0.0),
        reserve_soc=settings_dict.get("reserve_soc", 20.0),
        bms_max_current_a=settings_dict.get("bms_max_charge_a", 0.0),
        battery_voltage=settings_dict.get("battery_voltage", 0.0)
    )
    grid = calculate_grid_metrics(
        records,
        reserve_soc=settings_dict.get("reserve_soc", 20.0),
        inverter_power_kw=settings_dict.get("inverter_power_kw", 0.0),
        import_tariff=_resolve_effective_import_tariff(settings_dict, project_id=pid)
    )
    balance = reconcile_energy_balance(
        records,
        inverter_efficiency=settings_dict.get("battery_efficiency", 0.95),
        nominal_battery_kwh=settings_dict.get("battery_capacity_kwh", 0.0)
    )
    quality = calculate_data_quality_report(records)
    operating_states = build_operating_state_timeline(records, reserve_soc=settings_dict["reserve_soc"])

    valid_recs = [r for r in records if r.timestamp_valid]
    start_t = valid_recs[0].timestamp if valid_recs else ""
    end_t = valid_recs[-1].timestamp if valid_recs else ""

    summary_data = {
        "report_date": datetime.date.today().isoformat(),
        "filename": settings_dict.get("station_name") or "SolarScope_Dataset",
        "sheet_name": "Audited",
        "start_time": start_t,
        "start_time_12h": format_datetime_12h(start_t),
        "end_time": end_t,
        "end_time_12h": format_datetime_12h(end_t),
        "quality_score": quality["quality_score"],
        "quality_status": quality["status"],
        "pv_kwh": balance.get("pv_kwh", 0.0),
        "load_kwh": balance.get("household_demand_kwh", 0.0),
        "grid_import_kwh": balance.get("grid_imported_kwh", 0.0),
        "grid_export_kwh": balance.get("grid_exported_kwh", 0.0),
        "batt_disch_kwh": balance.get("battery_discharged_kwh", 0.0),
        "batt_chg_kwh": balance.get("battery_charged_kwh", 0.0),
        "residual_kwh": balance.get("residual_kwh", 0.0),
        "self_consumption": balance.get("solar_self_consumption_ratio", 0.0),
        "self_sufficiency": balance.get("solar_self_sufficiency_ratio", 0.0),
        "grid_dependence": grid.get("grid_dependence_ratio", 0.0),
        "peak_pv_kw": solar.get("peak_power_kw", 0.0),
        "peak_pv_time_12h": solar.get("peak_power_time_12h", ""),
        "peak_load_kw": consumption.get("peak_load_kw", 0.0),
        "peak_load_time_12h": consumption.get("peak_load_time_12h", ""),
        "base_load_kw": consumption.get("base_load_estimate_kw", 0.0),
        "total_sources_kwh": balance.get("total_sources_kwh", 0.0),
        "total_sinks_kwh": balance.get("total_sinks_kwh", 0.0)
    }

    report_id = str(uuid.uuid4())
    rep_type = payload.report_type.lower()

    if rep_type == "pdf":
        out_filename = f"SolarScope_Audit_{report_id[:8]}.pdf"
        out_path = settings.reports_dir / out_filename
        build_pdf_report(summary_data, out_path)
    elif rep_type == "excel" or rep_type == "xlsx":
        out_filename = f"SolarScope_Audit_{report_id[:8]}.xlsx"
        out_path = settings.reports_dir / out_filename
        hourly = []
        for h in range(24):
            hourly.append({
                "hour": h,
                "hour_label_12h": hour_index_to_12h(h),
                "pv_kwh": solar["hourly_breakdown"][h]["energy_kwh"] if solar else 0.0,
                "load_kwh": consumption["hourly_breakdown"][h]["energy_kwh"] if consumption else 0.0,
                "grid_kwh": grid["hourly_breakdown"][h]["energy_kwh"] if grid else 0.0
            })
        build_excel_report(records, summary_data, hourly, operating_states, out_path)
    else:
        out_filename = f"SolarScope_Audit_{report_id[:8]}.json"
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
    target_ds_id = dataset_id
    ds_check = conn.execute("SELECT id FROM datasets WHERE id = ? AND project_id = ?", (dataset_id, pid)).fetchone()
    if not ds_check:
        any_ds = conn.execute("SELECT id FROM datasets WHERE project_id = ? LIMIT 1", (pid,)).fetchone()
        if any_ds:
            target_ds_id = any_ds["id"]
    if ds_check or target_ds_id != dataset_id:
        conn.execute(
            """INSERT INTO audit_reports (id, project_id, dataset_id, report_type, filepath, filesize, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (report_id, pid, target_ds_id, rep_type, str(out_path), filesize, now)
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
def download_report(report_id: str, auth: AuthContext = Depends(get_auth_context)):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM audit_reports WHERE id = ? AND project_id = ?",
        (report_id, auth.project_id)
    ).fetchone()
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

@router.get("/billing/overview")
def get_billing_overview(
    response: Response,
    dataset_id: Optional[str] = None,
    fresh: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state(force=fresh)
    response.headers["Cache-Control"] = "no-store"
    pid = auth.project_id
    tz_name = get_settings(pid).get("timezone", "Asia/Manila")
    conn = get_connection()
    profile = get_billing_profile(conn, project_id=pid)
    sched = get_rate_schedule_for_month(conn, customer_class=profile.customer_class, billing_month=profile.billing_month, project_id=pid)
    check_state = get_rate_check_state(conn, project_id=pid)
    records = _get_records("all", project_id=pid)
    forecast = forecast_tei_bill(records, sched, profile, check_state, timezone=tz_name)
    sync_key = f"{len(records)}:{records[-1].timestamp if records else ''}:{profile.billing_cycle_day}:{profile.billing_month or ''}:{sched.id}"
    changed = False
    if _past_estimates_sync_key.get(pid) != sync_key:
        changed = sync_past_monthly_estimates(records, profile, conn, check_state, project_id=pid, timezone=tz_name)
        if upsert_monthly_estimate(forecast, profile, conn, project_id=pid):
            changed = True
        _past_estimates_sync_key[pid] = sync_key
    if changed:
        conn.commit()
    conn.close()
    if changed:
        _persist_state()
    return forecast

@router.get("/billing/progress")
def get_billing_progress(
    response: Response,
    dataset_id: Optional[str] = None,
    fresh: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state(force=fresh)
    response.headers["Cache-Control"] = "no-store"
    pid = auth.project_id
    conn = get_connection()
    profile = get_billing_profile(conn, project_id=pid)
    sched = get_rate_schedule_for_month(conn, customer_class=profile.customer_class, billing_month=profile.billing_month, project_id=pid)
    conn.close()
    records = _get_records("all", project_id=pid)
    return calculate_billing_progress_series(records, sched, profile)

@router.get("/billing/statement")
def get_billing_statement(
    response: Response,
    mode: str = "expected",
    dataset_id: Optional[str] = None,
    fresh: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state(force=fresh)
    response.headers["Cache-Control"] = "no-store"
    pid = auth.project_id
    tz_name = get_settings(pid).get("timezone", "Asia/Manila")
    conn = get_connection()
    profile = get_billing_profile(conn, project_id=pid)
    sched = get_rate_schedule_for_month(conn, customer_class=profile.customer_class, billing_month=profile.billing_month, project_id=pid)
    check_state = get_rate_check_state(conn, project_id=pid)
    conn.close()
    records = _get_records("all", project_id=pid)
    forecast = forecast_tei_bill(records, sched, profile, check_state, timezone=tz_name)
    if mode == "actual":
        return forecast.current_so_far_statement
    elif mode == "lower":
        return forecast.lower_estimate.statement
    elif mode == "higher":
        return forecast.higher_estimate.statement
    return forecast.expected_estimate.statement

@router.get("/billing/profile")
def get_billing_profile_endpoint(
    response: Response,
    fresh: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state(force=fresh)
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    prof = get_billing_profile(conn, project_id=auth.project_id)
    conn.close()
    return prof.model_dump()

@router.put("/billing/profile")
def update_billing_profile_endpoint(
    profile: TEIBillingProfile,
    response: Response,
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state(force=True)
    response.headers["Cache-Control"] = "no-store"
    pid = auth.project_id
    tz_name = get_settings(pid).get("timezone", "Asia/Manila")
    conn = get_connection()
    save_billing_profile(profile, conn, project_id=pid)
    conn.commit()
    saved = get_billing_profile(conn, project_id=pid)
    sched = get_rate_schedule_for_month(conn, customer_class=saved.customer_class, billing_month=saved.billing_month, project_id=pid)
    check_state = get_rate_check_state(conn, project_id=pid)
    records = _get_records("all", project_id=pid)
    forecast = forecast_tei_bill(records, sched, saved, check_state, timezone=tz_name)
    sync_past_monthly_estimates(records, saved, conn, check_state, project_id=pid, timezone=tz_name)
    upsert_monthly_estimate(forecast, saved, conn, project_id=pid)
    conn.commit()
    conn.close()
    _past_estimates_sync_key.pop(pid, None)
    _persist_state()
    return {"status": "updated", "profile": saved.model_dump()}

@router.get("/billing/rates")
def get_billing_rates(
    response: Response,
    fresh: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state(force=fresh)
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    rates = get_rate_history(conn, project_id=auth.project_id)
    conn.close()
    return rates

@router.post("/billing/rates/check_now")
def check_billing_rates_now(response: Response, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    response.headers["Cache-Control"] = "no-store"
    pid = auth.project_id
    tz_name = get_settings(pid).get("timezone", "Asia/Manila")
    conn = get_connection()
    profile = get_billing_profile(conn, project_id=pid)
    res = check_official_tei_rates(conn, force_fetch=True, customer_class=profile.customer_class, project_id=pid)
    active_sched = res.get("active_schedule") or get_active_rate_schedule(conn, customer_class=profile.customer_class, project_id=pid)
    eff_sched = get_rate_schedule_for_month(conn, customer_class=profile.customer_class, billing_month=profile.billing_month, project_id=pid)
    records = _get_records("all", project_id=pid)
    forecast = forecast_tei_bill(records, eff_sched, profile, res, timezone=tz_name)
    progress = calculate_billing_progress_series(records, eff_sched, profile)
    sync_past_monthly_estimates(records, profile, conn, res, project_id=pid, timezone=tz_name)
    upsert_monthly_estimate(forecast, profile, conn, project_id=pid)
    rates = get_rate_history(conn, project_id=pid)
    conn.commit()
    conn.close()
    _past_estimates_sync_key.pop(pid, None)
    _persist_state()
    return {
        "status": res["status"],
        "message": res["message"],
        "checked_at": res["checked_at"],
        "rate_change_alert": res["rate_change_alert"],
        "effective_month": active_sched.effective_month if active_sched else "",
        "active_schedule": active_sched.model_dump() if active_sched else None,
        "rates": rates,
        "forecast": forecast.model_dump(),
        "progress": progress
    }

@router.post("/billing/rates/manual")
def add_manual_billing_rate(payload: ManualRateScheduleRequest, auth: AuthContext = Depends(get_auth_context)):
    import hashlib
    _hydrate_state(force=True)
    pid = auth.project_id
    tz_name = get_settings(pid).get("timezone", "Asia/Manila")
    conn = get_connection()
    active_sched = get_active_rate_schedule(conn, customer_class=payload.customer_class, project_id=pid)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_comps = []
    for comp in active_sched.components:
        c_copy = comp.model_copy()
        if c_copy.component_id == "gen_charge":
            c_copy.rate_per_kwh = payload.generation_charge
            c_copy.vat_rate_per_kwh = payload.generation_vat
            c_copy.vat_treatment = "fixed_rate" if payload.generation_vat > 0 else "exempt"
        elif c_copy.component_id == "dist_charge":
            c_copy.rate_per_kwh = payload.distribution_charge
        elif c_copy.component_id == "trans_charge":
            c_copy.rate_per_kwh = payload.transmission_charge
        elif c_copy.component_id == "system_loss_charge":
            c_copy.rate_per_kwh = payload.system_loss_charge
        new_comps.append(c_copy)
    slug_class = payload.customer_class.lower().replace(" ", "_")
    sched_id = f"tei-rate-{pid}-{payload.effective_month}-{slug_class}-manual"
    new_sched = TEIRateSchedule(
        id=sched_id,
        effective_month=payload.effective_month,
        customer_class=payload.customer_class,
        publication_date=datetime.datetime.now().strftime("%Y-%m-%d"),
        source_url="Manual User Entry",
        document_hash=hashlib.sha256(f"{pid}-{payload.effective_month}-{payload.generation_charge}".encode()).hexdigest(),
        verification_status="manual",
        components=new_comps,
        created_at=now_iso
    )
    save_rate_schedule(new_sched, conn, project_id=pid)
    set_project_active_schedule(conn, pid, payload.customer_class, sched_id)
    check_state = {
        "status": "manual_applied",
        "message": f"Manual rate schedule for {payload.effective_month} activated.",
        "checked_at": now_iso,
        "rate_change_alert": None
    }
    save_rate_check_state(check_state, conn, project_id=pid)
    profile = get_billing_profile(conn, project_id=pid)
    eff_sched = get_rate_schedule_for_month(conn, customer_class=profile.customer_class, billing_month=profile.billing_month, project_id=pid)
    records = _get_records("all", project_id=pid)
    forecast = forecast_tei_bill(records, eff_sched, profile, check_state, timezone=tz_name)
    upsert_monthly_estimate(forecast, profile, conn, project_id=pid)
    conn.commit()
    conn.close()
    _past_estimates_sync_key.pop(pid, None)
    _persist_state()
    return {"status": "created", "schedule_id": new_sched.id, "active_schedule": new_sched.model_dump()}

@router.post("/billing/rates/{schedule_id}/activate")
def activate_billing_rate_endpoint(schedule_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    pid = auth.project_id
    tz_name = get_settings(pid).get("timezone", "Asia/Manila")
    conn = get_connection()
    activated = activate_rate_schedule(schedule_id, conn, project_id=pid)
    if not activated:
        conn.close()
        raise HTTPException(status_code=404, detail="Rate schedule not found")
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    check_state = {
        "status": "verified_current" if activated.verification_status == "verified" else "manual_applied",
        "message": f"Activated TEI {activated.effective_month} ({activated.customer_class}) rate schedule.",
        "checked_at": now_iso,
        "rate_change_alert": None
    }
    save_rate_check_state(check_state, conn, project_id=pid)
    profile = get_billing_profile(conn, project_id=pid)
    records = _get_records("all", project_id=pid)
    forecast = forecast_tei_bill(records, activated, profile, check_state, timezone=tz_name)
    upsert_monthly_estimate(forecast, profile, conn, project_id=pid)
    conn.commit()
    conn.close()
    _past_estimates_sync_key.pop(pid, None)
    _persist_state()
    return {"status": "activated", "schedule_id": activated.id, "active_schedule": activated.model_dump()}

@router.post("/billing/sensitivity")
def calculate_sensitivity_endpoint(
    response: Response,
    payload: SensitivityRequest,
    dataset_id: Optional[str] = None,
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    pid = auth.project_id
    tz_name = get_settings(pid).get("timezone", "Asia/Manila")
    conn = get_connection()
    profile = get_billing_profile(conn, project_id=pid)
    sched = get_rate_schedule_for_month(conn, customer_class=profile.customer_class, billing_month=profile.billing_month, project_id=pid)
    check_state = get_rate_check_state(conn, project_id=pid)
    conn.close()
    records = _get_records(dataset_id or "all", project_id=pid)
    forecast = forecast_tei_bill(records, sched, profile, check_state, timezone=tz_name)
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

@router.get("/billing/estimates")
def get_monthly_estimates_endpoint(
    response: Response,
    fresh: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state(force=fresh)
    response.headers["Cache-Control"] = "no-store"
    pid = auth.project_id
    tz_name = get_settings(pid).get("timezone", "Asia/Manila")
    conn = get_connection()
    profile = get_billing_profile(conn, project_id=pid)
    check_state = get_rate_check_state(conn, project_id=pid)
    records = _get_records("all", project_id=pid)
    sched = get_rate_schedule_for_month(conn, customer_class=profile.customer_class, billing_month=profile.billing_month, project_id=pid)
    sync_key = f"{len(records)}:{records[-1].timestamp if records else ''}:{profile.billing_cycle_day}:{profile.billing_month or ''}:{sched.id}"
    changed = False
    if fresh or _past_estimates_sync_key.get(pid) != sync_key:
        changed = sync_past_monthly_estimates(records, profile, conn, check_state, project_id=pid, timezone=tz_name)
        _past_estimates_sync_key[pid] = sync_key
        if changed:
            conn.commit()
    estimates = get_monthly_estimates(conn, project_id=pid, timezone=tz_name)
    conn.close()
    if changed:
        _persist_state()
    return estimates

@router.delete("/billing/estimates/{estimate_id}")
def delete_monthly_estimate_endpoint(estimate_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    pid = auth.project_id
    conn = get_connection()
    success = delete_monthly_estimate(estimate_id, conn, project_id=pid)
    conn.commit()
    conn.close()
    if not success:
        raise HTTPException(status_code=404, detail="Monthly estimate not found")
    _persist_state()
    return {"status": "deleted", "id": estimate_id}

@router.get("/billing/history")
def get_historical_bills_endpoint(
    response: Response,
    fresh: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state(force=fresh)
    response.headers["Cache-Control"] = "no-store"
    conn = get_connection()
    bills = get_historical_bills_summary(conn, project_id=auth.project_id)
    conn.close()
    return bills

@router.post("/billing/history")
def add_historical_bill_endpoint(payload: AddHistoricalBillRequest, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    conn = get_connection()
    res = insert_historical_bill(
        billing_period_start=payload.billing_period_start,
        billing_period_end=payload.billing_period_end,
        billed_kwh=payload.billed_kwh,
        actual_amount_due=payload.actual_amount_due,
        predicted_amount_due=payload.predicted_amount_due,
        notes=payload.notes or "",
        conn=conn,
        project_id=auth.project_id
    )
    conn.commit()
    conn.close()
    _persist_state()
    return res

@router.delete("/billing/history/{bill_id}")
def delete_historical_bill_endpoint(bill_id: str, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state(force=True)
    conn = get_connection()
    success = remove_historical_bill(bill_id, conn, project_id=auth.project_id)
    conn.commit()
    conn.close()
    if not success:
        raise HTTPException(status_code=404, detail="Historical bill not found")
    _persist_state()
    return {"status": "deleted", "id": bill_id}

@router.get("/deye/status")
def get_deye_status_endpoint(response: Response, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    client = DeyeCloudClient(project_id=auth.project_id)
    status = client.get_status()
    status["is_demo"] = status.get("app_id") == "demo" or status.get("username") == "demo"
    return status

@router.post("/deye/config")
def save_deye_config_endpoint(
    payload: DeyeConfigPayload,
    response: Response,
    auth: AuthContext = Depends(get_auth_context)
):
    response.headers["Cache-Control"] = "no-store"
    client = DeyeCloudClient(project_id=auth.project_id)
    client.save_config(payload.model_dump())
    status = client.get_status()
    status["is_demo"] = status.get("app_id") == "demo" or status.get("username") == "demo"
    return status

@router.delete("/deye/config")
def clear_deye_config_endpoint(response: Response, auth: AuthContext = Depends(get_auth_context)):
    response.headers["Cache-Control"] = "no-store"
    client = DeyeCloudClient(project_id=auth.project_id)
    client.clear_config()
    status = client.get_status()
    status["is_demo"] = False
    return status

@router.post("/deye/test")
def test_deye_connection_endpoint(
    response: Response,
    payload: Optional[DeyeConfigPayload] = Body(default=None),
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    client = DeyeCloudClient(project_id=auth.project_id)
    if payload and any([payload.station_id, payload.app_id, payload.app_secret, payload.username, payload.password]):
        client.save_config(payload.model_dump())
    return client.test_connection()

@router.post("/deye/sync")
def sync_deye_endpoint(
    response: Response,
    payload: Optional[DeyeConfigPayload] = Body(default=None),
    auth: AuthContext = Depends(get_auth_context)
):
    pid = auth.project_id
    try:
        _hydrate_state(force=True)
        response.headers["Cache-Control"] = "no-store"
        client = DeyeCloudClient(project_id=pid)
        if payload and any([payload.station_id, payload.app_id, payload.app_secret, payload.username, payload.password]):
            client.save_config(payload.model_dump())
        res = client.sync_now()
        invalidate_all_caches(pid)
        return res
    except Exception as e:
        return {"status": "FAILED", "message": str(e), "records_inserted": 0}

@router.post("/deye/sync_range")
def sync_deye_range_endpoint(
    payload: DeyeSyncRangePayload,
    response: Response,
    auth: AuthContext = Depends(get_auth_context)
):
    pid = auth.project_id
    try:
        _hydrate_state(force=True)
        response.headers["Cache-Control"] = "no-store"
        client = DeyeCloudClient(project_id=pid)
        if payload.credentials and any([payload.credentials.station_id, payload.credentials.app_id, payload.credentials.app_secret, payload.credentials.username, payload.credentials.password]):
            client.save_config(payload.credentials.model_dump())
        res = client.sync_range(payload.start_date, payload.end_date)
        invalidate_all_caches(pid)
        return res
    except Exception as e:
        return {"status": "FAILED", "message": str(e), "records_inserted": 0}

@router.get("/deye/missing_dates")
def get_deye_missing_dates_endpoint(response: Response, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    client = DeyeCloudClient(project_id=auth.project_id)
    missing = client.get_missing_dates()
    return {"missing_dates": missing, "count": len(missing)}

@router.post("/deye/sync_missing")
def sync_deye_missing_endpoint(response: Response, auth: AuthContext = Depends(get_auth_context)):
    pid = auth.project_id
    _hydrate_state(force=True)
    response.headers["Cache-Control"] = "no-store"
    client = DeyeCloudClient(project_id=pid)
    res = client.sync_missing_dates()
    invalidate_all_caches(pid)
    return res

@router.get("/deye/live_flow")
def get_deye_live_flow_endpoint(
    response: Response,
    refresh: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    return get_deye_mcp_client(auth.project_id).get_live_flow(force_refresh=refresh)

@router.get("/deye/health")
def get_deye_health_endpoint(response: Response, auth: AuthContext = Depends(get_auth_context)):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    return get_deye_mcp_client(auth.project_id).get_station_health()

@router.get("/weather/intelligence")
def get_weather_endpoint(
    response: Response,
    refresh: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context)
):
    _hydrate_state()
    response.headers["Cache-Control"] = "no-store"
    pid = auth.project_id
    settings_dict = get_settings(pid)
    lat = float(settings_dict.get("latitude") or 0.0)
    lon = float(settings_dict.get("longitude") or 0.0)
    loc_name = (settings_dict.get("location_name") or "").strip()
    tz_str = (settings_dict.get("timezone") or "Asia/Manila").strip()
    kwp = float(settings_dict.get("pv_capacity_kwp") or 0.0)
    batt = float(settings_dict.get("battery_capacity_kwh") or 0.0)
    res_soc = float(settings_dict.get("reserve_soc") if settings_dict.get("reserve_soc") is not None else 20.0)
    current_soc = 0.0
    daily_cons = 0.0
    records = _get_records("all", project_id=pid)
    if records:
        current_soc = float(records[-1].soc_percent or 0.0)
        daily_sums = calculate_daily_summaries(
            records=records,
            pv_capacity_kwp=kwp,
            nominal_battery_kwh=batt,
            reserve_soc=res_soc
        )
        if daily_sums:
            daily_cons = round(sum(d.get("load_kwh", 0.0) for d in daily_sums) / len(daily_sums), 2)
    return get_weather_intelligence(
        lat=lat,
        lon=lon,
        location_name=loc_name,
        timezone_str=tz_str,
        installed_kwp=kwp,
        battery_capacity_kwh=batt,
        reserve_soc=res_soc,
        current_soc=current_soc,
        daily_consumption_kwh=daily_cons,
        force_refresh=refresh
    )

@router.post("/ingestion/preview")
async def preview_uploaded_files(file: UploadFile = File(...), auth: AuthContext = Depends(get_auth_context)):
    temp_dir = settings.data_dir / "temp_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    safe_name = extract_basename(file.filename or "preview.xlsx")
    temp_path = temp_dir / f"preview_{uuid.uuid4().hex}_{safe_name}"
    content = await file.read()
    temp_path.write_bytes(content)
    try:
        preview = inspect_file_for_preview(temp_path, safe_name, project_id=auth.project_id)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return preview

@router.get("/datasets/{dataset_id}/grid_classification")
def get_grid_classification_endpoint(dataset_id: str, auth: AuthContext = Depends(get_auth_context)):
    return get_grid_analysis(dataset_id, auth=auth)

@router.post("/datasets/{dataset_id}/simulation_upgrade")
def simulate_upgrade_endpoint(
    dataset_id: str,
    payload: UpgradeSimulationRequest,
    auth: AuthContext = Depends(get_auth_context)
):
    pid = auth.project_id
    records = _get_records(dataset_id, project_id=pid)
    settings_dict = get_settings(pid)
    mppt_min = float(settings_dict.get("mppt_voltage_min_v") or 0.0)
    mppt_max = float(settings_dict.get("mppt_voltage_max_v") or 0.0)
    mppt_range_str = f"{mppt_min:.0f}-{mppt_max:.0f} V DC" if mppt_max > 0 else "--"
    pv_max_v = float(settings_dict.get("pv_voltage_max_v") or 0.0)
    pv_max_str = f"{pv_max_v:.0f} V DC" if pv_max_v > 0 else "--"
    return simulate_system_scenarios(
        records,
        baseline_battery_kwh=settings_dict.get("battery_capacity_kwh", 0.0),
        add_battery_kwh=payload.add_battery_kwh,
        baseline_pv_kwp=settings_dict.get("pv_capacity_kwp", 0.0),
        add_pv_kwp=payload.add_pv_kwp,
        new_reserve_soc=payload.new_reserve_soc,
        shift_load_kwh=payload.shift_load_kwh,
        tariff_rate=_resolve_effective_import_tariff(settings_dict, project_id=pid),
        inverter_rated_kw=settings_dict.get("inverter_power_kw", 0.0),
        inverter_peak_va=settings_dict.get("inverter_max_apparent_va", 0.0),
        inverter_max_current_a=settings_dict.get("inverter_max_battery_current_a", 0.0),
        bms_max_current_a=settings_dict.get("bms_max_charge_a", 0.0),
        battery_voltage=settings_dict.get("battery_voltage", 0.0),
        mppt_range_v=mppt_range_str,
        pv_max_voltage_v=pv_max_str,
        baseline_reserve_soc=settings_dict.get("reserve_soc", 20.0)
    )

@router.get("/analyst/presets")
def get_analyst_presets_endpoint(auth: AuthContext = Depends(get_auth_context)):
    return get_preset_diagnostic_queries()

@router.post("/datasets/{dataset_id}/analyst/query")
def run_analyst_query_endpoint(
    dataset_id: str,
    payload: AnalystQueryRequest,
    auth: AuthContext = Depends(get_auth_context)
):
    pid = auth.project_id
    records = _get_records(dataset_id, project_id=pid)
    return analyze_energy_query(
        records,
        query_key=payload.query_key,
        query_text=payload.query_text or "",
        project_id=pid
    )

@router.post("/datasets/{dataset_id}/analyst/stream")
def stream_analyst_endpoint(
    dataset_id: str,
    payload: AnalystStreamRequest,
    auth: AuthContext = Depends(get_auth_context)
):
    pid = auth.project_id
    records = _get_records(dataset_id, project_id=pid)

    def event_generator():
        for chunk in stream_analyst_response(payload.query_text, records, project_id=pid):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/analyst/performance")
def get_analyst_performance_endpoint(auth: AuthContext = Depends(get_auth_context)):
    return get_performance_overview(project_id=auth.project_id)

@router.get("/analyst/mcp/status")
def get_analyst_mcp_status_endpoint(auth: AuthContext = Depends(get_auth_context)):
    return get_performance_overview(project_id=auth.project_id)
