import hashlib
import json
import datetime
from typing import Dict, Any, List
from backend.app.ingestion.models import CanonicalRecord
from backend.app.analyst.data_retriever import extract_system_snapshot
from backend.app.analyst.evidence_engine import build_evidence_response
from backend.app.integrations.weather import get_weather_intelligence
from backend.app.storage.db import get_connection

def analyze_energy_query(
    records: List[CanonicalRecord],
    query_key: str,
    query_text: str = "",
    project_id: str = "default"
) -> Dict[str, Any]:
    query_hash = hashlib.sha256(f"{query_key}:{query_text}:{len(records)}".encode("utf-8")).hexdigest()

    conn = get_connection()
    cached = conn.execute("SELECT response_json FROM analyst_cache WHERE query_hash = ?", (query_hash,)).fetchone()
    conn.close()

    if cached:
        try:
            return json.loads(cached["response_json"])
        except Exception:
            pass

    snapshot = extract_system_snapshot(records, project_id=project_id)
    weather_info = get_weather_intelligence()
    result = build_evidence_response(query_key, snapshot, weather_info)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    c_conn = get_connection()
    c_conn.execute(
        """INSERT OR REPLACE INTO analyst_cache (id, query_hash, query_text, response_json, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (f"cache-{query_hash[:16]}", query_hash, query_text or query_key, json.dumps(result), now_iso)
    )
    c_conn.commit()
    c_conn.close()

    return result

def get_preset_diagnostic_queries() -> List[Dict[str, str]]:
    return [
        {
            "id": "why_battery_drained",
            "category": "Battery Health",
            "question": "Why did my battery drain quickly yesterday?"
        },
        {
            "id": "why_grid_purchased_with_battery",
            "category": "Grid Purchases",
            "question": "Why did my system purchase electricity from TEI even though the battery had charge?"
        },
        {
            "id": "will_battery_last_tonight",
            "category": "Nighttime Autonomy",
            "question": "Will my battery last throughout the night based on tomorrow's weather?"
        },
        {
            "id": "should_add_battery",
            "category": "Hardware Upgrades",
            "question": "Would adding more battery capacity significantly reduce my grid purchases?"
        },
        {
            "id": "system_performance_audit",
            "category": "System Efficiency",
            "question": "Is my solar and battery system operating at peak efficiency?"
        }
    ]

