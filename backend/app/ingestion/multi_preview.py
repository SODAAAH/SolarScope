import hashlib
from pathlib import Path
from typing import Dict, Any, List
from backend.app.ingestion.excel_reader import read_excel_sheet
from backend.app.ingestion.csv_reader import read_csv_file
from backend.app.ingestion.column_mapper import build_column_mapping_preview
from backend.app.metrics.time_utils import parse_timestamp
from backend.app.storage.db import get_connection

def inspect_file_for_preview(
    filepath: Path,
    original_filename: str,
    project_id: str = "default",
    timezone: str = "Asia/Manila"
) -> Dict[str, Any]:
    file_bytes = filepath.read_bytes()
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    file_size = len(file_bytes)
    file_ext = filepath.suffix.lower()

    conn = get_connection()
    existing_dup = conn.execute(
        "SELECT id, filename FROM datasets WHERE file_hash = ? AND project_id = ?",
        (file_hash, project_id)
    ).fetchone()
    conn.close()

    is_duplicate = existing_dup is not None
    existing_dataset_id = existing_dup["id"] if existing_dup else None

    issues: List[str] = []
    if is_duplicate:
        issues.append(f"Identical file already exists in library as {existing_dup['filename']}.")

    headers: List[str] = []
    sample_records: List[Dict[str, Any]] = []
    all_rows: List[Dict[str, Any]] = []
    total_records = 0

    try:
        if file_ext in [".xlsx", ".xlsm"]:
            headers, sample_records, _ = read_excel_sheet(filepath, max_rows=10)
            _, all_rows, total_records = read_excel_sheet(filepath)
        elif file_ext == ".csv":
            headers, sample_records, _ = read_csv_file(filepath, max_rows=10)
            _, all_rows, total_records = read_csv_file(filepath)
        else:
            issues.append(f"Unsupported file format {file_ext}.")
            return {
                "filename": original_filename,
                "file_format": file_ext,
                "filesize_bytes": file_size,
                "file_hash": file_hash,
                "total_records": 0,
                "start_time": None,
                "end_time": None,
                "sampling_interval_min": 0,
                "columns_detected": {},
                "is_duplicate": is_duplicate,
                "existing_dataset_id": existing_dataset_id,
                "quality_score": 0.0,
                "potential_issues": issues
            }
    except Exception as e:
        issues.append(f"Failed to read file: {str(e)}")
        return {
            "filename": original_filename,
            "file_format": file_ext,
            "filesize_bytes": file_size,
            "file_hash": file_hash,
            "total_records": 0,
            "start_time": None,
            "end_time": None,
            "sampling_interval_min": 0,
            "columns_detected": {},
            "is_duplicate": is_duplicate,
            "existing_dataset_id": existing_dataset_id,
            "quality_score": 0.0,
            "potential_issues": issues
        }

    mapping_preview = build_column_mapping_preview(headers, sample_records)
    detected_cols = {}
    for item in mapping_preview:
        if item.canonical_name:
            detected_cols[item.original_name] = item.canonical_name

    start_time = None
    end_time = None
    sampling_interval_min = 5.0

    if all_rows:
        time_key = None
        for col in ["Time", "Timestamp", "DateTime", "Date/Time", "time", "timestamp"]:
            if col in all_rows[0]:
                time_key = col
                break

        if time_key:
            t_start = parse_timestamp(all_rows[0].get(time_key), timezone)
            t_end = parse_timestamp(all_rows[-1].get(time_key), timezone)
            start_time = t_start.isoformat() if t_start else str(all_rows[0].get(time_key, ""))
            end_time = t_end.isoformat() if t_end else str(all_rows[-1].get(time_key, ""))
            if len(all_rows) > 1:
                t0 = parse_timestamp(all_rows[0].get(time_key), timezone)
                t1 = parse_timestamp(all_rows[1].get(time_key), timezone)
                if t0 is not None and t1 is not None and t1 > t0:
                    sampling_interval_min = max(0.5, round((t1 - t0).total_seconds() / 60.0, 1))
        else:
            issues.append("Timestamp column was not automatically identified.")

    required_signals = ["pv_power_kw", "load_power_kw", "grid_power_kw", "battery_power_kw"]
    found_signals = set(detected_cols.values())
    missing_signals = [s for s in required_signals if s not in found_signals]
    if missing_signals:
        issues.append(f"Missing core signals: {', '.join(missing_signals)}.")

    quality_score = 100.0
    if is_duplicate:
        quality_score -= 40.0
    if missing_signals:
        quality_score -= (len(missing_signals) * 15.0)
    if total_records < 100:
        quality_score -= 20.0
    quality_score = max(0.0, min(100.0, quality_score))

    return {
        "filename": original_filename,
        "file_format": file_ext,
        "filesize_bytes": file_size,
        "file_hash": file_hash,
        "total_records": total_records,
        "start_time": start_time,
        "end_time": end_time,
        "sampling_interval_min": sampling_interval_min,
        "columns_detected": detected_cols,
        "is_duplicate": is_duplicate,
        "existing_dataset_id": existing_dataset_id,
        "quality_score": round(quality_score, 1),
        "potential_issues": issues
    }

