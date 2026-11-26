import hashlib
import json
import time
import datetime
from typing import Dict, Any, List, Generator
from backend.app.ingestion.models import CanonicalRecord
from backend.app.analyst.data_retriever import extract_system_snapshot
from backend.app.analyst.evidence_engine import build_evidence_response
from backend.app.analyst.question_classifier import QuestionClassifier
from backend.app.analyst.fast_path import execute_fast_path
from backend.app.analyst.diagnostic_engine import DiagnosticEngine
from backend.app.analyst.response_formatter import format_diagnostic_response
from backend.app.integrations.weather import get_weather_intelligence
from backend.app.integrations.deye_mcp import get_deye_mcp_client
from backend.app.storage.db import get_connection

classifier = QuestionClassifier()

def analyze_energy_query(
    records: List[CanonicalRecord],
    query_key: str,
    query_text: str = "",
    project_id: str = "default"
) -> Dict[str, Any]:
    conn = get_connection()
    sys_row = conn.execute("SELECT * FROM system_settings WHERE project_id = ?", (project_id,)).fetchone()
    settings_stamp = (sys_row["updated_at"] or "") if sys_row else ""
    query_hash = hashlib.sha256(f"{project_id}:{query_key}:{query_text}:{len(records)}:{settings_stamp}".encode("utf-8")).hexdigest()
    cached = conn.execute(
        "SELECT response_json FROM analyst_cache WHERE query_hash = ? AND project_id = ?",
        (query_hash, project_id)
    ).fetchone()
    conn.close()

    if cached:
        try:
            return json.loads(cached["response_json"])
        except Exception:
            pass

    snapshot = extract_system_snapshot(records, project_id=project_id)
    keys = sys_row.keys() if sys_row else []
    lat = float(sys_row["latitude"] or 0.0) if "latitude" in keys else 0.0
    lon = float(sys_row["longitude"] or 0.0) if "longitude" in keys else 0.0
    loc_name = (sys_row["location_name"] or "").strip() if "location_name" in keys else ""
    tz_str = (sys_row["timezone"] or "Asia/Manila").strip() if "timezone" in keys else "Asia/Manila"
    pv_kwp = float(sys_row["pv_capacity_kwp"] or 0.0) if "pv_capacity_kwp" in keys else 0.0
    batt_kwh = float(sys_row["battery_capacity_kwh"] or 0.0) if "battery_capacity_kwh" in keys else 0.0
    reserve_soc = float(sys_row["reserve_soc"] if sys_row["reserve_soc"] is not None else 20.0) if "reserve_soc" in keys else 20.0

    current_soc = records[-1].soc_percent if records else 0.0
    daily_cons = snapshot.get("consumption", {}).get("total_demand_kwh", 0.0)

    weather_info = get_weather_intelligence(
        lat=lat,
        lon=lon,
        location_name=loc_name,
        timezone_str=tz_str,
        installed_kwp=pv_kwp,
        battery_capacity_kwh=batt_kwh,
        reserve_soc=reserve_soc,
        current_soc=current_soc,
        daily_consumption_kwh=daily_cons
    )
    result = build_evidence_response(query_key, snapshot, weather_info)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    c_conn = get_connection()
    c_conn.execute(
        """INSERT INTO analyst_cache (id, project_id, query_hash, query_text, response_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(query_hash) DO UPDATE SET
               response_json = excluded.response_json,
               created_at = excluded.created_at""",
        (f"cache-{query_hash[:16]}", project_id, query_hash, query_text or query_key, json.dumps(result), now_iso)
    )
    c_conn.commit()
    c_conn.close()

    return result

