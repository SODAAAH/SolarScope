from typing import Dict, Any, List
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.solar_metrics import calculate_solar_metrics
from backend.app.metrics.battery_metrics import calculate_battery_metrics
from backend.app.metrics.grid_metrics import calculate_grid_metrics
from backend.app.metrics.consumption_metrics import calculate_consumption_metrics
from backend.app.energy_balance.reconciliation import reconcile_energy_balance
from backend.app.storage.db import get_connection

def extract_system_snapshot(records: List[CanonicalRecord], project_id: str = "default") -> Dict[str, Any]:
    if not records:
        return {}

    conn = get_connection()
    sys_row = conn.execute("SELECT * FROM system_settings WHERE project_id = ?", (project_id,)).fetchone()
    conn.close()

    keys = sys_row.keys() if sys_row else []
    pv_kwp = float(sys_row["pv_capacity_kwp"] or 0.0) if "pv_capacity_kwp" in keys else 0.0
    batt_kwh = float(sys_row["battery_capacity_kwh"] or 0.0) if "battery_capacity_kwh" in keys else 0.0
    reserve_soc = float(sys_row["reserve_soc"] if sys_row["reserve_soc"] is not None else 20.0) if "reserve_soc" in keys else 20.0
    inv_kw = float(sys_row["inverter_power_kw"] or 0.0) if "inverter_power_kw" in keys else 0.0
    tariff = float(sys_row["import_tariff"] or 0.0) if "import_tariff" in keys else 0.0
    bms_a = float(sys_row["bms_max_charge_a"] or 0.0) if "bms_max_charge_a" in keys else 0.0
    batt_v = float(sys_row["battery_voltage"] or 0.0) if "battery_voltage" in keys else 0.0
    inv_max_a = float(sys_row["inverter_max_battery_current_a"] or 0.0) if "inverter_max_battery_current_a" in keys else 0.0
    location_name = (sys_row["location_name"] or "").strip() if "location_name" in keys else ""
    panel_model = (sys_row["panel_model"] or "").strip() if "panel_model" in keys else ""
    inverter_model = (sys_row["inverter_model"] or "").strip() if "inverter_model" in keys else ""
    battery_model = (sys_row["battery_model"] or "").strip() if "battery_model" in keys else ""

    solar = calculate_solar_metrics(records, pv_capacity_kwp=pv_kwp, inverter_rating_kw=inv_kw)
    battery = calculate_battery_metrics(
        records,
        nominal_capacity_kwh=batt_kwh,
        reserve_soc=reserve_soc,
        bms_max_current_a=bms_a,
        battery_voltage=batt_v
    )
    grid = calculate_grid_metrics(records, reserve_soc=reserve_soc, inverter_power_kw=inv_kw, import_tariff=tariff)
    consumption = calculate_consumption_metrics(records)
    balance = reconcile_energy_balance(records)

    night_records = []
    for r in records:
        try:
            h = int(r.timestamp[11:13])
            if h >= 20 or h < 6:
                night_records.append(r)
        except Exception:
            continue

    night_load_kwh = 0.0
    for i in range(len(night_records) - 1):
        avg_load = 0.5 * (night_records[i].load_power_kw + night_records[i + 1].load_power_kw)
        night_load_kwh += avg_load * (5.0 / 60.0)

    return {
        "hardware": {
            "pv_capacity_kwp": pv_kwp,
            "battery_capacity_kwh": batt_kwh,
            "battery_voltage": batt_v,
            "inverter_power_kw": inv_kw,
            "inverter_max_battery_current_a": inv_max_a,
            "bms_max_charge_a": bms_a,
            "reserve_soc_percent": reserve_soc,
            "tariff_rate_php": tariff,
            "location_name": location_name,
            "panel_model": panel_model,
            "inverter_model": inverter_model,
            "battery_model": battery_model
        },
        "solar": solar,
        "battery": battery,
        "grid": grid,
        "consumption": consumption,
        "balance": balance,
        "night_load_kwh": round(night_load_kwh, 2)
    }
