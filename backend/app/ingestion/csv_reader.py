import csv
from pathlib import Path
from typing import List, Dict, Any, Tuple

def read_csv_file(
    filepath: str | Path,
    max_rows: int | None = None
) -> Tuple[List[str], List[Dict[str, Any]], int]:
    encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample)
                    delimiter = dialect.delimiter
                except Exception:
                    delimiter = ","
                reader = csv.reader(f, delimiter=delimiter)
                header_row = next(reader, None)
                if not header_row:
                    return [], [], 0
                headers = [str(h).strip() if h else f"Column_{idx+1}" for idx, h in enumerate(header_row)]
                records: List[Dict[str, Any]] = []
                total_count = 0
                for r in reader:
                    if not any(v.strip() for v in r if isinstance(v, str)):
                        continue
                    total_count += 1
                    if max_rows is None or total_count <= max_rows:
                        record = {}
                        for idx, h in enumerate(headers):
                            val = r[idx].strip() if idx < len(r) else None
                            record[h] = val
                        records.append(record)
                return headers, records, total_count
        except UnicodeDecodeError:
            continue
    return [], [], 0
