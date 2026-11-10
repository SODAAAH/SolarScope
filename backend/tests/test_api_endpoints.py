import io
import csv
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def _sample_csv_bytes():
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Timestamp", "Solar Power (kW)", "Load Power (kW)", "Battery Power (kW)", "Grid Power (kW)", "SOC (%)"])
    for h in range(24):
        ts = f"2025-01-15 {h:02d}:00:00"
        pv = 3.5 if 8 <= h <= 15 else 0.0
        load = 1.2
        batt = -(pv - load) if pv > load else 0.8
        grid = 0.0 if pv > 0 else 0.4
        soc = 75.0 if 9 <= h <= 17 else 45.0
        writer.writerow([ts, pv, load, batt, grid, soc])
    writer.writerow(["2025-01-16 00:00:00", 0.0, 1.2, 0.8, 0.4, 42.0])
    return buf.getvalue().encode("utf-8")

def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["time_format"] == "12-hour"

def test_sample_endpoint_removed():
    res = client.post("/api/datasets/load_sample")
    assert res.status_code in (404, 405)

def test_unconfigured_defaults():
    settings_res = client.get("/api/settings")
    assert settings_res.status_code == 200
    settings_data = settings_res.json()
    assert "station_name" in settings_data

    flow_res = client.get("/api/deye/live_flow")
    assert flow_res.status_code == 200
    flow_data = flow_res.json()
    assert flow_data["data_source"] in ("offline", "live", "cached", "demo")

    weather_res = client.get("/api/weather/intelligence")
    assert weather_res.status_code == 200

    prof_res = client.get("/api/billing/profile")
    assert prof_res.status_code == 200
    assert 1 <= prof_res.json()["billing_cycle_day"] <= 31

def test_upload_and_historical_and_report_endpoints():
    csv_bytes = _sample_csv_bytes()
    upload_res = client.post(
        "/api/datasets/upload_batch",
        files=[("files", ("test_station_day.csv", csv_bytes, "text/csv"))]
    )
    assert upload_res.status_code == 200
    up_data = upload_res.json()
    assert up_data["total_uploaded"] == 1
    dataset_id = up_data["files"][0]["dataset_id"]

    try:
        sources_res = client.get("/api/sources")
        assert sources_res.status_code == 200
        assert any(s["id"] == dataset_id for s in sources_res.json())

        daily_res = client.get(f"/api/historical/daily?dataset_id={dataset_id}")
        assert daily_res.status_code == 200
        daily = daily_res.json()
        assert len(daily) >= 1
        d0 = daily[0]
        assert "peak_pv_time_12h" in d0
        assert "peak_load_time_12h" in d0
        assert "peak_grid_time_12h" in d0

        hourly_res = client.get(f"/api/historical/hourly_profile?dataset_id={dataset_id}")
        assert hourly_res.status_code == 200
        profiles = hourly_res.json()
        assert len(profiles) == 24
        assert profiles[0]["hour_label_12h"] == "12 AM"
        assert profiles[12]["hour_label_12h"] == "12 PM"

        heatmap_res = client.get(f"/api/historical/heatmap?dataset_id={dataset_id}&metric=pv_power_kw")
        assert heatmap_res.status_code == 200
        hm = heatmap_res.json()
        assert "matrix" in hm
        assert hm["hours"][0] == "12 AM"

        avg_res = client.get(f"/api/historical/averages?dataset_id={dataset_id}")
        assert avg_res.status_code == 200
        assert "time_weighted_avg_pv_power_kw" in avg_res.json()

        ww_res = client.get(f"/api/historical/weekdays_vs_weekends?dataset_id={dataset_id}")
        assert ww_res.status_code == 200
        assert len(ww_res.json()["hours_12h"]) == 24

        pdf_res = client.post(f"/api/datasets/{dataset_id}/reports/generate", json={"report_type": "pdf"})
        assert pdf_res.status_code == 200
        pdf_info = pdf_res.json()
        assert pdf_info["report_type"] == "pdf"
        down_res = client.get(pdf_info["download_url"])
        assert down_res.status_code == 200
        assert len(down_res.content) > 1000

        json_res = client.post(f"/api/datasets/{dataset_id}/reports/generate", json={"report_type": "json"})
        assert json_res.status_code == 200

        xlsx_res = client.post(f"/api/datasets/{dataset_id}/reports/generate", json={"report_type": "xlsx"})
        assert xlsx_res.status_code == 200
    finally:
        client.delete(f"/api/sources/{dataset_id}")