def stream_analyst_response(
    query_text: str,
    records: List[CanonicalRecord],
    project_id: str = "default"
) -> Generator[Dict[str, Any], None, None]:
    start_t = time.perf_counter()
    classification = classifier.classify(query_text)
    path = classification["path"]

    if path == "FAST_PATH":
        yield {"type": "status", "message": "Executing deterministic calculation..."}
        fast_res = execute_fast_path({
            "metric": classification["metric"].lower(),
            "intent": classification["intent"],
            "target_period": classification["date_info"].get("date_str")
        }, project_id=project_id)

        duration_ms = (time.perf_counter() - start_t) * 1000.0
        yield {
            "type": "fast_path",
            "title": fast_res.get("title", "Energy Calculation"),
            "content": fast_res.get("response_text", ""),
            "data": fast_res.get("data")
        }
        yield {
            "type": "done",
            "stats": {
                "path": "FAST_PATH",
                "duration_ms": round(duration_ms, 2),
                "source": "Deterministic Engine",
                "confidence": "Confirmed"
            }
        }
        return

    if path == "CLARIFICATION_REQUIRED":
        yield {
            "type": "fast_path",
            "title": "Inquiry Clarification",
            "content": (
                "Please specify what you would like to analyze: solar generation, "
                "battery charge levels, utility electricity purchases, or live station health."
            )
        }
        yield {
            "type": "done",
            "stats": {
                "path": "FAST_PATH",
                "duration_ms": 1.0,
                "source": "Deterministic Router",
                "confidence": "Confirmed"
            }
        }
        return

    yield {"type": "status", "message": "Classifying diagnostic inquiry..."}
    time.sleep(0.05)

    yield {"type": "status", "message": "Inspecting local telemetry database..."}
    local_records_dicts = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in records]

    yield {"type": "status", "message": "Querying Deye Cloud telemetry state..."}
    engine = DiagnosticEngine(project_id=project_id)
    diag = engine.investigate(classification, local_records_dicts)

    yield {"type": "status", "message": "Evaluating energy-balance rules and alert registers..."}
    formatted_text = format_diagnostic_response(diag)

    words = formatted_text.split(" ")
    chunk_size = 4
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i+chunk_size]) + " "
        yield {"type": "token", "token": chunk}
        time.sleep(0.01)

    duration_ms = (time.perf_counter() - start_t) * 1000.0
    yield {
        "type": "done",
        "stats": {
            "path": path,
            "duration_ms": round(duration_ms, 2),
            "confidence": diag.get("confidence_level", "Confirmed"),
            "source": "Deye Open MCP + Deterministic Diagnostics",
            "main_cause": diag.get("most_likely_explanation", "")
        }
    }

def get_performance_overview(project_id: str = "default") -> Dict[str, Any]:
    mcp_client = get_deye_mcp_client(project_id)
    creds = mcp_client._get_credentials()
    has_creds = bool(creds["app_id"] and creds["app_secret"])
    conn = get_connection()
    sys_row = conn.execute("SELECT * FROM system_settings WHERE project_id = ?", (project_id,)).fetchone()
    conn.close()

    keys = sys_row.keys() if sys_row else []
    station_name = (sys_row["station_name"] or "").strip() if "station_name" in keys else ""
    loc_name = (sys_row["location_name"] or "").strip() if "location_name" in keys else ""
    pv_kwp = float(sys_row["pv_capacity_kwp"] or 0.0) if "pv_capacity_kwp" in keys else 0.0
    inv_kw = float(sys_row["inverter_power_kw"] or 0.0) if "inverter_power_kw" in keys else 0.0
    batt_kwh = float(sys_row["battery_capacity_kwh"] or 0.0) if "battery_capacity_kwh" in keys else 0.0
    panel_model = (sys_row["panel_model"] or "").strip() if "panel_model" in keys else ""
    inverter_model = (sys_row["inverter_model"] or "").strip() if "inverter_model" in keys else ""
    battery_model = (sys_row["battery_model"] or "").strip() if "battery_model" in keys else ""

    hw_parts = []
    if pv_kwp > 0:
        hw_parts.append(f"{panel_model} {pv_kwp} kWp".strip() if panel_model else f"PV {pv_kwp} kWp")
    if inv_kw > 0:
        hw_parts.append(f"{inverter_model} {inv_kw} kW".strip() if inverter_model else f"Inverter {inv_kw} kW")
    if batt_kwh > 0:
        hw_parts.append(f"{battery_model} {batt_kwh} kWh".strip() if battery_model else f"Battery {batt_kwh} kWh")

    return {
        "mcp_connected": has_creds,
        "mcp_endpoint": mcp_client.mcp_endpoint,
        "station_name": station_name or "Station Not Configured",
        "station_id": creds["station_id"],
        "inverter_sn": creds["inverter_sn"],
        "read_only_enforced": True,
        "inference_engine": "100% Deterministic Physics & Telemetry Rules",
        "hardware_profile": " | ".join(hw_parts) if hw_parts else "Hardware profile not configured",
        "utility": loc_name or "Utility Tariff Configured in Billing"
    }

def get_preset_diagnostic_queries() -> List[Dict[str, str]]:
    return [
        {"id": "why_battery_drained", "category": "Battery", "question": "Why did my battery drain down to its reserve limit?"},
        {"id": "why_grid_purchased_with_battery", "category": "Grid", "question": "Why did my home buy grid electricity while the battery had charge?"},
        {"id": "will_battery_last_tonight", "category": "Forecast", "question": "Will my solar and battery cover tonight's household demand?"},
        {"id": "should_add_battery", "category": "Upgrades", "question": "Would adding 5 kWh of battery storage pay off for my household?"},
        {"id": "performance_audit", "category": "Overview", "question": "Summarize my overall solar generation, consumption, and grid reliance."}
    ]
