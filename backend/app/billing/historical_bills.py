import uuid
import datetime
from typing import List, Dict, Any, Optional

def get_historical_bills_summary(conn) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM tei_historical_bills WHERE project_id = 'default' ORDER BY billing_period_start DESC"
    ).fetchall()

    results = []
    for r in rows:
        actual = r["actual_amount_due"]
        predicted = r["predicted_amount_due"]
        var_pesos = round(predicted - actual, 2) if predicted is not None else None
        var_pct = round((var_pesos / actual) * 100.0, 1) if (var_pesos is not None and actual > 0) else None
        acc_pct = max(0.0, round(100.0 - abs(var_pct), 1)) if var_pct is not None else None

        results.append({
            "id": r["id"],
            "billing_period_start": r["billing_period_start"],
            "billing_period_end": r["billing_period_end"],
            "billed_kwh": r["billed_kwh"],
            "actual_amount_due": actual,
            "predicted_amount_due": predicted,
            "variance_pesos": var_pesos,
            "variance_percent": var_pct,
            "accuracy_percent": acc_pct,
            "notes": r["notes"] or "",
            "created_at": r["created_at"]
        })
    return results

def insert_historical_bill(
    billing_period_start: str,
    billing_period_end: str,
    billed_kwh: float,
    actual_amount_due: float,
    predicted_amount_due: Optional[float],
    notes: str,
    conn
) -> Dict[str, Any]:
    bill_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO tei_historical_bills
           (id, project_id, billing_period_start, billing_period_end, billed_kwh, actual_amount_due, predicted_amount_due, notes, created_at)
           VALUES (?, 'default', ?, ?, ?, ?, ?, ?, ?)""",
        (
            bill_id,
            billing_period_start,
            billing_period_end,
            billed_kwh,
            actual_amount_due,
            predicted_amount_due,
            notes,
            now_iso
        )
    )
    return {
        "id": bill_id,
        "billing_period_start": billing_period_start,
        "billing_period_end": billing_period_end,
        "billed_kwh": billed_kwh,
        "actual_amount_due": actual_amount_due,
        "predicted_amount_due": predicted_amount_due
    }

def remove_historical_bill(bill_id: str, conn) -> bool:
    res = conn.execute("DELETE FROM tei_historical_bills WHERE id = ?", (bill_id,))
    return res.rowcount > 0
