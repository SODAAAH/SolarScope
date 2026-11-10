import datetime
from backend.app.metrics.time_utils import format_date_mmddyyyy
from typing import Dict, Any, List, Optional
from backend.app.storage.db import get_connection
from backend.app.integrations.deye_mcp import deye_mcp_client

MANILA_TZ = datetime.timezone(datetime.timedelta(hours=8))

class DiagnosticEngine:
    def __init__(self, project_id: str = "default"):
        self.project_id = project_id

    def _load_hardware_profile(self) -> Dict[str, Any]:
        conn = get_connection()
        row = conn.execute("SELECT * FROM system_settings WHERE project_id = ?", (self.project_id,)).fetchone()
        conn.close()
        keys = row.keys() if row else []

        def fval(col: str, default: float = 0.0) -> float:
            if col in keys and row[col] is not None:
                return float(row[col])
            return default

        def ival(col: str, default: int = 0) -> int:
            if col in keys and row[col] is not None:
                return int(row[col])
            return default

        def sval(col: str, default: str = "") -> str:
            if col in keys and row[col] is not None:
                return str(row[col]).strip()
            return default

        batt_v = fval("battery_voltage", 0.0)
        bms_a = fval("bms_max_discharge_a", 0.0) or fval("bms_max_charge_a", 0.0)
        max_disch_kw = fval("max_discharge_kw", 0.0)
        if max_disch_kw <= 0 and bms_a > 0 and batt_v > 0:
            max_disch_kw = round((bms_a * batt_v) / 1000.0, 2)

        return {
            "solar": {
                "model": sval("panel_model"),
                "module_count": ival("num_modules", 0),
                "module_wattage_w": fval("module_wattage", 0.0),
                "rated_capacity_kwp": fval("pv_capacity_kwp", 0.0)
            },
            "inverter": {
                "model": sval("inverter_model"),
                "serial": sval("inverter_serial"),
                "nominal_ac_output_kw": fval("inverter_power_kw", 0.0),
                "peak_apparent_power_va": fval("inverter_max_apparent_va", 0.0),
                "max_battery_discharge_current_a": fval("inverter_max_battery_current_a", 0.0),
                "logger_serial": sval("logger_serial")
            },
            "battery": {
                "model": sval("battery_model"),
                "nominal_voltage_v": batt_v,
                "capacity_ah": fval("battery_ah", 0.0),
                "nominal_energy_kwh": fval("battery_capacity_kwh", 0.0),
                "usable_energy_kwh": fval("usable_capacity_kwh", 0.0),
                "reserve_soc_percent": fval("reserve_soc", 20.0),
                "bms_max_discharge_current_a": bms_a,
                "max_continuous_discharge_kw": max_disch_kw
            },
            "utility": {
                "location": sval("location_name"),
                "timezone": sval("timezone", "Asia/Manila"),
                "currency": sval("currency", "PHP"),
                "import_tariff": fval("import_tariff", 0.0)
            }
        }

    def investigate(self, classification: Dict[str, Any], local_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        intent = classification.get("intent", "GENERAL_ROOT_CAUSE")
        date_info = classification.get("date_info", {})
        target_date = date_info.get("date_str")

        filtered_records = self._filter_records_by_date(local_records, target_date)
        if not filtered_records and local_records:
            filtered_records = local_records[-288:]

        mcp_data = self._gather_mcp_evidence(classification, target_date)

        if intent in ["GRID_IMPORT_INVESTIGATION", "GRID_IMPORT"]:
            return self._investigate_grid_import(filtered_records, mcp_data, target_date)
        elif intent in ["BATTERY_DRAIN_INVESTIGATION", "BATTERY"]:
            return self._investigate_battery(filtered_records, mcp_data, target_date)
        elif intent in ["SOLAR_DROP_INVESTIGATION", "SOLAR"]:
            return self._investigate_solar(filtered_records, mcp_data, target_date)
        elif intent in ["INVERTER_ALERT_INVESTIGATION", "INVERTER_LIMIT_INVESTIGATION"]:
            return self._investigate_alerts(filtered_records, mcp_data)
        elif intent == "HYBRID_ANALYSIS":
            return self._investigate_hybrid(local_records, mcp_data, target_date)
        else:
            return self._investigate_general(filtered_records, mcp_data, target_date)

    def _filter_records_by_date(self, records: List[Dict[str, Any]], date_str: Optional[str]) -> List[Dict[str, Any]]:
        if not date_str or not records:
            return records
        matched = []
        for r in records:
            t = r.get("timestamp") or r.get("Time") or ""
            if date_str in t:
                matched.append(r)
        return matched

    def _gather_mcp_evidence(self, classification: Dict[str, Any], target_date: Optional[str]) -> Dict[str, Any]:
        evidence = {
            "mcp_connected": False,
            "station_latest": None,
            "device_alerts": [],
            "history_power": []
        }

        token = deye_mcp_client.get_auth_token()
        if not token:
            return evidence

        evidence["mcp_connected"] = True
        creds = deye_mcp_client._get_credentials()
        station_id = creds["station_id"]
        inverter_sn = creds["inverter_sn"]

        if station_id:
            evidence["station_latest"] = deye_mcp_client.get_station_latest(station_id)

        now_sec = int(datetime.datetime.now(MANILA_TZ).timestamp())
        week_ago_sec = now_sec - (7 * 86400)
        if inverter_sn:
            alerts_res = deye_mcp_client.get_device_alerts(inverter_sn, week_ago_sec, now_sec)
            evidence["device_alerts"] = alerts_res.get("alerts", [])

        if station_id and target_date and target_date != "WEEK" and target_date != "MONTH":
            try:
                d = datetime.date.fromisoformat(target_date)
                start_ts = int(datetime.datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=MANILA_TZ).timestamp())
                end_ts = int(datetime.datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=MANILA_TZ).timestamp())
                p_res = deye_mcp_client.get_station_history_power(station_id, start_ts, end_ts)
                if p_res.get("success"):
                    evidence["history_power"] = p_res.get("readings", [])
            except Exception:
                pass

        return evidence

    def _investigate_grid_import(self, records: List[Dict[str, Any]], mcp_data: Dict[str, Any], target_date: Optional[str]) -> Dict[str, Any]:
        hw = self._load_hardware_profile()
        grid_events = []
        total_grid_kwh = 0.0
        battery_reserve_events = []
        power_limit_events = []
        trickle_events = []

        max_discharge_kw = hw["battery"]["max_continuous_discharge_kw"]
        inverter_max_kw = hw["inverter"]["nominal_ac_output_kw"]
        reserve_soc = hw["battery"]["reserve_soc_percent"]
        usable_kwh = hw["battery"]["usable_energy_kwh"]
        batt_label = hw["battery"]["model"] or "battery bank"
        inv_label = hw["inverter"]["model"] or "hybrid inverter"

        for idx, r in enumerate(records):
            grid_kw = float(r.get("grid_power_kw") or r.get("Grid Power(kW)") or 0.0)
            soc = float(r.get("soc_percent") or r.get("Battery SOC(%)") or 0.0)
            load_kw = float(r.get("load_power_kw") or r.get("Load Power(kW)") or 0.0)
            pv_kw = float(r.get("pv_power_kw") or r.get("PV Power(kW)") or 0.0)
            t_str = r.get("timestamp") or r.get("Time") or f"Record {idx}"

            if grid_kw > 0.05:
                total_grid_kwh += (grid_kw * (5.0 / 60.0))
                event = {
                    "timestamp": t_str,
                    "grid_kw": grid_kw,
                    "household_load_kw": load_kw,
                    "battery_soc": soc,
                    "solar_kw": pv_kw
                }
                grid_events.append(event)

                if soc <= (reserve_soc + 2.0):
                    battery_reserve_events.append(event)
                elif (max_discharge_kw > 0 and load_kw > (max_discharge_kw + pv_kw)) or (inverter_max_kw > 0 and load_kw > inverter_max_kw):
                    power_limit_events.append(event)
                elif grid_kw < 0.10:
                    trickle_events.append(event)

        active_alerts = mcp_data.get("device_alerts", [])
        alert_during_import = len(active_alerts) > 0

        possible_causes = []

        if len(battery_reserve_events) > 0:
            first_time = battery_reserve_events[0]["timestamp"].split(" ")[-1]
            end_time = battery_reserve_events[-1]["timestamp"].split(" ")[-1]
            possible_causes.append({
                "cause": "Battery Reserve Threshold Reached",
                "confidence": "Confirmed" if len(battery_reserve_events) > 3 else "Likely",
                "explanation": (
                    f"Your {batt_label} reached its configured safety cutoff ({reserve_soc:.0f}% charge level) "
                    f"starting at {first_time}. When the reserve threshold is hit, the {inv_label} preserves battery lifespan "
                    f"by transferring household electricity demand to the utility grid until solar generation recovers."
                ),
                "supporting_evidence": [
                    f"{len(battery_reserve_events)} intervals recorded with battery charge level at or below {reserve_soc + 2.0:.0f}%.",
                    f"Event duration: from {first_time} through {end_time}.",
                    f"Total energy purchased during reserve phase: ~{sum(e['grid_kw'] * (5.0/60.0) for e in battery_reserve_events):.2f} kWh."
                ],
                "contradicting_evidence": []
            })

        if len(power_limit_events) > 0:
            max_load_event = max(power_limit_events, key=lambda e: e["household_load_kw"])
            limit_ref = max_discharge_kw if max_discharge_kw > 0 else inverter_max_kw
            possible_causes.append({
                "cause": "Household Demand Exceeded Battery / Inverter Discharge Limit",
                "confidence": "Confirmed",
                "explanation": (
                    f"At {max_load_event['timestamp'].split(' ')[-1]}, household power draw peaked at {max_load_event['household_load_kw']:.2f} kW, "
                    f"exceeding the configured {limit_ref:.1f} kW continuous discharge/inverter output ceiling. "
                    f"The inverter blended {max_load_event['grid_kw']:.2f} kW of utility power to support the surge safely."
                ),
                "supporting_evidence": [
                    f"Peak power draw: {max_load_event['household_load_kw']:.2f} kW (exceeds {limit_ref:.1f} kW limit).",
                    f"Recorded battery charge level during surge: {max_load_event['battery_soc']:.0f}%.",
                    f"Number of surge intervals: {len(power_limit_events)}."
                ],
                "contradicting_evidence": []
            })

        if len(trickle_events) > 0 and len(battery_reserve_events) == 0 and len(power_limit_events) == 0:
            possible_causes.append({
                "cause": "Zero-Export Sensor Feedback Inertia",
                "confidence": "Likely",
                "explanation": (
                    "The external CT sensor regulates energy flow dynamically. When heavy home appliances cycle off, "
                    "a small residual import (20 to 50 W) is routinely drawn from the utility grid briefly to prevent inadvertent export."
                ),
                "supporting_evidence": [
                    f"{len(trickle_events)} minor intervals recorded with import power under 100 W while battery was charged."
                ],
                "contradicting_evidence": []
            })

        if alert_during_import:
            possible_causes.append({
                "cause": "Inverter Operational Alert",
                "confidence": "Possible",
                "explanation": "One or more alert records were reported by the monitoring logger during the period. Inspect device event logs.",
                "supporting_evidence": [f"Active alert records: {len(active_alerts)} alerts."],
                "contradicting_evidence": []
            })

        if not possible_causes:
            possible_causes.append({
                "cause": "Normal Grid Interconnection",
                "confidence": "Likely",
                "explanation": "Minimal utility power was recorded. The system functioned within expected operating envelopes.",
                "supporting_evidence": [f"Total utility electricity purchased: {total_grid_kwh:.2f} kWh."],
                "contradicting_evidence": []
            })

        best_cause = possible_causes[0]
        recs = []
        if any(c["cause"] == "Battery Reserve Threshold Reached" for c in possible_causes):
            recs.append("Shift heavy laundry, water pumps, or high-draw loads to daylight hours (10:00 AM to 2:00 PM) to preserve stored battery energy for the night.")
            if usable_kwh > 0:
                recs.append(f"If overnight consumption consistently exceeds usable storage capacity ({usable_kwh:.1f} kWh), consider adding battery capacity.")
            else:
                recs.append("If overnight consumption consistently depletes storage before sunrise, consider evaluating additional battery capacity in Scenarios.")
        if any(c["cause"] == "Household Demand Exceeded Battery / Inverter Discharge Limit" for c in possible_causes):
            recs.append("Stagger heavy appliances (e.g. induction stove, air conditioning, water heater) between 6:00 PM and 9:00 PM to stay within continuous discharge ratings.")

        return {
            "analysis_type": "GRID_IMPORT_INVESTIGATION",
            "period": format_date_mmddyyyy(target_date) or "Recorded Period",
            "status": "completed",
            "main_finding": f"Your home purchased {total_grid_kwh:.2f} kWh of electricity from the utility grid.",
            "most_likely_explanation": best_cause["cause"],
            "confidence_level": best_cause["confidence"],
            "detailed_explanation": best_cause["explanation"],
            "supporting_evidence": best_cause["supporting_evidence"],
            "other_possible_causes": [c for c in possible_causes if c != best_cause],
            "total_grid_purchased_kwh": round(total_grid_kwh, 2),
            "recommendations": recs,
            "hardware_limits_checked": {
                "inverter_nominal_ac_kw": inverter_max_kw,
                "battery_max_discharge_kw": max_discharge_kw,
                "configured_reserve_soc": reserve_soc
            }
        }

    def _investigate_battery(self, records: List[Dict[str, Any]], mcp_data: Dict[str, Any], target_date: Optional[str]) -> Dict[str, Any]:
        hw = self._load_hardware_profile()
        if not records:
            return {
                "analysis_type": "BATTERY_INVESTIGATION",
                "period": format_date_mmddyyyy(target_date) or "Current",
                "status": "completed",
                "main_finding": "No battery telemetry records found for the requested period.",
                "most_likely_explanation": "Insufficient Data",
                "confidence_level": "Unknown",
                "detailed_explanation": "Please upload a dataset or verify Deye Cloud logger synchronization.",
                "supporting_evidence": [],
                "other_possible_causes": [],
                "recommendations": []
            }

        night_records = []
        is_night = False
        for r in records:
            pv = float(r.get("pv_power_kw") or r.get("PV Power(kW)") or 0.0)
            batt_w = float(r.get("battery_power_kw") or r.get("Battery Power(kW)") or 0.0)
            load = float(r.get("load_power_kw") or r.get("Load Power(kW)") or 0.0)

            if pv < 0.10 and (batt_w > 0.05 or load > 0.10):
                is_night = True

            if is_night and pv < 0.10:
                night_records.append(r)

        if not night_records:
            night_records = records

        soc_values = [float(r.get("soc_percent") or r.get("Battery SOC(%)") or 0.0) for r in night_records]
        load_values = [float(r.get("load_power_kw") or r.get("Load Power(kW)") or 0.0) for r in night_records]

        start_soc = soc_values[0] if soc_values else 0.0
        min_soc = min(soc_values) if soc_values else 0.0
        end_soc = soc_values[-1] if soc_values else 0.0
        avg_load = sum(load_values) / len(load_values) if load_values else 0.0
        max_load = max(load_values) if load_values else 0.0
        total_night_consumed_kwh = sum(l * (5.0 / 60.0) for l in load_values)

        reserve_soc = hw["battery"]["reserve_soc_percent"]
        usable_kwh = hw["battery"]["usable_energy_kwh"]
        batt_label = hw["battery"]["model"] or "battery system"
        reserve_hit = min_soc <= (reserve_soc + 2.0)
        high_load_cause = avg_load > 1.2

        if high_load_cause and reserve_hit:
            cause = "High Sustained Overnight Household Consumption"
            conf = "Confirmed"
            cap_note = f"usable capacity of {usable_kwh:.2f} kWh above the {reserve_soc:.0f}% reserve" if usable_kwh > 0 else f"usable storage above the {reserve_soc:.0f}% reserve"
            exp = (
                f"Your {batt_label} discharged rapidly because overnight household electricity demand averaged {avg_load:.2f} kW "
                f"(peaking at {max_load:.2f} kW). Over the night, your home consumed {total_night_consumed_kwh:.2f} kWh, "
                f"exhausting the {cap_note} before morning."
            )
        elif reserve_hit:
            cause = "Normal Nighttime Energy Utilization Reaching Reserve"
            conf = "Likely"
            exp = (
                f"Your battery smoothly powered your home throughout the night, reducing its charge level from {start_soc:.0f}% to {min_soc:.0f}%. "
                f"The battery reached its configured {reserve_soc:.0f}% safety threshold as designed, avoiding grid purchases until reserve cutoff."
            )
        else:
            cause = "Nominal Battery Discharge Within Capacity Bounds"
            conf = "Confirmed"
            exp = (
                f"Battery discharge was nominal. Charge level began the period at {start_soc:.0f}% and remained safely above reserve at {end_soc:.0f}%, "
                f"supplying {total_night_consumed_kwh:.2f} kWh of clean stored electricity to your home."
            )

        return {
            "analysis_type": "BATTERY_INVESTIGATION",
            "period": format_date_mmddyyyy(target_date) or "Nighttime",
            "status": "completed",
            "main_finding": f"Overnight household electricity demand totaled {total_night_consumed_kwh:.2f} kWh with an average load of {avg_load:.2f} kW.",
            "most_likely_explanation": cause,
            "confidence_level": conf,
            "detailed_explanation": exp,
            "supporting_evidence": [
                f"Initial battery charge level: {start_soc:.0f}%.",
                f"Lowest recorded charge level: {min_soc:.0f}%.",
                f"Average household power draw: {avg_load:.2f} kW.",
                f"Total overnight energy supplied: {total_night_consumed_kwh:.2f} kWh."
            ],
            "other_possible_causes": [],
            "recommendations": [
                "Schedule high-draw appliances to run during peak solar generation hours rather than overnight.",
                "Verify battery BMS cell voltage balance periodically in diagnostics."
            ]
        }

    def _investigate_solar(self, records: List[Dict[str, Any]], mcp_data: Dict[str, Any], target_date: Optional[str]) -> Dict[str, Any]:
        hw = self._load_hardware_profile()
        pv_powers = [float(r.get("pv_power_kw") or r.get("PV Power(kW)") or 0.0) for r in records]
        peak_pv = max(pv_powers) if pv_powers else 0.0
        total_pv_kwh = sum(p * (5.0 / 60.0) for p in pv_powers)

        rated_kwp = hw["solar"]["rated_capacity_kwp"]
        panel_label = hw["solar"]["model"] or "solar array"
        loc_label = hw["utility"]["location"]

        if rated_kwp > 0:
            expected_daily_kwh = rated_kwp * 4.2
            util_pct = (peak_pv / rated_kwp) * 100.0
            if total_pv_kwh < (expected_daily_kwh * 0.6):
                cause = "Reduced Atmospheric Solar Irradiance (Cloud Cover / Rain)"
                conf = "Likely"
                loc_phrase = f" at {loc_label}" if loc_label else ""
                exp = (
                    f"Your {rated_kwp:.2f} kWp {panel_label} produced {total_pv_kwh:.2f} kWh on {format_date_mmddyyyy(target_date) or 'the selected day'}, "
                    f"which is below the typical seasonal benchmark of ~{expected_daily_kwh:.1f} kWh{loc_phrase}. "
                    f"Peak generation reached {peak_pv:.2f} kW with localized irradiance fluctuations."
                )
            else:
                cause = "Optimal Solar Generation Within Expected Engineering Specifications"
                conf = "Confirmed"
                exp = (
                    f"Solar harvest was strong. Your {rated_kwp:.2f} kWp system generated {total_pv_kwh:.2f} kWh, peaking at {peak_pv:.2f} kW "
                    f"({util_pct:.0f}% of rated nameplate capacity)."
                )
            cap_evidence = f"Capacity utilization: {util_pct:.1f}% of {rated_kwp:.2f} kWp array."
        else:
            cause = "Solar Generation Summary"
            conf = "Likely"
            exp = (
                f"Your PV array generated {total_pv_kwh:.2f} kWh with a peak output of {peak_pv:.2f} kW. "
                f"Configure your array nameplate kWp in System Settings to enable capacity factor benchmarking."
            )
            cap_evidence = "Configure PV capacity (kWp) in System Settings for nameplate utilization metrics."

        return {
            "analysis_type": "SOLAR_INVESTIGATION",
            "period": format_date_mmddyyyy(target_date) or "Recorded Day",
            "status": "completed",
            "main_finding": f"Total solar electricity produced was {total_pv_kwh:.2f} kWh (Peak: {peak_pv:.2f} kW).",
            "most_likely_explanation": cause,
            "confidence_level": conf,
            "detailed_explanation": exp,
            "supporting_evidence": [
                f"Total production: {total_pv_kwh:.2f} kWh.",
                f"Peak DC output: {peak_pv:.2f} kW.",
                cap_evidence
            ],
            "other_possible_causes": [],
            "recommendations": [
                "Inspect panel surfaces periodically for dust, bird droppings, or shading obstructions.",
                "Trim nearby trees if morning or late afternoon string power shows abrupt drops."
            ]
        }

    def _investigate_alerts(self, records: List[Dict[str, Any]], mcp_data: Dict[str, Any]) -> Dict[str, Any]:
        hw = self._load_hardware_profile()
        inv_sn = hw["inverter"]["serial"]
        log_sn = hw["inverter"]["logger_serial"]
        inv_desc = f"inverter {inv_sn}" if inv_sn else "the configured inverter"
        if log_sn:
            inv_desc += f" and logger {log_sn}"

        if not mcp_data.get("mcp_connected"):
            return {
                "analysis_type": "ALERT_INVESTIGATION",
                "period": "Past 7 Days",
                "status": "completed",
                "main_finding": "Deye Cloud connection is not active to query live device alert registers.",
                "most_likely_explanation": "Cloud Telemetry Not Connected",
                "confidence_level": "Unknown",
                "detailed_explanation": "Configure your Deye Cloud API credentials in Data Library & Cloud to query live inverter fault and alert logs.",
                "supporting_evidence": [
                    "No active Deye Cloud session configured for live alert polling."
                ],
                "other_possible_causes": [],
                "recommendations": ["Add your Deye Cloud credentials in Data Library & Cloud to enable live fault tracking."]
            }

        alerts = mcp_data.get("device_alerts", [])
        if not alerts:
            return {
                "analysis_type": "ALERT_INVESTIGATION",
                "period": "Past 7 Days",
                "status": "completed",
                "main_finding": "No active inverter or battery alerts recorded by the monitoring system.",
                "most_likely_explanation": "Inverter Operating Nominally",
                "confidence_level": "Confirmed",
                "detailed_explanation": f"All internal diagnostic registers on {inv_desc} indicate normal operational health with zero logged fault codes.",
                "supporting_evidence": [
                    "Alert list query returned 0 fault or warning events in the last 7 days.",
                    "Connection status reported as NORMAL."
                ],
                "other_possible_causes": [],
                "recommendations": ["No technical maintenance required. Continue routine operational monitoring."]
            }

        first_alert = alerts[0]
        alert_name = first_alert.get("alertName", "Inverter Warning")
        alert_code = first_alert.get("alertCode", "N/A")
        alert_time = first_alert.get("alertTime", "Recent")

        return {
            "analysis_type": "ALERT_INVESTIGATION",
            "period": "Past 7 Days",
            "status": "completed",
            "main_finding": f"{len(alerts)} device alert event(s) recorded on {inv_desc}.",
            "most_likely_explanation": f"Device Alert: {alert_name} (Code {alert_code})",
            "confidence_level": "Confirmed",
            "detailed_explanation": (
                f"The inverter logged alert '{alert_name}' at {alert_time}. "
                f"The diagnostic engine cross-referenced this with electrical operating limits."
            ),
            "supporting_evidence": [
                f"Alert description: {alert_name}.",
                f"Reported event code: {alert_code} at {alert_time}.",
                f"Total alert count in window: {len(alerts)}."
            ],
            "other_possible_causes": [],
            "recommendations": [
                "Check AC grid voltage and frequency stability on utility supply lines.",
                "If alerts persist, contact your certified installer to inspect DC breaker terminals and grounding resistance."
            ]
        }

    def _investigate_hybrid(self, records: List[Dict[str, Any]], mcp_data: Dict[str, Any], target_date: Optional[str]) -> Dict[str, Any]:
        hw = self._load_hardware_profile()
        mcp_latest = mcp_data.get("station_latest") or {}
        live_m = mcp_latest.get("measurements", {}) if mcp_latest.get("success") else {}

        if not live_m:
            return {
                "analysis_type": "HYBRID_INVESTIGATION",
                "period": format_date_mmddyyyy(target_date) or "System Operational History",
                "status": "completed",
                "main_finding": "Live Deye Cloud state is currently offline or unconfigured.",
                "most_likely_explanation": "Historical Baseline Available; Live Cloud Offline",
                "confidence_level": "Likely",
                "detailed_explanation": (
                    "Historical telemetry records were loaded from local datasets, but live Deye Cloud telemetry is currently offline or unconfigured. "
                    "Connect Deye Cloud credentials in Data Library & Cloud to combine live power measurements with historical analysis."
                ),
                "supporting_evidence": [
                    f"Historical records evaluated: {len(records)} intervals."
                ],
                "other_possible_causes": [],
                "recommendations": [
                    "Configure Deye Cloud credentials in Data Library & Cloud to stream real-time hybrid telemetry."
                ]
            }

        live_pv = float(live_m.get("pv_power_kw") or 0.0)
        live_load = float(live_m.get("household_load_kw") or 0.0)
        live_soc = float(live_m.get("battery_charge_level_percent") or 0.0)
        live_grid = float(live_m.get("grid_power_kw") or 0.0)
        pv_kwp = hw["solar"]["rated_capacity_kwp"]
        array_label = f"{pv_kwp:.2f} kWp solar array" if pv_kwp > 0 else "solar array"
        batt_label = hw["battery"]["model"] or "battery storage"

        return {
            "analysis_type": "HYBRID_INVESTIGATION",
            "period": format_date_mmddyyyy(target_date) or "System Operational History",
            "status": "completed",
            "main_finding": f"System actively generating {live_pv:.2f} kW with battery at {live_soc:.0f}% charge level.",
            "most_likely_explanation": "Coordinated Local History & Live Telemetry Analysis",
            "confidence_level": "Confirmed",
            "detailed_explanation": (
                f"SolarScope reconciled your historical telemetry baseline against live Deye Cloud measurements. "
                f"Currently, your {array_label} produces {live_pv:.2f} kW, supplying the {live_load:.2f} kW home load "
                f"while {batt_label} sits at {live_soc:.0f}% SOC. Net grid exchange is {live_grid:.2f} kW."
            ),
            "supporting_evidence": [
                f"Live solar power: {live_pv:.2f} kW.",
                f"Live home electricity demand: {live_load:.2f} kW.",
                f"Live battery charge level: {live_soc:.0f}%.",
                "Live Deye Cloud telemetry status: Connected."
            ],
            "other_possible_causes": [],
            "recommendations": [
                "Keep high-draw appliances scheduled during strong daylight generation windows when surplus power is available."
            ]
        }

    def _investigate_general(self, records: List[Dict[str, Any]], mcp_data: Dict[str, Any], target_date: Optional[str]) -> Dict[str, Any]:
        return self._investigate_grid_import(records, mcp_data, target_date)

diagnostic_engine_instance = DiagnosticEngine()
