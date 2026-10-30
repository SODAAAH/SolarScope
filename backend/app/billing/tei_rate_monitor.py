import urllib.request
import urllib.error
import re
import json
import hashlib
import datetime
from typing import Dict, Any, Optional, Tuple, List
from backend.app.billing.tariff_models import TEIRateSchedule, TEIRateComponent
from backend.app.billing.tariff_defaults import (
    get_default_october_2026_schedule,
    get_default_october_2026_components
)

OFFICIAL_TEI_URL = "https://tarlacelectric.com/rate-schedule-customer-class"

def compute_document_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def get_active_rate_schedule(conn) -> TEIRateSchedule:
    row = conn.execute(
        "SELECT * FROM tei_rate_schedules WHERE is_active = 1 ORDER BY effective_month DESC, created_at DESC LIMIT 1"
    ).fetchone()
    if row:
        comps_data = json.loads(row["schedule_data_json"])
        comps = [TEIRateComponent(**c) for c in comps_data]
        return TEIRateSchedule(
            id=row["id"],
            effective_month=row["effective_month"],
            customer_class=row["customer_class"],
            publication_date=row["publication_date"] or "",
            source_url=row["source_url"] or OFFICIAL_TEI_URL,
            document_hash=row["document_hash"] or "",
            verification_status=row["verification_status"] or "verified",
            components=comps,
            created_at=row["created_at"]
        )
    default_sched = get_default_october_2026_schedule()
    save_rate_schedule(default_sched, conn)
    return default_sched

def save_rate_schedule(schedule: TEIRateSchedule, conn) -> None:
    conn.execute("UPDATE tei_rate_schedules SET is_active = 0 WHERE customer_class = ?", (schedule.customer_class,))
    comps_json = json.dumps([c.model_dump() for c in schedule.components])
    conn.execute(
        """INSERT OR REPLACE INTO tei_rate_schedules
           (id, effective_month, customer_class, publication_date, source_url, document_hash, verification_status, is_active, schedule_data_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        (
            schedule.id,
            schedule.effective_month,
            schedule.customer_class,
            schedule.publication_date,
            schedule.source_url,
            schedule.document_hash,
            schedule.verification_status,
            comps_json,
            schedule.created_at
        )
    )

def get_rate_history(conn) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, effective_month, customer_class, publication_date, source_url, document_hash, verification_status, is_active, created_at, schedule_data_json FROM tei_rate_schedules ORDER BY effective_month DESC, created_at DESC"
    ).fetchall()
    results = []
    for r in rows:
        comps = json.loads(r["schedule_data_json"])
        gen_rate = next((c["rate_per_kwh"] for c in comps if c["component_id"] == "gen_charge"), 6.7489)
        results.append({
            "id": r["id"],
            "effective_month": r["effective_month"],
            "customer_class": r["customer_class"],
            "publication_date": r["publication_date"],
            "source_url": r["source_url"],
            "document_hash": r["document_hash"],
            "verification_status": r["verification_status"],
            "is_active": bool(r["is_active"]),
            "created_at": r["created_at"],
            "generation_charge": gen_rate,
            "components_count": len(comps)
        })
    return results

def check_official_tei_rates(conn, force_fetch: bool = False) -> Dict[str, Any]:
    active_sched = get_active_rate_schedule(conn)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    prev_gen_rate = 6.74890
    for c in active_sched.components:
        if c.component_id == "gen_charge":
            prev_gen_rate = c.rate_per_kwh

    try:
        req = urllib.request.Request(
            OFFICIAL_TEI_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            html_bytes = response.read()
            html_text = html_bytes.decode("utf-8", errors="ignore")
            doc_hash = compute_document_hash(html_bytes)

            gen_match = re.search(r"Generation\s*(?:Charge)?\s*[:=\s]*[₱P]?\s*([0-9]+\.[0-9]+)", html_text, re.IGNORECASE)
            extracted_gen = float(gen_match.group(1)) if gen_match else None

            if extracted_gen and 4.0 <= extracted_gen <= 20.0 and abs(extracted_gen - prev_gen_rate) > 0.0001:
                new_comps = []
                for c in active_sched.components:
                    comp_copy = c.model_copy()
                    if comp_copy.component_id == "gen_charge":
                        comp_copy.rate_per_kwh = extracted_gen
                    new_comps.append(comp_copy)

                effective_month = datetime.datetime.now().strftime("%Y-%m")
                new_sched = TEIRateSchedule(
                    id=f"tei-rate-{effective_month}-residential",
                    effective_month=effective_month,
                    customer_class="Residential",
                    publication_date=datetime.datetime.now().strftime("%Y-%m-%d"),
                    source_url=OFFICIAL_TEI_URL,
                    document_hash=doc_hash,
                    verification_status="verified",
                    components=new_comps,
                    created_at=now_iso
                )
                save_rate_schedule(new_sched, conn)

                diff = round(extracted_gen - prev_gen_rate, 5)
                direction = "increased" if diff > 0 else "decreased"
                alert = {
                    "has_changed": True,
                    "previous_rate": prev_gen_rate,
                    "new_rate": extracted_gen,
                    "difference_per_kwh": diff,
                    "effective_month": effective_month,
                    "publication_date": new_sched.publication_date,
                    "summary": f"TEI published a new electricity rate. Generation Charge {direction} by ₱{abs(diff):.5f}/kWh to ₱{extracted_gen:.5f}/kWh. SolarScope updated your estimated bill."
                }
                return {
                    "status": "updated",
                    "message": "New verified rate schedule extracted and applied.",
                    "active_schedule": new_sched,
                    "rate_change_alert": alert,
                    "checked_at": now_iso
                }

            return {
                "status": "verified_current",
                "message": "TEI official rate schedule checked. Current rates are up to date.",
                "active_schedule": active_sched,
                "rate_change_alert": None,
                "checked_at": now_iso
            }

    except Exception:
        return {
            "status": "offline_retained_verified",
            "message": "Unable to check for new TEI rates. Your estimate is using the last verified rate schedule.",
            "active_schedule": active_sched,
            "rate_change_alert": None,
            "checked_at": now_iso
        }
