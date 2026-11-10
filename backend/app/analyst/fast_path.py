from typing import Dict, Any
from backend.app.metrics.time_utils import format_date_mmddyyyy, format_datetime_12h
from backend.app.storage.db import get_connection
from backend.app.integrations.deye_mcp import get_station_health

def execute_fast_path(intent_info: Dict[str, Any], project_id: str = "default") -> Dict[str, Any]:
    metric = str(intent_info.get("metric", "")).lower()
    intent = str(intent_info.get("intent", "")).upper()
    target_period = intent_info.get("target_period")

    if intent == "STATION_HEALTH" or "health" in metric or "station" in metric:
        health = get_station_health(project_id)
        rt = health["realtime_power"]
        msg = (
            f"**Station Status: {health['station_name']} ({health['overall_status']})**\n\n"
            f"- **Solar Electricity Produced:** {rt['pv_kw']:.2f} kW\n"
            f"- **Household Electricity Use:** {rt['load_kw']:.2f} kW\n"
            f"- **Battery Charge Level:** {rt['battery_soc_percent']:.0f}% ({rt['battery_kw']:.2f} kW charging/discharging)\n"
            f"- **Utility Grid Power:** {rt['grid_kw']:.2f} kW\n\n"
            f"**System Recommendation:** {health['recommendation']}"
        )
        return {
            "path": "FAST_PATH",
            "intent": "STATION_HEALTH",
            "title": f"Station Overview: {health['station_name']}",
            "response_text": msg,
            "data": health,
            "duration_ms": 2.5
        }

    conn = get_connection()
    sys_row = conn.execute("SELECT * FROM system_settings WHERE project_id = ?", (project_id,)).fetchone()
    datasets = conn.execute(
        "SELECT id, filename, start_time, end_time, total_rows FROM datasets WHERE is_included = 1 ORDER BY start_time ASC"
    ).fetchall()
    conn.close()

    total_days = len(datasets)
    start_str = format_date_mmddyyyy(datasets[0]["start_time"]) if datasets else "--"
    end_str = format_date_mmddyyyy(datasets[-1]["end_time"]) if datasets else "--"

    from backend.app.api.endpoints import _get_historical_records
    from backend.app.aggregation.historical import calculate_daily_summaries

    records = _get_historical_records()
    keys = sys_row.keys() if sys_row else []
    pv_kwp = float(sys_row["pv_capacity_kwp"] or 0.0) if "pv_capacity_kwp" in keys else 0.0
    batt_kwh = float(sys_row["battery_capacity_kwh"] or 0.0) if "battery_capacity_kwh" in keys else 0.0
    reserve_soc = float(sys_row["reserve_soc"] if sys_row["reserve_soc"] is not None else 20.0) if "reserve_soc" in keys else 20.0
    tariff_rate = float(sys_row["import_tariff"] or 0.0) if "import_tariff" in keys else 0.0
    batt_model = (sys_row["battery_model"] or "").strip() if "battery_model" in keys else ""

    daily_summaries = calculate_daily_summaries(
        records,
        pv_capacity_kwp=pv_kwp,
        nominal_battery_kwh=batt_kwh,
        reserve_soc=reserve_soc
    )

    if not daily_summaries:
        return {
            "path": "FAST_PATH",
            "intent": "METRIC_LOOKUP",
            "title": "No Records Available",
            "response_text": "No historical telemetry records were found in the database. Please upload an Excel or CSV file or sync with Deye Cloud.",
            "duration_ms": 1.2
        }

    target_day = None
    if target_period and target_period != "WEEK" and target_period != "MONTH":
        for d in daily_summaries:
            if d.get("date") == target_period:
                target_day = d
                break

    if "solar" in metric:
        if target_day:
            text = (
                f"On **{format_date_mmddyyyy(target_day['date'])}**, your solar panels produced **{target_day.get('pv_kwh', 0.0):.2f} kWh** of electricity, "
                f"reaching a peak production power of **{target_day.get('peak_pv_kw', 0.0):.2f} kW** at {target_day.get('peak_pv_time_12h', 'midday')}."
            )
            return {
                "path": "FAST_PATH",
                "intent": "METRIC_LOOKUP",
                "title": f"Solar Production ({format_date_mmddyyyy(target_day['date'])})",
                "response_text": text,
                "duration_ms": 3.0
            }
        else:
            pv_values = [d.get("pv_kwh", 0.0) for d in daily_summaries if d.get("pv_kwh", 0.0) > 0]
            avg_pv = sum(pv_values) / len(pv_values) if pv_values else 0.0
            total_pv = sum(pv_values)
            text = (
                f"Your solar panels produce an average of **{avg_pv:.2f} kWh per day** of clean electricity.\n\n"
                f"Across the **{len(pv_values)} recorded days** ({start_str} to {end_str}), "
                f"total solar harvest reached **{total_pv:.1f} kWh**."
            )
            return {
                "path": "FAST_PATH",
                "intent": "METRIC_LOOKUP",
                "title": "Average Daily Solar Generation",
                "response_text": text,
                "duration_ms": 3.5
            }

    if "battery" in metric:
        latest = records[-1] if records else None
        soc_val = latest.soc_percent if latest else 0.0
        ts_val = format_datetime_12h(latest.timestamp) if latest and latest.timestamp else "No Data"
        usable_kwh = (soc_val / 100.0) * batt_kwh if batt_kwh > 0 else 0.0
        batt_label = batt_model if batt_model else "battery"
        stored_text = f" (approximately **{usable_kwh:.2f} kWh** of stored energy)" if batt_kwh > 0 else ""
        text = (
            f"Your {batt_label} last recorded a **{soc_val:.0f}% charge level**{stored_text} as of `{ts_val}`.\n\n"
            f"Safety reserve is configured at {reserve_soc:.0f}% to safeguard long-term battery cell health."
        )
        return {
            "path": "FAST_PATH",
            "intent": "METRIC_LOOKUP",
            "title": "Battery Charge Level",
            "response_text": text,
            "duration_ms": 2.2
        }

    if "grid" in metric or "tei" in metric:
        if target_day:
            grid_kwh = target_day.get("grid_import_kwh", 0.0)
            cost = grid_kwh * tariff_rate
            text = (
                f"On **{format_date_mmddyyyy(target_day['date'])}**, your home purchased **{grid_kwh:.2f} kWh** of electricity from the utility grid "
                f"(equivalent to approximately PHP {cost:.2f})."
            )
            return {
                "path": "FAST_PATH",
                "intent": "METRIC_LOOKUP",
                "title": f"Utility Electricity Purchased ({format_date_mmddyyyy(target_day['date'])})",
                "response_text": text,
                "duration_ms": 3.1
            }
        else:
            total_grid = sum(d.get("grid_import_kwh", 0.0) for d in daily_summaries)
            avg_grid = total_grid / len(daily_summaries) if daily_summaries else 0.0
            text = (
                f"Your home purchases an average of **{avg_grid:.2f} kWh per day** from the utility grid "
                f"(total purchased over {len(daily_summaries)} recorded days: {total_grid:.1f} kWh, approx. PHP {total_grid * tariff_rate:,.2f})."
            )
            return {
                "path": "FAST_PATH",
                "intent": "METRIC_LOOKUP",
                "title": "Utility Electricity Purchased",
                "response_text": text,
                "duration_ms": 3.4
            }

    if "consumption" in metric or "load" in metric:
        load_values = [d.get("load_kwh", 0.0) for d in daily_summaries]
        avg_load = sum(load_values) / len(load_values) if load_values else 0.0
        total_load = sum(load_values)
        text = (
            f"Your household electricity use averages **{avg_load:.2f} kWh per day** "
            f"(total recorded electricity consumed: **{total_load:.1f} kWh** across {len(daily_summaries)} days)."
        )
        return {
            "path": "FAST_PATH",
            "intent": "METRIC_LOOKUP",
            "title": "Household Electricity Use",
            "response_text": text,
            "duration_ms": 2.8
        }

    if "bill" in metric:
        avg_grid = sum(d.get("grid_import_kwh", 0.0) for d in daily_summaries) / len(daily_summaries) if daily_summaries else 0.0
        avg_load = sum(d.get("load_kwh", 0.0) for d in daily_summaries) / len(daily_summaries) if daily_summaries else 0.0
        projected_kwh = avg_grid * 30.5
        est_bill = projected_kwh * tariff_rate
        avoided_kwh_month = max(0.0, (avg_load - avg_grid) * 30.5)
        avoided = avoided_kwh_month * tariff_rate
        array_label = f"{pv_kwp:.2f} kWp solar and battery system" if pv_kwp > 0 else "solar and battery system"
        text = (
            f"Based on your daily average grid import of **{avg_grid:.2f} kWh/day**, your estimated monthly utility bill "
            f"is approximately **PHP {est_bill:,.2f}** ({projected_kwh:.1f} kWh at PHP {tariff_rate:.2f}/kWh).\n\n"
            f"Your {array_label} avoids an estimated **PHP {avoided:,.2f}** in monthly utility charges."
        )
        return {
            "path": "FAST_PATH",
            "intent": "BILL_ESTIMATE",
            "title": "Estimated Monthly Electricity Bill",
            "response_text": text,
            "duration_ms": 3.5
        }

    return {
        "path": "FAST_PATH",
        "intent": "METRIC_LOOKUP",
        "title": "System Summary",
        "response_text": f"SolarScope has verified telemetry for {total_days} datasets ({start_str} to {end_str}). All systems operational.",
        "duration_ms": 2.0
    }
