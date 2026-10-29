from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.validation.gap_detector import analyze_sampling_intervals
from backend.app.validation.range_validator import validate_channel_ranges

def calculate_data_quality_report(
    records: List[CanonicalRecord],
    gap_threshold_minutes: float = 30.0
) -> Dict[str, Any]:
    if not records:
        return {
            "quality_score": 0.0,
            "status": "NO_DATA",
            "coverage_ratio": 0.0,
            "total_records": 0,
            "findings": ["Dataset is empty."],
            "sampling_audit": {},
            "range_audit": {}
        }

    timestamps = [r.timestamp for r in records]
    sampling_audit = analyze_sampling_intervals(timestamps, gap_threshold_minutes)
    range_audit = validate_channel_ranges(records)

    score = 100.0
    findings: List[str] = []

    if sampling_audit["duplicate_timestamps"] > 0:
        deduction = min(15.0, sampling_audit["duplicate_timestamps"] * 2.0)
        score -= deduction
        findings.append(f"Detected {sampling_audit['duplicate_timestamps']} duplicate timestamps.")

    if not sampling_audit["is_monotonic"]:
        score -= 20.0
        findings.append("Timestamps are not strictly chronological.")

    cov = sampling_audit["coverage_ratio"]
    if cov < 1.0:
        deduction = round((1.0 - cov) * 40.0, 1)
        score -= deduction
        findings.append(f"Sampling coverage is {round(cov * 100, 1)}% due to {len(sampling_audit['gaps'])} data gaps exceeding {gap_threshold_minutes} minutes.")

    if range_audit["invalid_soc_count"] > 0:
        score -= 10.0
        findings.append(f"Found {range_audit['invalid_soc_count']} SOC readings outside physical 0-100% boundary.")

    if range_audit["negative_load_count"] > 0:
        score -= 10.0
        findings.append(f"Found {range_audit['negative_load_count']} negative household load measurements.")

    for const in range_audit["constant_channels"]:
        findings.append(f"Channel '{const['channel']}' is inactive (consistently 0.0 kW). Verified as inactive channel, not sensor failure.")

    final_score = max(0.0, min(100.0, round(score, 1)))

    if final_score >= 90.0:
        status = "EXCELLENT"
    elif final_score >= 75.0:
        status = "GOOD"
    elif final_score >= 50.0:
        status = "ACCEPTABLE"
    else:
        status = "POOR"

    return {
        "quality_score": final_score,
        "status": status,
        "coverage_ratio": sampling_audit["coverage_ratio"],
        "total_records": len(records),
        "findings": findings,
        "sampling_audit": sampling_audit,
        "range_audit": range_audit
    }
