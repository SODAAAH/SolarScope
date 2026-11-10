import pytest
from backend.app.ingestion.models import CanonicalRecord
from backend.app.aggregation.historical import (
    calculate_daily_summaries,
    calculate_weekly_summaries,
    calculate_monthly_summaries,
    calculate_averages_comparison
)

def test_daily_summaries():
    records = []
    for h in range(24):
        h_str = f"{h:02d}:00:00"
        records.append(CanonicalRecord(
            timestamp=f"2025-01-15 {h_str}",
            pv_power_kw=4.0 if 8 <= h <= 16 else 0.0,
            load_power_kw=1.5,
            grid_power_kw=0.5 if h < 6 else 0.0,
            battery_power_kw=-1.0 if 8 <= h <= 12 else 0.5,
            soc_percent=50.0
        ))
    records.append(CanonicalRecord(
        timestamp="2025-01-16 00:00:00",
        pv_power_kw=0.0,
        load_power_kw=1.5,
        grid_power_kw=0.5,
        battery_power_kw=0.5,
        soc_percent=45.0
    ))

    daily = calculate_daily_summaries(records)
    assert len(daily) == 2
    d1 = daily[0]
    assert d1["date"] == "2025-01-15"
    assert d1["status"] == "COMPLETE"
    assert d1["pv_kwh"] > 0
    assert d1["load_kwh"] > 0
    assert "peak_pv_time_12h" in d1

def test_weekly_and_monthly_summaries():
    daily_summaries = [
        {"date": "2025-01-15", "status": "COMPLETE", "pv_kwh": 20.0, "load_kwh": 30.0, "grid_import_kwh": 10.0},
        {"date": "2025-01-16", "status": "COMPLETE", "pv_kwh": 25.0, "load_kwh": 28.0, "grid_import_kwh": 8.0},
        {"date": "2025-01-17", "status": "COMPLETE", "pv_kwh": 22.0, "load_kwh": 31.0, "grid_import_kwh": 9.0}
    ]
    weeks = calculate_weekly_summaries(daily_summaries)
    assert len(weeks) == 1
    assert weeks[0]["days_observed"] == 3
    assert weeks[0]["total_pv_kwh"] == 67.0
    assert weeks[0]["mean_daily_pv_kwh"] == round(67.0 / 3, 2)

    months = calculate_monthly_summaries(daily_summaries)
    assert len(months) == 1
    assert months[0]["month"] == "2025-01"
    assert months[0]["total_pv_kwh"] == 67.0
    assert months[0]["best_day_date"] == "2025-01-16"

def test_averages_comparison():
    records = [
        CanonicalRecord(timestamp="2025-01-15 00:00:00", pv_power_kw=0.0, load_power_kw=1.0),
        CanonicalRecord(timestamp="2025-01-15 12:00:00", pv_power_kw=4.0, load_power_kw=2.0),
        CanonicalRecord(timestamp="2025-01-15 23:59:59", pv_power_kw=0.0, load_power_kw=1.0)
    ]
    daily = [
        {"date": "2025-01-15", "status": "COMPLETE", "pv_kwh": 24.0, "load_kwh": 30.0}
    ]
    comp = calculate_averages_comparison(records, daily)
    assert "time_weighted_avg_pv_power_kw" in comp
    assert "arithmetic_mean_pv_power_kw" in comp
    assert "mean_daily_pv_energy_kwh" in comp
    assert "median_daily_pv_energy_kwh" in comp
