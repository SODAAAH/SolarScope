import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.billing.tariff_models import TEIRateSchedule, TEIBillingProfile
from backend.app.billing.bill_calculator import calculate_statement_of_account
from backend.app.metrics.integrator import integrate_power_series

def calculate_billing_progress_series(
    records: List[CanonicalRecord],
    schedule: TEIRateSchedule,
    profile: TEIBillingProfile
) -> Dict[str, Any]:
    cycle_day = profile.billing_cycle_day or 18
    now = datetime.datetime.now()

    if profile.cycle_start_date and profile.cycle_end_date:
        start_date = datetime.datetime.strptime(profile.cycle_start_date, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(profile.cycle_end_date, "%Y-%m-%d").date()
    else:
        if now.day >= cycle_day:
            start_date = datetime.date(now.year, now.month, cycle_day)
            next_month = now.month + 1 if now.month < 12 else 1
            next_year = now.year if now.month < 12 else now.year + 1
            end_date = datetime.date(next_year, next_month, cycle_day)
        else:
            prev_month = now.month - 1 if now.month > 1 else 12
            prev_year = now.year if now.month > 1 else now.year - 1
            start_date = datetime.date(prev_year, prev_month, cycle_day)
            end_date = datetime.date(now.year, now.month, cycle_day)

    today_date = now.date()

    daily_imports: Dict[str, float] = {}
    day_records_map: Dict[str, List[CanonicalRecord]] = {}
    for r in records:
        day_str = r.timestamp[:10]
        if day_str not in day_records_map:
            day_records_map[day_str] = []
        day_records_map[day_str].append(r)

    for day_str, recs in day_records_map.items():
        if len(recs) < 2:
            continue
        ts_list = [r.timestamp for r in recs]
        daily_imports[day_str] = integrate_power_series(ts_list, [max(0.0, r.grid_power_kw) for r in recs])[0]

    all_sorted_days = sorted(daily_imports.keys())
    sample_days = all_sorted_days[-7:] if len(all_sorted_days) >= 7 else all_sorted_days
    sample_values = [daily_imports[d] for d in sample_days] if sample_days else [7.5]
    avg_daily_rate = sum(sample_values) / len(sample_values) if sample_values else 7.5

    series_days = []
    curr_dt = start_date
    cum_kwh_actual = 0.0
    cum_kwh_expected = 0.0

    test_soa_100 = calculate_statement_of_account(100.0, schedule, profile, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    eff_rate = test_soa_100.effective_average_rate_per_kwh if test_soa_100.effective_average_rate_per_kwh > 0 else 11.85

    while curr_dt <= end_date:
        d_str = curr_dt.strftime("%Y-%m-%d")
        is_past_or_today = (curr_dt <= today_date)

        if is_past_or_today:
            day_kwh = daily_imports.get(d_str, avg_daily_rate if d_str in daily_imports else 0.0)
            cum_kwh_actual += day_kwh
            cum_kwh_expected = cum_kwh_actual
            cost_actual = round(cum_kwh_actual * eff_rate, 2)
            cost_expected = cost_actual
            series_days.append({
                "date": d_str,
                "day_label": curr_dt.strftime("%b %d"),
                "is_actual": True,
                "is_today": (curr_dt == today_date),
                "is_meter_reading": (curr_dt == end_date),
                "daily_kwh": round(day_kwh, 2),
                "cumulative_kwh_actual": round(cum_kwh_actual, 2),
                "cumulative_cost_actual": cost_actual,
                "cumulative_kwh_expected": round(cum_kwh_expected, 2),
                "cumulative_cost_expected": cost_expected
            })
        else:
            cum_kwh_expected += avg_daily_rate
            cost_expected = round(cum_kwh_expected * eff_rate, 2)
            series_days.append({
                "date": d_str,
                "day_label": curr_dt.strftime("%b %d"),
                "is_actual": False,
                "is_today": False,
                "is_meter_reading": (curr_dt == end_date),
                "daily_kwh": round(avg_daily_rate, 2),
                "cumulative_kwh_actual": None,
                "cumulative_cost_actual": None,
                "cumulative_kwh_expected": round(cum_kwh_expected, 2),
                "cumulative_cost_expected": cost_expected
            })

        curr_dt += datetime.timedelta(days=1)

    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "today_date": today_date.strftime("%Y-%m-%d"),
        "average_daily_kwh": round(avg_daily_rate, 2),
        "timeline": series_days
    }
