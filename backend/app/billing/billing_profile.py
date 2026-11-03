import calendar
import datetime
from typing import Optional, Tuple
from backend.app.billing.tariff_models import TEIBillingProfile

def compute_cycle_dates(cycle_day: int, ref_date: Optional[datetime.date] = None) -> Tuple[datetime.date, datetime.date]:
    if ref_date is None:
        tz_manila = datetime.timezone(datetime.timedelta(hours=8))
        ref_date = datetime.datetime.now(tz_manila).date()

    cycle_day = max(1, min(31, int(cycle_day or 25)))
    y = ref_date.year
    m = ref_date.month
    d = ref_date.day

    def make_date(year: int, month: int, day: int) -> datetime.date:
        max_d = calendar.monthrange(year, month)[1]
        return datetime.date(year, month, min(day, max_d))

    if d >= cycle_day:
        start_dt = make_date(y, m, cycle_day)
        next_m = m + 1 if m < 12 else 1
        next_y = y if m < 12 else y + 1
        end_dt = make_date(next_y, next_m, cycle_day)
    else:
        prev_m = m - 1 if m > 1 else 12
        prev_y = y if m > 1 else y - 1
        start_dt = make_date(prev_y, prev_m, cycle_day)
        end_dt = make_date(y, m, cycle_day)

    return start_dt, end_dt

def get_billing_profile(conn) -> TEIBillingProfile:
    row = conn.execute("SELECT * FROM tei_billing_profiles WHERE project_id = 'default'").fetchone()
    if row:
        cycle_day = max(1, min(31, int(row["billing_cycle_day"] or 25)))
        start_dt, end_dt = compute_cycle_dates(cycle_day)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        if row["cycle_start_date"] != start_str or row["cycle_end_date"] != end_str:
            conn.execute(
                "UPDATE tei_billing_profiles SET cycle_start_date = ?, cycle_end_date = ? WHERE project_id = 'default'",
                (start_str, end_str)
            )
            conn.commit()

        return TEIBillingProfile(
            customer_class=row["customer_class"] or "Residential",
            billing_cycle_day=cycle_day,
            cycle_start_date=start_str,
            cycle_end_date=end_str,
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

    start_dt, end_dt = compute_cycle_dates(25)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    default_profile = TEIBillingProfile(
        customer_class="Residential",
        billing_cycle_day=25,
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
    cycle_day = max(1, min(31, int(profile.billing_cycle_day or 25)))
    start_dt, end_dt = compute_cycle_dates(cycle_day)
    profile.billing_cycle_day = cycle_day
    profile.cycle_start_date = start_dt.strftime("%Y-%m-%d")
    profile.cycle_end_date = end_dt.strftime("%Y-%m-%d")

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
