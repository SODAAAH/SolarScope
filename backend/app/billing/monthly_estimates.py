import datetime
import re
from typing import List, Dict, Any
from backend.app.billing.tariff_models import BillForecastResponse, TEIBillingProfile

def resolve_estimate_month(forecast: BillForecastResponse, profile: TEIBillingProfile) -> str:
    if profile.billing_month and re.match(r"^\d{4}-\d{2}$", profile.billing_month.strip()):
        return profile.billing_month.strip()
    return (forecast.billing_cycle_start or "")[:7]

def upsert_monthly_estimate(forecast: BillForecastResponse, profile: TEIBillingProfile, conn) -> bool:
    billing_month = resolve_estimate_month(forecast, profile)
    if not billing_month or not re.match(r"^\d{4}-\d{2}$", billing_month):
        return False

    est_id = f"est-default-{billing_month}"
    lower_amt = round(float(forecast.lower_estimate.estimated_total_amount), 2)
    expected_amt = round(float(forecast.expected_estimate.estimated_total_amount), 2)
    higher_amt = round(float(forecast.higher_estimate.estimated_total_amount), 2)
    actual_kwh = round(float(forecast.actual_imported_kwh), 2)
    projected_kwh = round(float(forecast.expected_estimate.total_projected_kwh), 2)
    gen_charge = round(float(forecast.active_generation_charge), 5)
    savings_pesos = round(float(forecast.solar_savings.get("savings_pesos", 0.0)), 2)
    savings_pct = round(float(forecast.solar_savings.get("savings_percentage", 0.0)), 1)
    eff_rate = round(float(forecast.expected_estimate.statement.effective_average_rate_per_kwh), 4)
    is_completed = 1 if int(forecast.days_remaining) == 0 else 0

    existing = conn.execute(
        "SELECT * FROM tei_monthly_estimates WHERE project_id = 'default' AND billing_month = ?",
        (billing_month,)
    ).fetchone()

    if existing:
        same = (
            existing["billing_cycle_start"] == forecast.billing_cycle_start
            and existing["billing_cycle_end"] == forecast.billing_cycle_end
            and existing["customer_class"] == profile.customer_class
            and existing["rate_effective_month"] == forecast.active_rate_effective_month
            and abs(float(existing["generation_charge"]) - gen_charge) < 1e-5
            and abs(float(existing["actual_imported_kwh"]) - actual_kwh) < 0.01
            and abs(float(existing["projected_kwh"]) - projected_kwh) < 0.01
            and abs(float(existing["expected_estimate_amount"]) - expected_amt) < 0.01
            and abs(float(existing["lower_estimate_amount"]) - lower_amt) < 0.01
            and abs(float(existing["higher_estimate_amount"]) - higher_amt) < 0.01
            and abs(float(existing["solar_savings_pesos"]) - savings_pesos) < 0.01
            and int(existing["is_completed_cycle"] or 0) == is_completed
        )
        if same:
            return False

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO tei_monthly_estimates (
               id, project_id, billing_month, billing_cycle_start, billing_cycle_end,
               customer_class, rate_effective_month, generation_charge,
               actual_imported_kwh, projected_kwh, lower_estimate_amount,
               expected_estimate_amount, higher_estimate_amount,
               solar_savings_pesos, savings_percentage, effective_average_rate,
               is_completed_cycle, updated_at
           ) VALUES (?, 'default', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            est_id,
            billing_month,
            forecast.billing_cycle_start,
            forecast.billing_cycle_end,
            profile.customer_class,
            forecast.active_rate_effective_month,
            gen_charge,
            actual_kwh,
            projected_kwh,
            lower_amt,
            expected_amt,
            higher_amt,
            savings_pesos,
            savings_pct,
            eff_rate,
            is_completed,
            now_iso
        )
    )
    return True

def get_monthly_estimates(conn) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM tei_monthly_estimates WHERE project_id = 'default' ORDER BY billing_month DESC"
    ).fetchall()
    return [
        {
            "id": r["id"],
            "billing_month": r["billing_month"],
            "billing_cycle_start": r["billing_cycle_start"],
            "billing_cycle_end": r["billing_cycle_end"],
            "customer_class": r["customer_class"],
            "rate_effective_month": r["rate_effective_month"],
            "generation_charge": float(r["generation_charge"]),
            "actual_imported_kwh": float(r["actual_imported_kwh"]),
            "projected_kwh": float(r["projected_kwh"]),
            "lower_estimate_amount": float(r["lower_estimate_amount"]),
            "expected_estimate_amount": float(r["expected_estimate_amount"]),
            "higher_estimate_amount": float(r["higher_estimate_amount"]),
            "solar_savings_pesos": float(r["solar_savings_pesos"]),
            "savings_percentage": float(r["savings_percentage"]),
            "effective_average_rate": float(r["effective_average_rate"]),
            "is_completed_cycle": bool(r["is_completed_cycle"]),
            "updated_at": r["updated_at"]
        }
        for r in rows
    ]

def delete_monthly_estimate(estimate_id: str, conn) -> bool:
    res = conn.execute("DELETE FROM tei_monthly_estimates WHERE id = ? OR billing_month = ?", (estimate_id, estimate_id))
    return res.rowcount > 0
