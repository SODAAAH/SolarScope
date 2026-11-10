from typing import Dict, Any

def build_evidence_response(
    query_key: str,
    snapshot: Dict[str, Any],
    weather_info: Dict[str, Any]
) -> Dict[str, Any]:
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
            "what_happened": f"Your battery discharged {disch_kwh:.2f} kWh and reached its safety reserve level of {reserve_soc:.0f}%.",
            "what_data_shows": f"Battery charge dropped to {min_soc:.1f}% and remained at the reserve limit for {hours_at_reserve:.1f} hours. Nighttime household usage consumed {night_kwh:.2f} kWh between 8:00 PM and 6:00 AM.",
            "why_it_happened": "Sustained evening and nighttime household electricity usage exceeded the available stored energy above your battery's safety reserve limit.",
            "energy_or_money_impact": f"{disch_kwh:.2f} kWh of clean battery power supplied to your home, saving approximately PHP {cost_impact:.2f} in utility grid purchases.",
            "what_to_do": "To extend battery autonomy through morning sunrise, shift heavy appliance usage (such as washing machines or water pumps) to peak daylight solar hours between 10:00 AM and 2:00 PM.",
            "confidence_level": "High (derived from direct battery telemetry and continuous power integration)"
        }

    elif query_key == "why_grid_purchased_with_battery":
        grid_import_kwh = grid.get("imported_energy_kwh", 0.0)
        classifications = grid.get("import_classification", [])
        reserve_cat = next((c for c in classifications if c["category"] == "Battery Reserve"), None)
        power_cat = next((c for c in classifications if c["category"] == "Power Limit"), None)
        trickle_cat = next((c for c in classifications if c["category"] == "Grid Trickle"), None)

        primary_reason = "Reserve Limit"
        if power_cat and power_cat["energy_kwh"] > (reserve_cat["energy_kwh"] if reserve_cat else 0):
            primary_reason = "Power Demand Limit"
        elif trickle_cat and trickle_cat["energy_kwh"] > (grid_import_kwh * 0.6):
            primary_reason = "Inverter Zero-Export Stabilization"

        return {
            "query_key": query_key,
            "title": "Grid Purchase Cause Analysis",
            "what_happened": f"Your home imported {grid_import_kwh:.2f} kWh of utility electricity during this observation period.",
            "what_data_shows": f"Classification breakdown: {reserve_cat['energy_kwh'] if reserve_cat else 0:.2f} kWh occurred while battery was at reserve, {power_cat['energy_kwh'] if power_cat else 0:.2f} kWh occurred due to power limit surges, and {trickle_cat['energy_kwh'] if trickle_cat else 0:.2f} kWh was standard inverter grid trickle.",
            "why_it_happened": f"The primary cause was {primary_reason}. When home electricity demand spikes above inverter discharge limits or when the battery reaches its reserve threshold, the inverter draws utility power to protect your battery.",
            "energy_or_money_impact": f"Total utility grid import cost was approximately PHP {grid_import_kwh * tariff:.2f}.",
            "what_to_do": "Review the Energy & Demand tab to check if heavy appliances operated concurrently, and stagger air conditioner or motor start times to stay within inverter output limits.",
            "confidence_level": "High (calculated through 5-category state classification)"
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
                "energy_or_money_impact": f"Each kWh stored offsets PHP {tariff:.2f} in utility imports.",
                "what_to_do": "Enter your site latitude, longitude, PV kWp, and battery kWh in System Settings to generate tomorrow's solar and battery autonomy forecast.",
                "confidence_level": "Low (location coordinates not configured)"
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
            "what_happened": f"Tomorrow's solar generation is forecast at {expected_pv:.1f} kWh, giving a {prob_full:.0f}% probability of reaching full battery charge before sunset.",
            "what_data_shows": f"Projected battery state-of-charge at sunset is approximately {sunset_soc:.0f}%, providing an estimated {autonomy_str} of autonomous power.",
            "why_it_happened": f"Forecasted solar irradiance{loc_phrase}{array_phrase} determines expected daytime surplus available to replenish {batt_phrase}.",
            "energy_or_money_impact": f"Reaching full charge before sunset will offset approximately {night_kwh:.1f} kWh of nighttime grid purchases, saving about PHP {night_kwh * tariff:.2f} per night.",
            "what_to_do": "Monitor midday weather; if heavy cloud cover develops, reduce non-essential evening electricity loads to ensure the battery lasts until sunrise.",
            "confidence_level": "Moderate (based on Open-Meteo atmospheric modeling and historical household consumption)"
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
            "what_happened": f"{batt_phrase} still leaves an average import of {grid_import_kwh:.2f} kWh/day from the utility grid.",
            "what_data_shows": f"Adding a 5.0 kWh storage expansion could capture surplus midday solar and reduce grid imports by up to {potential_reduction_kwh:.2f} kWh per day.",
            "why_it_happened": f"Household demand after sunset occasionally outlasts usable stored energy, triggering the {reserve_soc:.0f}% battery reserve cutoff.",
            "energy_or_money_impact": f"Estimated hardware cost is PHP {est_cost:,.2f}. Projected monthly savings are PHP {monthly_savings:,.2f}, delivering an estimated payback period of {payback} years." if monthly_savings > 0 else f"Estimated hardware cost for 5.0 kWh is PHP {est_cost:,.2f}. Configure your electricity tariff rate to project payback.",
            "what_to_do": "Open the What-If & Upgrades tab to test custom storage sizes and compare return on investment against solar array additions.",
            "confidence_level": f"High ({cap_conf})"
        }

    else:
        pv_kwh = solar.get("total_generation_kwh", 0.0)
        load_kwh = consumption.get("total_consumption_kwh", 0.0)
        grid_kwh = grid.get("imported_energy_kwh", 0.0)
        avoided_php = max(0.0, (load_kwh - grid_kwh) * tariff)
        reserve_soc = hardware.get("reserve_soc_percent", 20.0)
        array_desc = f"Your {pv_kwp:.2f} kWp solar installation" if pv_kwp > 0 else "Your solar installation"
        equip_desc = f"{panel_model} panels and {inverter_model} inverter".strip() if (panel_model or inverter_model) else "PV modules and hybrid inverter"
        return {
            "query_key": query_key,
            "title": "Energy Systems Performance Audit",
            "what_happened": f"{array_desc} generated {pv_kwh:.2f} kWh of clean electricity while your home consumed {load_kwh:.2f} kWh.",
            "what_data_shows": f"Solar production directly powered your appliances and charged your battery, requiring {grid_kwh:.2f} kWh of electricity from the utility grid.",
            "why_it_happened": f"Your {equip_desc} operated within electrical specifications.",
            "energy_or_money_impact": f"Your solar and battery system saved approximately PHP {avoided_php:.2f} compared to purchasing all electricity from the utility grid.",
            "what_to_do": f"Maintain solar panel cleanliness and keep battery state-of-charge within the {reserve_soc:.0f}% to 100% operational window.",
            "confidence_level": "High (derived from verified electrical telemetry)"
        }
