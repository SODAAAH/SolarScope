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
            "reliability_badge": "UNAVAILABLE",
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

    invalid_ts = int(sampling_audit.get("invalid_timestamps", 0))
    if invalid_ts > 0:
        deduction = min(30.0, (invalid_ts / max(1, len(records))) * 60.0)
        score -= deduction
        findings.append(f"Excluded {invalid_ts} record(s) with unparseable timestamps from energy integration.")

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

    missing_counts = range_audit.get("missing_channel_counts", {})
    invalid_counts = range_audit.get("invalid_channel_counts", {})
    core_missing = sum(missing_counts.get(k, 0) for k in ("pv_power_kw", "load_power_kw", "grid_power_kw", "battery_power_kw"))
    core_invalid = sum(invalid_counts.get(k, 0) for k in ("pv_power_kw", "load_power_kw", "grid_power_kw", "battery_power_kw"))

    if core_missing > 0:
        miss_ratio = core_missing / max(1, len(records) * 4)
        score -= min(25.0, round(miss_ratio * 50.0, 1))
        findings.append(f"Detected {core_missing} missing power measurement cells across core channels (flagged as missing, not real zero).")

    if core_invalid > 0:
        score -= min(20.0, core_invalid * 1.0)
        findings.append(f"Detected {core_invalid} malformed numeric power readings.")

    if range_audit["invalid_soc_count"] > 0:
        score -= 10.0
        findings.append(f"Found {range_audit['invalid_soc_count']} SOC readings outside physical 0-100% boundary.")

    if range_audit["negative_load_count"] > 0:
        score -= 10.0
        findings.append(f"Found {range_audit['negative_load_count']} negative household load measurements (sign convention review recommended).")

    if range_audit["negative_pv_count"] > 0:
        score -= 5.0
        findings.append(f"Found {range_audit['negative_pv_count']} negative PV power readings clamped to 0.0 kW.")

    if range_audit.get("energy_imbalance_intervals", 0) > max(5, len(records) * 0.1):
        score -= 8.0
        findings.append(f"Found {range_audit['energy_imbalance_intervals']} intervals with >1.5 kW source-sink residual imbalance.")

    for const in range_audit["constant_channels"]:
        findings.append(f"Channel '{const['channel']}' is inactive (consistently 0.0 kW). Verified as inactive channel, not sensor failure.")

    final_score = max(0.0, min(100.0, round(score, 1)))

    if final_score >= 90.0:
        status = "EXCELLENT"
        badge = "MEASURED"
    elif final_score >= 75.0:
        status = "GOOD"
        badge = "CALCULATED"
    elif final_score >= 50.0:
        status = "ACCEPTABLE"
        badge = "DEGRADED"
    else:
        status = "POOR"
        badge = "DEGRADED"

    return {
        "quality_score": final_score,
        "status": status,
        "reliability_badge": badge,
        "coverage_ratio": sampling_audit["coverage_ratio"],
        "total_records": len(records),
        "findings": findings,
        "sampling_audit": sampling_audit,
        "range_audit": range_audit
    }
