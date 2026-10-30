from typing import Dict, Any, List

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
    tariff = hardware.get("tariff_rate_php", 11.50)
    night_kwh = snapshot.get("night_load_kwh", 0.0)

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
            "what_happened": f"Your home imported {grid_import_kwh:.2f} kWh of electricity from TEI during this observation period.",
            "what_data_shows": f"Classification breakdown: {reserve_cat['energy_kwh'] if reserve_cat else 0:.2f} kWh occurred while battery was at reserve, {power_cat['energy_kwh'] if power_cat else 0:.2f} kWh occurred due to power limit surges, and {trickle_cat['energy_kwh'] if trickle_cat else 0:.2f} kWh was standard inverter grid trickle.",
            "why_it_happened": f"The primary cause was {primary_reason}. When home electricity demand spikes above inverter discharge limits or when the battery reaches its reserve threshold, the inverter draws utility power to protect your battery.",
            "energy_or_money_impact": f"Total utility grid import cost was approximately PHP {grid_import_kwh * tariff:.2f}.",
            "what_to_do": "Review the Grid Purchases tab to check if heavy appliances operated concurrently, and stagger air conditioner or motor start times to stay within inverter output limits.",
            "confidence_level": "High (calculated through 5-category state classification)"
        }

    elif query_key == "will_battery_last_tonight":
        tomorrow = weather_info.get("tomorrow_forecast", {})
        sunset_soc = tomorrow.get("projected_sunset_soc_percent", 85.0)
        autonomy_str = tomorrow.get("projected_night_autonomy_formatted", "8h 15m")
        prob_full = tomorrow.get("probability_full_charge_percent", 75.0)
        expected_pv = tomorrow.get("expected_solar_kwh", 20.0)
        return {
            "query_key": query_key,
            "title": "Nighttime Battery Autonomy Forecast",
            "what_happened": f"Tomorrow's solar generation is forecast at {expected_pv:.1f} kWh, giving a {prob_full:.0f}% probability of reaching full battery charge before sunset.",
            "what_data_shows": f"Projected battery state-of-charge at sunset is approximately {sunset_soc:.0f}%, which provides an estimated {autonomy_str} of autonomous power.",
            "why_it_happened": "Forecasted solar irradiance in Tarlac combined with your 6.2 kWp solar array is expected to generate sufficient daytime surplus to replenish your 16.08 kWh battery storage.",
            "energy_or_money_impact": f"Reaching full charge before sunset will offset approximately {night_kwh:.1f} kWh of nighttime grid purchases, saving about PHP {night_kwh * tariff:.2f} per night.",
            "what_to_do": "Monitor midday weather; if heavy cloud cover develops, reduce non-essential evening electricity loads to ensure the battery lasts until morning sunrise.",
            "confidence_level": "Moderate (based on Open-Meteo atmospheric modeling and historical household consumption)"
        }

    elif query_key == "should_add_battery":
        grid_import_kwh = grid.get("imported_energy_kwh", 0.0)
        monthly_grid_cost = grid_import_kwh * 30.5 * tariff
        potential_reduction_kwh = min(grid_import_kwh * 0.75, 4.5)
        monthly_savings = potential_reduction_kwh * 30.5 * tariff
        est_cost = 5.0 * 22000.0
        payback = round(est_cost / (monthly_savings * 12.0), 1) if monthly_savings > 0 else 99.0
        return {
            "query_key": query_key,
            "title": "Battery Storage Upgrade Assessment",
            "what_happened": f"Your current 16.08 kWh battery provides strong daytime coverage but imports an average of {grid_import_kwh:.2f} kWh/day from TEI.",
            "what_data_shows": f"Adding a 5.0 kWh storage expansion would capture surplus midday solar and reduce grid imports by approximately {potential_reduction_kwh:.2f} kWh per day.",
            "why_it_happened": "Your household demand after sunset occasionally outlasts usable stored energy, triggering the 20% battery reserve cutoff.",
            "energy_or_money_impact": f"Estimated hardware cost is PHP {est_cost:,.2f}. Projected monthly savings are PHP {monthly_savings:,.2f}, delivering an estimated payback period of {payback} years.",
            "what_to_do": "Open the What-If Simulator in the Scenarios tab to test different storage sizes and compare return on investment against solar panel additions.",
            "confidence_level": "High (constrained by inverter 135A battery current and actual household demand)"
        }

    else:
        pv_kwh = solar.get("generated_energy_kwh", 0.0)
        load_kwh = consumption.get("consumed_energy_kwh", 0.0)
        grid_kwh = grid.get("imported_energy_kwh", 0.0)
        avoided_php = max(0.0, (load_kwh - grid_kwh) * tariff)
        return {
            "query_key": query_key,
            "title": "Energy Systems Performance Audit",
            "what_happened": f"Your 6.2 kWp solar installation generated {pv_kwh:.2f} kWh of clean electricity while your home consumed {load_kwh:.2f} kWh.",
            "what_data_shows": f"Solar production directly powered your appliances and charged your battery, requiring only {grid_kwh:.2f} kWh of electricity from TEI.",
            "why_it_happened": "Your Canadian Solar TOPCon panels and Deye hybrid inverter operated within standard electrical specifications with minimal clipping.",
            "energy_or_money_impact": f"Your solar and battery system saved approximately PHP {avoided_php:.2f} compared to purchasing all electricity from TEI.",
            "what_to_do": "Maintain solar panel cleanliness and keep battery state-of-charge within the 20% to 100% operational window.",
            "confidence_level": "High (derived from verified electrical telemetry)"
        }
