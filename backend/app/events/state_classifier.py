import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.time_utils import format_time_12h

def classify_operating_state(
    record: CanonicalRecord,
    reserve_soc: float = 20.0
) -> str:
    pv = record.pv_power_kw
    load = record.load_power_kw
    grid = record.grid_power_kw
    batt = record.battery_power_kw
    soc = record.soc_percent

    is_daylight = pv >= 0.1
    is_grid_importing = grid >= 0.1
    is_battery_discharging = batt >= 0.1
    is_battery_charging = batt <= -0.1
    is_at_reserve = soc <= (reserve_soc + 0.5)

    if is_daylight:
        if is_battery_charging and (pv >= load):
            return "SOLAR_SUPPLYING_LOAD_AND_CHARGING_BATTERY"
        if is_grid_importing and (load > pv):
            return "GRID_IMPORT_DURING_DAYLIGHT"
        if pv >= (load * 0.8):
            return "SOLAR_SUPPLYING_LOAD"
        return "DAYTIME_SOLAR_GENERATION"
    else:
        if is_at_reserve and is_grid_importing:
            return "GRID_IMPORT_AT_BATTERY_RESERVE"
        if is_battery_discharging and not is_grid_importing:
            return "BATTERY_DISCHARGING_SUPPLYING_LOAD"
        if is_grid_importing and not is_battery_discharging:
            return "GRID_IMPORT_SUPPLYING_LOAD"
        if is_battery_discharging and is_grid_importing:
            return "COMBINED_BATTERY_AND_GRID_SUPPLY"
        if is_at_reserve:
            return "BATTERY_IDLE_AT_RESERVE"

    return "LOW_POWER_OR_STANDBY"

def build_operating_state_timeline(
    records: List[CanonicalRecord],
    reserve_soc: float = 20.0
) -> List[Dict[str, Any]]:
    if not records:
        return []

    episodes: List[Dict[str, Any]] = []
    
    current_state = classify_operating_state(records[0], reserve_soc)
    start_time = records[0].timestamp
    readings_count = 1
    total_pv_energy = 0.0
    total_load_energy = 0.0
    total_grid_energy = 0.0
    total_disch_energy = 0.0

    for i in range(1, len(records)):
        state = classify_operating_state(records[i], reserve_soc)
        
        try:
            t0 = datetime.datetime.strptime(records[i - 1].timestamp, "%Y-%m-%d %H:%M:%S")
            t1 = datetime.datetime.strptime(records[i].timestamp, "%Y-%m-%d %H:%M:%S")
            dt_h = (t1 - t0).total_seconds() / 3600.0
        except Exception:
            dt_h = 5.0 / 60.0

        p_pv = 0.5 * (records[i - 1].pv_power_kw + records[i].pv_power_kw)
        p_load = 0.5 * (records[i - 1].load_power_kw + records[i].load_power_kw)
        p_grid = 0.5 * (max(0.0, records[i - 1].grid_power_kw) + max(0.0, records[i].grid_power_kw))
        p_disch = 0.5 * (max(0.0, records[i - 1].battery_power_kw) + max(0.0, records[i].battery_power_kw))

        total_pv_energy += p_pv * dt_h
        total_load_energy += p_load * dt_h
        total_grid_energy += p_grid * dt_h
        total_disch_energy += p_disch * dt_h

        if state != current_state:
            end_time = records[i - 1].timestamp
            try:
                st = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                et = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                duration_m = round((et - st).total_seconds() / 60.0, 1)
            except Exception:
                duration_m = round(readings_count * 5.0, 1)

            reason = _get_state_reason(current_state)

            episodes.append({
                "state": current_state,
                "start_time": start_time,
                "start_time_12h": format_time_12h(start_time),
                "end_time": end_time,
                "end_time_12h": format_time_12h(end_time),
                "duration_minutes": duration_m,
                "readings_count": readings_count,
                "pv_energy_kwh": round(total_pv_energy, 4),
                "load_energy_kwh": round(total_load_energy, 4),
                "grid_energy_kwh": round(total_grid_energy, 4),
                "battery_discharge_kwh": round(total_disch_energy, 4),
                "reason": reason
            })

            current_state = state
            start_time = records[i].timestamp
            readings_count = 1
            total_pv_energy = 0.0
            total_load_energy = 0.0
            total_grid_energy = 0.0
            total_disch_energy = 0.0
        else:
            readings_count += 1

    end_time = records[-1].timestamp
    try:
        st = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        et = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        duration_m = round((et - st).total_seconds() / 60.0, 1)
    except Exception:
        duration_m = round(readings_count * 5.0, 1)

    episodes.append({
        "state": current_state,
        "start_time": start_time,
        "start_time_12h": format_time_12h(start_time),
        "end_time": end_time,
        "end_time_12h": format_time_12h(end_time),
        "duration_minutes": duration_m,
        "readings_count": readings_count,
        "pv_energy_kwh": round(total_pv_energy, 4),
        "load_energy_kwh": round(total_load_energy, 4),
        "grid_energy_kwh": round(total_grid_energy, 4),
        "battery_discharge_kwh": round(total_disch_energy, 4),
        "reason": _get_state_reason(current_state)
    })

    return episodes

def _get_state_reason(state: str) -> str:
    reasons = {
        "SOLAR_SUPPLYING_LOAD_AND_CHARGING_BATTERY": "PV generation exceeds household demand, with surplus power directed to charge the battery bank.",
        "SOLAR_SUPPLYING_LOAD": "Solar generation matches or covers household load requirements without significant battery interaction.",
        "DAYTIME_SOLAR_GENERATION": "Solar generation active during daylight hours.",
        "BATTERY_DISCHARGING_SUPPLYING_LOAD": "Battery discharges stored energy to supply household load with zero grid import reliance.",
        "GRID_IMPORT_AT_BATTERY_RESERVE": "Battery reached reserve cutoff limit, forcing grid imports to support continuous household consumption.",
        "GRID_IMPORT_SUPPLYING_LOAD": "Household electricity supplied from the utility grid.",
        "GRID_IMPORT_DURING_DAYLIGHT": "Grid electricity imported during daylight hours, typically due to peak load exceeding inverter/solar capacity.",
        "COMBINED_BATTERY_AND_GRID_SUPPLY": "Both battery discharge and utility grid imports active simultaneously to meet heavy demand.",
        "BATTERY_IDLE_AT_RESERVE": "Battery state of charge at configured reserve limit with zero active power flow.",
        "LOW_POWER_OR_STANDBY": "Minimal power flow throughout system components."
    }
    return reasons.get(state, "Standard operational state transition.")
