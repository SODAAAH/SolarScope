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

    pv_kwp = sys_row["pv_capacity_kwp"] if sys_row else 6.2
    batt_kwh = sys_row["battery_capacity_kwh"] if sys_row else 16.08
    reserve_soc = sys_row["reserve_soc"] if sys_row else 20.0
    inv_kw = sys_row["inverter_power_kw"] if sys_row else 6.0
    tariff = sys_row["import_tariff"] if sys_row else 11.50
    bms_a = sys_row["bms_max_charge_a"] if sys_row else 100.0

    solar = calculate_solar_metrics(records, pv_capacity_kwp=pv_kwp)
    battery = calculate_battery_metrics(records, nominal_capacity_kwh=batt_kwh, reserve_soc=reserve_soc, bms_max_current_a=bms_a)
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
            "inverter_power_kw": inv_kw,
            "reserve_soc_percent": reserve_soc,
            "tariff_rate_php": tariff
        },
        "solar": solar,
        "battery": battery,
        "grid": grid,
        "consumption": consumption,
        "balance": balance,
        "night_load_kwh": round(night_load_kwh, 2)
    }
