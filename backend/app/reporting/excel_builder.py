from pathlib import Path
from typing import List, Dict, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.time_utils import format_time_12h, format_datetime_12h, hour_index_to_12h

def build_excel_report(
    records: List[CanonicalRecord],
    summary_data: Dict[str, Any],
    hourly_breakdown: List[Dict[str, Any]],
    operating_states: List[Dict[str, Any]],
    output_path: str | Path
) -> Path:
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    sub_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    ws_summary = wb.active
    ws_summary.title = "Audit Summary"

    ws_summary["A1"] = "SolarScope Technical Audit Summary"
    ws_summary["A1"].font = Font(name="Calibri", size=16, bold=True, color="0F172A")
    ws_summary["A2"] = f"Generated on {summary_data.get('report_date', '')} | File: {summary_data.get('filename', 'SolarScope Dataset')}"
    ws_summary["A2"].font = Font(name="Calibri", size=10, italic=True, color="475569")

    ws_summary.append([])
    ws_summary.append(["Key Performance Indicator", "Value", "Unit", "Methodology / Formula"])
    row_idx = 4
    for col_idx in range(1, 5):
        cell = ws_summary.cell(row=row_idx, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center" if col_idx in [2, 3] else "left")

    kpis = [
        ("Solar PV Generation", summary_data.get("pv_kwh", 0.0), "kWh", "Trapezoidal numerical integration over Δt"),
        ("Household Demand", summary_data.get("load_kwh", 0.0), "kWh", "Trapezoidal numerical integration over Δt"),
        ("Grid Imported Energy", summary_data.get("grid_import_kwh", 0.0), "kWh", "Trapezoidal integration of positive grid power"),
        ("Grid Exported Energy", summary_data.get("grid_export_kwh", 0.0), "kWh", "Trapezoidal integration of negative grid power"),
        ("Battery Discharging Energy", summary_data.get("batt_disch_kwh", 0.0), "kWh", "Trapezoidal integration of positive battery power"),
        ("Battery Charging Energy", summary_data.get("batt_chg_kwh", 0.0), "kWh", "Trapezoidal integration of negative battery power"),
        ("Reconciliation Residual", summary_data.get("residual_kwh", 0.0), "kWh", "Sources (PV+Grid+Disch) - Sinks (Load+Chg)"),
        ("Solar Self-Consumption Ratio", summary_data.get("self_consumption", 0.0), "Ratio", "(Direct Solar + Battery Charge) / Total PV"),
        ("Solar Self-Sufficiency Ratio", summary_data.get("self_sufficiency", 0.0), "Ratio", "(Direct Solar + Battery Disch) / Total Load"),
        ("Grid Dependence Ratio", summary_data.get("grid_dependence", 0.0), "Ratio", "Grid Import / Total Load"),
        ("Peak PV Power", summary_data.get("peak_pv_kw", 0.0), "kW", f"Instantaneous max @ {summary_data.get('peak_pv_time_12h', 'N/A')}"),
        ("Peak Household Load", summary_data.get("peak_load_kw", 0.0), "kW", f"Instantaneous max @ {summary_data.get('peak_load_time_12h', 'N/A')}"),
        ("Base-Load Estimate", summary_data.get("base_load_kw", 0.0), "kW", "5th percentile night demand (2:00 AM - 5:00 AM)")
    ]

    for item in kpis:
        ws_summary.append([item[0], item[1], item[2], item[3]])
        curr_row = ws_summary.max_row
        for c in range(1, 5):
            cell = ws_summary.cell(row=curr_row, column=c)
            cell.border = thin_border
            if c == 2 and isinstance(item[1], float):
                cell.number_format = "#,##0.00"

    ws_hourly = wb.create_sheet(title="Hourly Breakdown")
    ws_hourly.append(["Hour of Day", "PV Energy (kWh)", "Household Demand (kWh)", "Grid Import (kWh)"])
    for col_idx in range(1, 5):
        cell = ws_hourly.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill

    for h in hourly_breakdown:
        ws_hourly.append([
            h.get("hour_label_12h", hour_index_to_12h(h.get("hour", 0))),
            h.get("pv_kwh", 0.0),
            h.get("load_kwh", 0.0),
            h.get("grid_kwh", 0.0)
        ])
        curr_row = ws_hourly.max_row
        for c in range(1, 5):
            cell = ws_hourly.cell(row=curr_row, column=c)
            cell.border = thin_border
            if c > 1:
                cell.number_format = "#,##0.000"

    ws_states = wb.create_sheet(title="Operating States")
    ws_states.append(["State Identifier", "Start Time (12h)", "End Time (12h)", "Duration (min)", "PV (kWh)", "Load (kWh)", "Grid (kWh)", "Classification Reason"])
    for col_idx in range(1, 9):
        cell = ws_states.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill

    for s in operating_states:
        ws_states.append([
            s.get("state"),
            s.get("start_time_12h", format_time_12h(s.get("start_time"))),
            s.get("end_time_12h", format_time_12h(s.get("end_time"))),
            s.get("duration_minutes"),
            s.get("pv_energy_kwh"),
            s.get("load_energy_kwh"),
            s.get("grid_energy_kwh"),
            s.get("reason")
        ])
        curr_row = ws_states.max_row
        for c in range(1, 9):
            ws_states.cell(row=curr_row, column=c).border = thin_border

    ws_raw = wb.create_sheet(title="Normalized Telemetry")
    ws_raw.append(["Timestamp", "PV Power (kW)", "Load Power (kW)", "Grid Power (kW)", "Battery Power (kW)", "SOC (%)", "Residual Power (kW)"])
    for col_idx in range(1, 8):
        cell = ws_raw.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill

    for r in records:
        ws_raw.append([
            r.timestamp,
            r.pv_power_kw,
            r.load_power_kw,
            r.grid_power_kw,
            r.battery_power_kw,
            r.soc_percent,
            r.residual_power_kw
        ])
        curr_row = ws_raw.max_row
        for c in range(1, 8):
            cell = ws_raw.cell(row=curr_row, column=c)
            cell.border = thin_border
            if c in [2, 3, 4, 5, 7]:
                cell.number_format = "0.000"
            elif c == 6:
                cell.number_format = "0.0"

    for ws in [ws_summary, ws_hourly, ws_states, ws_raw]:
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    wb.save(str(target_path))
    wb.close()
    return target_path
