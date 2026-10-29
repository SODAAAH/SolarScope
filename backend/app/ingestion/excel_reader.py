import openpyxl
from pathlib import Path
from typing import List, Dict, Any, Tuple

def list_excel_sheets(filepath: str | Path) -> List[str]:
    wb = openpyxl.load_workbook(str(filepath), read_only=True, keep_links=False)
    sheets = wb.sheetnames
    wb.close()
    return sheets

def read_excel_sheet(
    filepath: str | Path,
    sheet_name: str | None = None,
    max_rows: int | None = None
) -> Tuple[List[str], List[Dict[str, Any]], int]:
    wb = openpyxl.load_workbook(str(filepath), data_only=True, keep_links=False)
    sheet = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active
    
    rows_iter = sheet.iter_rows(values_only=True)
    header_row = next(rows_iter, None)
    if not header_row:
        wb.close()
        return [], [], 0
    
    headers = [str(h).strip() if h is not None else f"Column_{idx+1}" for idx, h in enumerate(header_row)]
    
    records: List[Dict[str, Any]] = []
    total_count = 0
    for r in rows_iter:
        if not any(v is not None for v in r):
            continue
        total_count += 1
        if max_rows is None or total_count <= max_rows:
            record = {}
            for idx, h in enumerate(headers):
                val = r[idx] if idx < len(r) else None
                record[h] = val
            records.append(record)
            
    wb.close()
    return headers, records, total_count
