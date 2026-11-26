import datetime
import re
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.billing.tariff_models import BillForecastResponse, TEIBillingProfile
from backend.app.billing.billing_profile import compute_cycle_dates
from backend.app.billing.bill_forecaster import forecast_tei_bill
from backend.app.billing.tei_rate_monitor import get_rate_schedule_for_month
from backend.app.metrics.time_utils import resolve_zoneinfo

def resolve_estimate_month(forecast: BillForecastResponse, profile: TEIBillingProfile) -> str:
    if profile.billing_month and re.match(r"^\d{4}-\d{2}$", profile.billing_month.strip()):
        return profile.billing_month.strip()
    return (forecast.billing_cycle_start or "")[:7]

def upsert_monthly_estimate(
    forecast: BillForecastResponse,
    profile: TEIBillingProfile,
    conn,
    project_id: str = "default"
) -> bool:
    if int(forecast.days_remaining) > 0:
        return False

    billing_month = resolve_estimate_month(forecast, profile)
    if not billing_month or not re.match(r"^\d{4}-\d{2}$", billing_month):
        return False

    if float(forecast.actual_imported_kwh) <= 0.0 and float(forecast.expected_estimate.total_projected_kwh) <= 0.0 and float(forecast.solar_savings.get("household_total_demand_kwh", 0.0)) <= 0.0:
        return False

    est_id = f"est-{project_id}-{billing_month}"
    lower_amt = round(float(forecast.lower_estimate.estimated_total_amount), 2)
    expected_amt = round(float(forecast.expected_estimate.estimated_total_amount), 2)
    higher_amt = round(float(forecast.higher_estimate.estimated_total_amount), 2)
    actual_kwh = round(float(forecast.actual_imported_kwh), 2)
    projected_kwh = round(float(forecast.expected_estimate.total_projected_kwh), 2)
    gen_charge = round(float(forecast.active_generation_charge), 5)
    savings_pesos = round(float(forecast.solar_savings.get("savings_pesos", 0.0)), 2)
    savings_pct = round(float(forecast.solar_savings.get("savings_percentage", 0.0)), 1)
    eff_rate = round(float(forecast.expected_estimate.statement.effective_average_rate_per_kwh), 4)
    is_completed = 1

    existing = conn.execute(
        "SELECT * FROM tei_monthly_estimates WHERE project_id = ? AND billing_month = ?",
        (project_id, billing_month)
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
        """INSERT INTO tei_monthly_estimates (
               id, project_id, billing_month, billing_cycle_start, billing_cycle_end,
               customer_class, rate_effective_month, generation_charge,
               actual_imported_kwh, projected_kwh, lower_estimate_amount,
               expected_estimate_amount, higher_estimate_amount,
               solar_savings_pesos, savings_percentage, effective_average_rate,
               is_completed_cycle, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(project_id, billing_month) DO UPDATE SET
               billing_cycle_start = excluded.billing_cycle_start,
               billing_cycle_end = excluded.billing_cycle_end,
               customer_class = excluded.customer_class,
               rate_effective_month = excluded.rate_effective_month,
               generation_charge = excluded.generation_charge,
               actual_imported_kwh = excluded.actual_imported_kwh,
               projected_kwh = excluded.projected_kwh,
               lower_estimate_amount = excluded.lower_estimate_amount,
               expected_estimate_amount = excluded.expected_estimate_amount,
               higher_estimate_amount = excluded.higher_estimate_amount,
               solar_savings_pesos = excluded.solar_savings_pesos,
               savings_percentage = excluded.savings_percentage,
               effective_average_rate = excluded.effective_average_rate,
               is_completed_cycle = excluded.is_completed_cycle,
               updated_at = excluded.updated_at""",
        (
            est_id,
            project_id,
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

def sync_past_monthly_estimates(
    records: List[CanonicalRecord],
    profile: TEIBillingProfile,
    conn,
    check_state: Dict[str, Any],
    project_id: str = "default",
    timezone: str = "Asia/Manila"
) -> bool:
    tz = resolve_zoneinfo(timezone)
    today_date = datetime.datetime.now(tz).date()
    today_str = today_date.strftime("%Y-%m-%d")

    del_res = conn.execute(
        "DELETE FROM tei_monthly_estimates WHERE project_id = ? AND (is_completed_cycle = 0 OR billing_cycle_end > ?)",
        (project_id, today_str)
    )
    changed = del_res.rowcount > 0

    if not records:
        return changed

    observed_days = sorted({r.timestamp[:10] for r in records if r.timestamp_valid and r.timestamp and len(r.timestamp) >= 10})
    if not observed_days:
        return changed

    min_dt = datetime.date.fromisoformat(observed_days[0])
    cycle_day = max(1, min(31, int(profile.billing_cycle_day or 25)))
    cur_start, _ = compute_cycle_dates(cycle_day, min_dt, timezone=timezone)
    iter_year, iter_month = cur_start.year, cur_start.month

    while True:
        bm = f"{iter_year:04d}-{iter_month:02d}"
        c_start, c_end = compute_cycle_dates(cycle_day, billing_month=bm, timezone=timezone)
        if c_end > today_date:
            break

        c_start_str = c_start.strftime("%Y-%m-%d")
        c_end_str = c_end.strftime("%Y-%m-%d")
        cycle_total_days = max(1, (c_end - c_start).days)
        days_in_cycle = sum(1 for d in observed_days if c_start_str <= d < c_end_str)

        if days_in_cycle >= max(7, cycle_total_days // 2):
            is_explicit_month = (profile.billing_month == bm)
            past_prof = profile.model_copy(update={
                "billing_month": bm,
                "cycle_start_date": c_start_str,
                "cycle_end_date": c_end_str,
                "prev_meter_reading": profile.prev_meter_reading if is_explicit_month else None,
                "latest_meter_reading": profile.latest_meter_reading if is_explicit_month else None,
                "previous_unpaid_balance": profile.previous_unpaid_balance if is_explicit_month else 0.0,
                "payments_received": profile.payments_received if is_explicit_month else 0.0,
            })
            sched = get_rate_schedule_for_month(conn, customer_class=profile.customer_class, billing_month=bm, project_id=project_id)
            past_forecast = forecast_tei_bill(records, sched, past_prof, check_state, timezone=timezone)
            if upsert_monthly_estimate(past_forecast, past_prof, conn, project_id=project_id):
                changed = True

        iter_month += 1
        if iter_month > 12:
            iter_month = 1
            iter_year += 1

    return changed

def get_monthly_estimates(conn, project_id: str = "default", timezone: str = "Asia/Manila") -> List[Dict[str, Any]]:
    tz = resolve_zoneinfo(timezone)
    today_str = datetime.datetime.now(tz).date().strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT * FROM tei_monthly_estimates
           WHERE project_id = ? AND is_completed_cycle = 1 AND billing_cycle_end <= ?
           ORDER BY billing_month DESC""",
        (project_id, today_str)
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
            "is_estimate": True,
            "updated_at": r["updated_at"]
        }
        for r in rows
    ]

def delete_monthly_estimate(estimate_id: str, conn, project_id: str = "default") -> bool:
    res = conn.execute(
        "DELETE FROM tei_monthly_estimates WHERE project_id = ? AND (id = ? OR billing_month = ?)",
        (project_id, estimate_id, estimate_id)
    )
    return res.rowcount > 0
