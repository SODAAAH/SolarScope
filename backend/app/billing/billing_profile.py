import datetime
import json
from typing import Optional
from backend.app.billing.tariff_models import TEIBillingProfile

def get_billing_profile(conn) -> TEIBillingProfile:
    row = conn.execute("SELECT * FROM tei_billing_profiles WHERE project_id = 'default'").fetchone()
    if row:
        return TEIBillingProfile(
            customer_class=row["customer_class"] or "Residential",
            billing_cycle_day=row["billing_cycle_day"] or 18,
            cycle_start_date=row["cycle_start_date"],
            cycle_end_date=row["cycle_end_date"],
            prev_meter_reading=row["prev_meter_reading"],
            latest_meter_reading=row["latest_meter_reading"],
            meter_reading_date=row["meter_reading_date"],
            connection_type=row["connection_type"] or "behind_meter",
            is_lifeline_eligible=bool(row["is_lifeline_eligible"]),
            is_senior_eligible=bool(row["is_senior_eligible"]),
            is_prompt_payment_eligible=bool(row["is_prompt_payment_eligible"]),
            previous_unpaid_balance=row["previous_unpaid_balance"] or 0.0,
            payments_received=row["payments_received"] or 0.0,
            forecast_method=row["forecast_method"] or "7day",
            updated_at=row["updated_at"]
        )

    now = datetime.datetime.now()
    cycle_day = 18
    if now.day >= cycle_day:
        start_dt = datetime.date(now.year, now.month, cycle_day)
        next_month = now.month + 1 if now.month < 12 else 1
        next_year = now.year if now.month < 12 else now.year + 1
        end_dt = datetime.date(next_year, next_month, cycle_day)
    else:
        prev_month = now.month - 1 if now.month > 1 else 12
        prev_year = now.year if now.month > 1 else now.year - 1
        start_dt = datetime.date(prev_year, prev_month, cycle_day)
        end_dt = datetime.date(now.year, now.month, cycle_day)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    default_profile = TEIBillingProfile(
        customer_class="Residential",
        billing_cycle_day=cycle_day,
        cycle_start_date=start_dt.strftime("%Y-%m-%d"),
        cycle_end_date=end_dt.strftime("%Y-%m-%d"),
        connection_type="behind_meter",
        is_lifeline_eligible=False,
        is_senior_eligible=False,
        is_prompt_payment_eligible=False,
        previous_unpaid_balance=0.0,
        payments_received=0.0,
        forecast_method="7day",
        updated_at=now_iso
    )
    save_billing_profile(default_profile, conn)
    return default_profile

def save_billing_profile(profile: TEIBillingProfile, conn) -> None:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO tei_billing_profiles
           (id, project_id, customer_class, billing_cycle_day, cycle_start_date, cycle_end_date,
            prev_meter_reading, latest_meter_reading, meter_reading_date, connection_type,
            is_lifeline_eligible, is_senior_eligible, is_prompt_payment_eligible,
            previous_unpaid_balance, payments_received, forecast_method, updated_at)
           VALUES ('profile-default', 'default', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            profile.customer_class,
            profile.billing_cycle_day,
            profile.cycle_start_date,
            profile.cycle_end_date,
            profile.prev_meter_reading,
            profile.latest_meter_reading,
            profile.meter_reading_date,
            profile.connection_type,
            1 if profile.is_lifeline_eligible else 0,
            1 if profile.is_senior_eligible else 0,
            1 if profile.is_prompt_payment_eligible else 0,
            profile.previous_unpaid_balance,
            profile.payments_received,
            profile.forecast_method,
            now_iso
        )
    )
