import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["time_format"] == "12-hour"

def test_load_sample_and_sources():
    res = client.post("/api/datasets/load_sample")
    assert res.status_code == 200
    data = res.json()
    dataset_id = data["dataset_id"]
    assert dataset_id is not None
    assert data["filename"] == "Oct 21.xlsx"

    sources_res = client.get("/api/sources")
    assert sources_res.status_code == 200
    sources = sources_res.json()
    assert len(sources) >= 1
    found = next((s for s in sources if s["id"] == dataset_id), None)
    assert found is not None

def test_historical_endpoints_with_sample():
    sample_res = client.post("/api/datasets/load_sample")
    dataset_id = sample_res.json()["dataset_id"]

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
    assert "hours" in hm
    assert hm["hours"][0] == "12 AM"

    avg_res = client.get(f"/api/historical/averages?dataset_id={dataset_id}")
    assert avg_res.status_code == 200
    avgs = avg_res.json()
    assert "time_weighted_avg_pv_power_kw" in avgs
    assert "arithmetic_mean_pv_power_kw" in avgs
    assert "mean_daily_pv_energy_kwh" in avgs

    ww_res = client.get(f"/api/historical/weekdays_vs_weekends?dataset_id={dataset_id}")
    assert ww_res.status_code == 200
    ww = ww_res.json()
    assert "weekday_hourly_load_kw" in ww
    assert len(ww["hours_12h"]) == 24

def test_report_generation():
    sample_res = client.post("/api/datasets/load_sample")
    dataset_id = sample_res.json()["dataset_id"]

    pdf_res = client.post(f"/api/datasets/{dataset_id}/reports/generate", json={"report_type": "pdf"})
    assert pdf_res.status_code == 200
    pdf_info = pdf_res.json()
    assert pdf_info["report_type"] == "pdf"
    assert "download_url" in pdf_info

    down_res = client.get(pdf_info["download_url"])
    assert down_res.status_code == 200
    assert len(down_res.content) > 1000

    json_res = client.post(f"/api/datasets/{dataset_id}/reports/generate", json={"report_type": "json"})
    assert json_res.status_code == 200
    assert json_res.json()["report_type"] == "json"

    xlsx_res = client.post(f"/api/datasets/{dataset_id}/reports/generate", json={"report_type": "xlsx"})
    assert xlsx_res.status_code == 200
    assert xlsx_res.json()["report_type"] == "xlsx"

