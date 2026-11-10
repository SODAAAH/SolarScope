import pytest
from backend.app.ingestion.models import CanonicalRecord
from backend.app.ingestion.file_hasher import compute_file_hash
from backend.app.ingestion.conflict_detector import detect_record_conflicts, resolve_and_merge_records

def test_file_hasher():
    b1 = b"Sample File Contents 123"
    b2 = b"Sample File Contents 123"
    b3 = b"Different File Contents"
    h1 = compute_file_hash(b1)
    h2 = compute_file_hash(b2)
    h3 = compute_file_hash(b3)
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64

def test_detect_record_conflicts_no_overlap():
    recs_a = [
        CanonicalRecord(timestamp="2025-01-15 00:00:00", pv_power_kw=0.0, load_power_kw=1.0, grid_power_kw=1.0),
        CanonicalRecord(timestamp="2025-01-15 01:00:00", pv_power_kw=0.0, load_power_kw=1.0, grid_power_kw=1.0)
    ]
    recs_b = [
        CanonicalRecord(timestamp="2025-01-16 00:00:00", pv_power_kw=0.0, load_power_kw=1.2, grid_power_kw=1.2),
        CanonicalRecord(timestamp="2025-01-16 01:00:00", pv_power_kw=0.0, load_power_kw=1.2, grid_power_kw=1.2)
    ]
    res = detect_record_conflicts(recs_a, recs_b)
    assert res["has_overlap"] is False
    assert res["conflicting_points"] == 0

def test_detect_record_conflicts_with_overlap():
    recs_a = [
        CanonicalRecord(timestamp="2025-01-15 12:00:00", pv_power_kw=3.0, load_power_kw=1.5, grid_power_kw=0.0),
        CanonicalRecord(timestamp="2025-01-15 13:00:00", pv_power_kw=3.5, load_power_kw=1.8, grid_power_kw=0.0)
    ]
    recs_b = [
        CanonicalRecord(timestamp="2025-01-15 12:00:00", pv_power_kw=2.0, load_power_kw=1.5, grid_power_kw=0.0),
        CanonicalRecord(timestamp="2025-01-15 14:00:00", pv_power_kw=2.5, load_power_kw=1.5, grid_power_kw=0.0)
    ]
    res = detect_record_conflicts(recs_a, recs_b)
    assert res["has_overlap"] is True
    assert res["conflicting_points"] == 1
    assert res["conflicts"][0]["pv_diff_kw"] == 1.0

def test_resolve_and_merge_records():
    recs_a = [
        CanonicalRecord(timestamp="2025-01-15 12:00:00", pv_power_kw=3.0, load_power_kw=1.0),
        CanonicalRecord(timestamp="2025-01-15 13:00:00", pv_power_kw=3.5, load_power_kw=1.0)
    ]
    recs_b = [
        CanonicalRecord(timestamp="2025-01-15 13:00:00", pv_power_kw=9.9, load_power_kw=9.9),
        CanonicalRecord(timestamp="2025-01-15 14:00:00", pv_power_kw=2.0, load_power_kw=1.0)
    ]
    merged_keep = resolve_and_merge_records(recs_a, recs_b, policy="KEEP_EXISTING")
    assert len(merged_keep) == 3
    rec_13 = next(r for r in merged_keep if r.timestamp == "2025-01-15 13:00:00")
    assert rec_13.pv_power_kw == 3.5

    merged_replace = resolve_and_merge_records(recs_a, recs_b, policy="REPLACE_OLDER")
    rec_13_rep = next(r for r in merged_replace if r.timestamp == "2025-01-15 13:00:00")
    assert rec_13_rep.pv_power_kw == 9.9
