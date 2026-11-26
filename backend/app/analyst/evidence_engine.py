from typing import Dict, Any

def build_evidence_response(
    query_key: str,
    snapshot: Dict[str, Any],
    weather_info: Dict[str, Any]
) -> Dict[str, Any]:
    if not snapshot:
        return {
            "query_key": query_key,
            "title": "Telemetry Unavailable",
            "what_happened": "No historical telemetry records are loaded for this installation yet.",
            "what_data_shows": "0 telemetry intervals available for calculation.",
            "why_it_happened": "Upload CSV/Excel inverter exports or sync historical dates from Deye Cloud in Data Library & Cloud.",
            "energy_or_money_impact": "Financial and energy calculations require recorded solar, load, battery, and grid telemetry.",
            "what_to_do": "Open Data Library & Cloud to upload or synchronize at least one day of inverter data.",
            "confidence_level": "Unavailable (no recorded telemetry)"
        }

    solar = snapshot.get("solar", {})
    battery = snapshot.get("battery", {})
    grid = snapshot.get("grid", {})
    consumption = snapshot.get("consumption", {})
    hardware = snapshot.get("hardware", {})

    tariff = float(hardware.get("tariff_rate_php", 0.0) or 0.0)
    pv_kwp = float(hardware.get("pv_capacity_kwp", 0.0) or 0.0)
    batt_kwh = float(hardware.get("battery_capacity_kwh", 0.0) or 0.0)
    inv_max_a = float(hardware.get("inverter_max_battery_current_a", 0.0) or 0.0)
    bms_a = float(hardware.get("bms_max_charge_a", 0.0) or 0.0)
    eff_a = min(inv_max_a, bms_a) if (inv_max_a > 0 and bms_a > 0) else max(inv_max_a, bms_a)
    loc_name = (hardware.get("location_name") or "").strip()
    panel_model = (hardware.get("panel_model") or "").strip()
    inverter_model = (hardware.get("inverter_model") or "").strip()
    night_kwh = float(snapshot.get("night_load_kwh", 0.0) or 0.0)

    if query_key == "why_battery_drained":
        disch_kwh = battery.get("discharging_energy_kwh", 0.0)
        min_soc = battery.get("min_soc_percent", 0.0)
        reserve_soc = battery.get("reserve_soc_percent", 20.0)
        hours_at_reserve = battery.get("hours_at_reserve_limit", 0.0)
        cost_impact = round(disch_kwh * tariff, 2)
        return {
            "query_key": query_key,
            "title": "Battery Depletion Diagnostic",
            "what_happened": f"Your battery discharged {disch_kwh:.2f} kWh and reached a minimum recorded SOC of {min_soc:.1f}% (reserve setting: {reserve_soc:.0f}%).",
            "what_data_shows": f"Battery stayed at or below reserve threshold for {hours_at_reserve:.1f} hours. Nighttime household usage consumed {night_kwh:.2f} kWh between 8:00 PM and 6:00 AM.",
            "why_it_happened": "Sustained evening and nighttime household electricity usage exceeded the available stored energy above your battery's safety reserve limit.",
            "energy_or_money_impact": f"{disch_kwh:.2f} kWh of battery power supplied to your home (estimated offset ~PHP {cost_impact:.2f} at configured tariff)." if tariff > 0 else f"{disch_kwh:.2f} kWh of battery power supplied to your home.",
            "what_to_do": "To extend battery autonomy through morning sunrise, shift heavy appliance usage (such as washing machines or water pumps) to peak daylight solar hours between 10:00 AM and 2:00 PM.",
            "confidence_level": "Confirmed (derived from recorded battery power and SOC telemetry)"
        }

    elif query_key == "why_grid_purchased_with_battery":
        grid_import_kwh = grid.get("imported_energy_kwh", 0.0)
        classifications = grid.get("import_classification", [])
        reserve_cat = next((c for c in classifications if "Reserve" in c["category"]), None)
        power_cat = next((c for c in classifications if "Peak Load" in c["category"] or "Power Limit" in c["category"]), None)
        trickle_cat = next((c for c in classifications if "Trickle" in c["category"]), None)

        primary_reason = "Reserve Limit"
        if power_cat and power_cat["energy_kwh"] > (reserve_cat["energy_kwh"] if reserve_cat else 0):
            primary_reason = "Power Demand Limit"
        elif trickle_cat and trickle_cat["energy_kwh"] > (grid_import_kwh * 0.6):
            primary_reason = "Inverter Zero-Export Stabilization"

        return {
            "query_key": query_key,
            "title": "Grid Purchase Cause Analysis",
            "what_happened": f"Your home imported {grid_import_kwh:.2f} kWh of utility electricity during this observation period.",
            "what_data_shows": f"Classification breakdown: {reserve_cat['energy_kwh'] if reserve_cat else 0:.2f} kWh at reserve cutoff, {power_cat['energy_kwh'] if power_cat else 0:.2f} kWh during peak load/inverter assist, and {trickle_cat['energy_kwh'] if trickle_cat else 0:.2f} kWh in grid trickle/sync.",
            "why_it_happened": f"The primary driver was {primary_reason}. When home electricity demand spikes above inverter discharge limits or when the battery reaches its reserve threshold, the inverter draws utility power.",
            "energy_or_money_impact": f"Estimated utility grid import cost: PHP {grid_import_kwh * tariff:.2f}." if tariff > 0 else f"Total utility grid import measured: {grid_import_kwh:.2f} kWh (configure tariff rate for cost impact).",
            "what_to_do": "Review the Energy & Demand tab to check if heavy appliances operated concurrently, and stagger air conditioner or motor start times to stay within inverter output limits.",
            "confidence_level": "Calculated (derived from 6-category interval classification)"
        }

    elif query_key == "will_battery_last_tonight":
        tomorrow = weather_info.get("tomorrow_forecast")
        if not tomorrow:
            return {
                "query_key": query_key,
                "title": "Nighttime Battery Autonomy Forecast",
                "what_happened": "Local weather forecast is unavailable because site coordinates or forecast data have not been loaded.",
                "what_data_shows": f"Observed nighttime household demand is {night_kwh:.2f} kWh between 8:00 PM and 6:00 AM.",
                "why_it_happened": "Open-Meteo solar irradiance modeling requires configured latitude, longitude, PV capacity, and battery capacity in System Settings.",
                "energy_or_money_impact": f"Each kWh stored offsets PHP {tariff:.2f} in utility imports." if tariff > 0 else "Configure utility tariff in System Settings to estimate nighttime cost offset.",
                "what_to_do": "Enter your site latitude, longitude, PV kWp, and battery kWh in System Settings to generate tomorrow's solar and battery autonomy forecast.",
                "confidence_level": "Unavailable (location coordinates not configured)"
            }
        sunset_soc = tomorrow.get("projected_sunset_soc_percent", 0.0)
        autonomy_str = tomorrow.get("projected_night_autonomy_formatted", "--")
        prob_full = tomorrow.get("probability_full_charge_percent", 0.0)
        expected_pv = tomorrow.get("expected_solar_kwh", 0.0)
        loc_phrase = f" in {loc_name}" if loc_name else ""
        array_phrase = f" with your {pv_kwp:.2f} kWp solar array" if pv_kwp > 0 else ""
        batt_phrase = f"your {batt_kwh:.2f} kWh battery storage" if batt_kwh > 0 else "your battery storage"
        return {
            "query_key": query_key,
            "title": "Nighttime Battery Autonomy Forecast",
            "what_happened": f"Weather-based solar harvest is estimated at {expected_pv:.1f} kWh tomorrow, giving an estimated {prob_full:.0f}% likelihood of reaching full battery charge before sunset.",
            "what_data_shows": f"Estimated battery state-of-charge at sunset is {sunset_soc:.0f}%, providing roughly {autonomy_str} of autonomous power based on recent average nighttime load ({night_kwh:.1f} kWh).",
            "why_it_happened": f"Forecasted solar irradiance{loc_phrase}{array_phrase} determines expected daytime surplus available to replenish {batt_phrase}.",
            "energy_or_money_impact": f"Reaching full charge before sunset would offset approximately {night_kwh:.1f} kWh of nighttime grid purchases (~PHP {night_kwh * tariff:.2f} per night)." if tariff > 0 else f"Reaching full charge before sunset would offset approximately {night_kwh:.1f} kWh of nighttime grid purchases.",
            "what_to_do": "Monitor midday sky conditions; if heavy cloud cover develops, reduce non-essential evening electricity loads to preserve battery reserve.",
            "confidence_level": "Estimated (weather forecast model combined with observed household consumption)"
        }

    elif query_key == "should_add_battery":
        grid_import_kwh = grid.get("imported_energy_kwh", 0.0)
        reserve_soc = hardware.get("reserve_soc_percent", 20.0)
        potential_reduction_kwh = min(grid_import_kwh * 0.75, 4.5)
        monthly_savings = potential_reduction_kwh * 30.5 * tariff
        est_cost = 5.0 * 22000.0
        payback = round(est_cost / (monthly_savings * 12.0), 1) if monthly_savings > 0 else 0.0
        batt_phrase = f"Your current {batt_kwh:.2f} kWh battery" if batt_kwh > 0 else "Your current storage system"
        cap_conf = f"constrained by {eff_a:.0f}A continuous current limit and observed demand" if eff_a > 0 else "derived from observed household demand"
        return {
            "query_key": query_key,
            "title": "Battery Storage Upgrade Assessment",
            "what_happened": f"{batt_phrase} still leaves an observed import of {grid_import_kwh:.2f} kWh over the selected window from the utility grid.",
            "what_data_shows": f"A hypothetical 5.0 kWh storage expansion could capture surplus midday solar and reduce grid imports by up to ~{potential_reduction_kwh:.2f} kWh per day.",
            "why_it_happened": f"Household demand after sunset occasionally outlasts usable stored energy, triggering the {reserve_soc:.0f}% battery reserve cutoff.",
            "energy_or_money_impact": f"Hypothetical hardware budget: PHP {est_cost:,.2f} (assumed PHP 22,000/kWh). Projected monthly savings: PHP {monthly_savings:,.2f}, estimated payback: {payback} years." if monthly_savings > 0 else f"Hypothetical hardware budget for 5.0 kWh: PHP {est_cost:,.2f}. Configure your electricity tariff rate to project payback.",
            "what_to_do": "Open the What-If & Upgrades tab to test custom storage sizes and compare modeled return on investment against solar array additions.",
            "confidence_level": f"Simulated ({cap_conf})"
        }

    else:
        pv_kwh = solar.get("total_generation_kwh", 0.0)
        load_kwh = consumption.get("total_demand_kwh", consumption.get("total_consumption_kwh", 0.0))
        grid_kwh = grid.get("imported_energy_kwh", 0.0)
        avoided_php = max(0.0, (load_kwh - grid_kwh) * tariff)
        reserve_soc = hardware.get("reserve_soc_percent", 20.0)
        array_desc = f"Your {pv_kwp:.2f} kWp solar installation" if pv_kwp > 0 else "Your solar installation"
        equip_desc = f"{panel_model} panels and {inverter_model} inverter".strip() if (panel_model or inverter_model) else "PV modules and hybrid inverter"
        return {
            "query_key": query_key,
            "title": "Energy Systems Performance Audit",
            "what_happened": f"{array_desc} generated {pv_kwh:.2f} kWh of electricity while your home consumed {load_kwh:.2f} kWh.",
            "what_data_shows": f"Measured grid imports totaled {grid_kwh:.2f} kWh across the selected telemetry window ({equip_desc}).",
            "why_it_happened": "Totals are computed via timestamp-differenced trapezoidal quadrature over recorded telemetry intervals.",
            "energy_or_money_impact": f"Estimated avoided utility charges: PHP {avoided_php:.2f} at your configured tariff." if tariff > 0 else "Configure your utility tariff or TEI rate schedule in Bill Intelligence to compute peso savings.",
            "what_to_do": f"Inspect Diagnostics for residual energy balance details and keep battery SOC within the {reserve_soc:.0f}% to 100% operational window.",
            "confidence_level": "Calculated (derived from recorded inverter telemetry)"
        }
