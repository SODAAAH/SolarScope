from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.integrator import integrate_power_series, parse_iso

def _integrate_pair(p0: float, p1: float, dt_h: float, method: str) -> float:
    if method in ("forward_hold", "rectangular"):
        return p0 * dt_h
    if method == "backward_hold":
        return p1 * dt_h
    return 0.5 * (p0 + p1) * dt_h

def reconcile_energy_balance(
    records: List[CanonicalRecord],
    inverter_efficiency: float = 0.95,
    inverter_tare_loss_kw: float = 0.07,
    method: str = "trapezoidal",
    nominal_battery_kwh: float = 0.0,
    max_gap_hours: float = 2.0
) -> Dict[str, Any]:
    if not records:
        return {}

    timestamps = [r.timestamp for r in records]
    pv_series = [r.pv_power_kw for r in records]
    load_series = [r.load_power_kw for r in records]
    grid_imp_series = [max(0.0, r.grid_power_kw) for r in records]
    grid_exp_series = [max(0.0, -r.grid_power_kw) for r in records]
    batt_disch_series = [max(0.0, r.battery_power_kw) for r in records]
    batt_chg_series = [max(0.0, -r.battery_power_kw) for r in records]
    gen_series = [r.generator_power_kw for r in records]

    pv_kwh, _, dur_h = integrate_power_series(timestamps, pv_series, method=method, max_gap_hours=max_gap_hours)
    load_kwh, _, _ = integrate_power_series(timestamps, load_series, method=method, max_gap_hours=max_gap_hours)
    grid_imp_kwh, _, _ = integrate_power_series(timestamps, grid_imp_series, method=method, max_gap_hours=max_gap_hours)
    grid_exp_kwh, _, _ = integrate_power_series(timestamps, grid_exp_series, method=method, max_gap_hours=max_gap_hours)
    batt_disch_kwh, _, _ = integrate_power_series(timestamps, batt_disch_series, method=method, max_gap_hours=max_gap_hours)
    batt_chg_kwh, _, _ = integrate_power_series(timestamps, batt_chg_series, method=method, max_gap_hours=max_gap_hours)
    gen_kwh, _, _ = integrate_power_series(timestamps, gen_series, method=method, max_gap_hours=max_gap_hours)

    total_sources_kwh = round(pv_kwh + grid_imp_kwh + batt_disch_kwh + gen_kwh, 4)
    total_sinks_kwh = round(load_kwh + batt_chg_kwh + grid_exp_kwh, 4)
    residual_kwh = round(total_sources_kwh - total_sinks_kwh, 4)
    residual_percent = round((residual_kwh / total_sources_kwh) * 100.0, 2) if total_sources_kwh > 0 else 0.0

    eff_clamped = max(0.5, min(1.0, float(inverter_efficiency or 0.95)))
    tare_kw = max(0.0, float(inverter_tare_loss_kw if inverter_tare_loss_kw is not None else 0.07))
    modeled_unmeasured_tare_kwh = round(tare_kw * dur_h, 4)
    conversion_loss_basis = pv_kwh + batt_disch_kwh + batt_chg_kwh
    modeled_conversion_loss_kwh = round(conversion_loss_basis * (1.0 - eff_clamped), 4)

    dts = [parse_iso(r.timestamp) for r in records]
    direct_solar_used_kwh = 0.0
    solar_to_batt_kwh = 0.0
    grid_to_batt_kwh = 0.0
    unattributed_batt_charge_kwh = 0.0
    solar_origin_discharge_kwh = 0.0
    grid_origin_discharge_kwh = 0.0

    init_soc = records[0].soc_percent if records else 0.0
    if nominal_battery_kwh > 0 and init_soc > 0:
        stored_solar_kwh = (init_soc / 100.0) * nominal_battery_kwh * 0.5
        stored_grid_kwh = (init_soc / 100.0) * nominal_battery_kwh * 0.5
        initial_state_unknown = init_soc > 25.0
    else:
        stored_solar_kwh = 0.0
        stored_grid_kwh = 0.0
        initial_state_unknown = init_soc > 25.0

    missing_telemetry_count = sum(
        1 for r in records
        if not r.timestamp_valid or any(c in r.missing_channels or c in r.invalid_channels for c in ("pv_power_kw", "load_power_kw", "grid_power_kw", "battery_power_kw"))
    )

    for i in range(len(records) - 1):
        t0, t1 = dts[i], dts[i + 1]
        if t0 is None or t1 is None:
            continue
        dt_h = (t1 - t0).total_seconds() / 3600.0
        if dt_h <= 0.0 or dt_h > max_gap_hours:
            continue

        r0, r1 = records[i], records[i + 1]
        e_pv = _integrate_pair(r0.pv_power_kw, r1.pv_power_kw, dt_h, method)
        e_load = _integrate_pair(r0.load_power_kw, r1.load_power_kw, dt_h, method)
        e_imp = _integrate_pair(max(0.0, r0.grid_power_kw), max(0.0, r1.grid_power_kw), dt_h, method)
        e_exp = _integrate_pair(max(0.0, -r0.grid_power_kw), max(0.0, -r1.grid_power_kw), dt_h, method)
        e_disch = _integrate_pair(max(0.0, r0.battery_power_kw), max(0.0, r1.battery_power_kw), dt_h, method)
        e_chg = _integrate_pair(max(0.0, -r0.battery_power_kw), max(0.0, -r1.battery_power_kw), dt_h, method)
        e_gen = _integrate_pair(r0.generator_power_kw, r1.generator_power_kw, dt_h, method)

        pv_retained = max(0.0, e_pv - e_exp)
        non_grid_load = max(0.0, e_load - e_imp)

        if e_chg > 0:
            if e_imp <= 0.001 and e_gen <= 0.001:
                s_chg = min(e_chg, pv_retained)
                g_chg = 0.0
            else:
                load_from_pv = min(pv_retained, max(0.0, e_load - e_imp - e_disch))
                pv_surplus = max(0.0, pv_retained - load_from_pv)
                s_chg = min(e_chg, pv_surplus)
                g_chg = min(e_chg - s_chg, e_imp + e_gen)
            rem_chg = max(0.0, e_chg - s_chg - g_chg)
            solar_to_batt_kwh += s_chg
            grid_to_batt_kwh += g_chg
            unattributed_batt_charge_kwh += rem_chg
            stored_solar_kwh += s_chg + (rem_chg * 0.5)
            stored_grid_kwh += g_chg + (rem_chg * 0.5)
            e_direct = min(non_grid_load, max(0.0, pv_retained - s_chg))
        else:
            e_direct = min(non_grid_load, pv_retained)

        direct_solar_used_kwh += e_direct

        if e_disch > 0:
            total_pool = stored_solar_kwh + stored_grid_kwh
            if total_pool > 0.001:
                solar_share = stored_solar_kwh / total_pool
            elif pv_kwh > 0 and grid_to_batt_kwh <= 0.01:
                solar_share = 1.0
            else:
                solar_share = 0.5
            s_disch = e_disch * solar_share
            g_disch = e_disch * (1.0 - solar_share)
            solar_origin_discharge_kwh += s_disch
            grid_origin_discharge_kwh += g_disch
            stored_solar_kwh = max(0.0, stored_solar_kwh - s_disch)
            stored_grid_kwh = max(0.0, stored_grid_kwh - g_disch)

    if pv_kwh > 0:
        solar_self_consumed_kwh = min(pv_kwh, direct_solar_used_kwh + solar_to_batt_kwh)
        solar_self_consumption_ratio = round(min(1.0, max(0.0, solar_self_consumed_kwh / pv_kwh)), 4)
    else:
        solar_self_consumption_ratio = 0.0

    if load_kwh > 0:
        solar_covered_load_kwh = min(load_kwh, direct_solar_used_kwh + solar_origin_discharge_kwh)
        solar_self_sufficiency_ratio = round(min(1.0, max(0.0, solar_covered_load_kwh / load_kwh)), 4)
    else:
        solar_self_sufficiency_ratio = 0.0

    if missing_telemetry_count > len(records) * 0.25:
        attribution_status = "degraded_missing_telemetry"
    elif grid_to_batt_kwh > 0.05 or unattributed_batt_charge_kwh > 0.05 or initial_state_unknown:
        attribution_status = "estimated_mixed_origin"
    else:
        attribution_status = "measured_solar_dominant"

    residuals_kw = [r.residual_power_kw for r in records]

    factors = [
        {
            "factor": "Inverter Standby / Auxiliary Tare Consumption",
            "estimated_impact_kwh": modeled_unmeasured_tare_kwh,
            "basis": "estimated",
            "assumed_parameter": f"{round(tare_kw * 1000.0, 1)} W continuous tare",
            "description": f"Modeled internal power consumption by inverter control circuits, display, and radios assuming {round(tare_kw * 1000.0, 1)} W baseline over {dur_h:.1f} h."
        },
        {
            "factor": "AC/DC Power Conversion & Roundtrip Losses",
            "estimated_impact_kwh": modeled_conversion_loss_kwh,
            "basis": "estimated",
            "assumed_parameter": f"{round(eff_clamped * 100.0, 1)}% inverter conversion efficiency",
            "description": f"Modeled dissipation across bidirectional DC-DC and DC-AC conversion stages assuming {round(eff_clamped * 100.0, 1)}% efficiency."
        },
        {
            "factor": "Measurement Topology & Sensor Boundary Skew",
            "estimated_impact_kwh": round(max(0.0, residual_kwh - modeled_unmeasured_tare_kwh - modeled_conversion_loss_kwh), 4),
            "basis": "calculated",
            "description": "Unexplained residual after modeled tare and conversion assumptions, reflecting DC vs AC sensor boundaries and polling skew."
        }
    ]

    sankey_nodes = [
        {"name": "Solar PV"},
        {"name": "Grid Import"},
        {"name": "Battery Discharge"},
        {"name": "Hybrid Inverter"},
        {"name": "Household Consumption"},
        {"name": "Battery Charge"},
        {"name": "Grid Export"},
        {"name": "Reconciliation Residual"}
    ]

    sankey_links = [
        {"source": "Solar PV", "target": "Hybrid Inverter", "value": round(pv_kwh, 2)},
        {"source": "Grid Import", "target": "Hybrid Inverter", "value": round(grid_imp_kwh, 2)},
        {"source": "Battery Discharge", "target": "Hybrid Inverter", "value": round(batt_disch_kwh, 2)},
        {"source": "Hybrid Inverter", "target": "Household Consumption", "value": round(load_kwh, 2)},
        {"source": "Hybrid Inverter", "target": "Battery Charge", "value": round(batt_chg_kwh, 2)},
        {"source": "Hybrid Inverter", "target": "Grid Export", "value": round(grid_exp_kwh, 2)},
        {"source": "Hybrid Inverter", "target": "Reconciliation Residual", "value": max(0.01, round(abs(residual_kwh), 2))}
    ]

    return {
        "pv_kwh": pv_kwh,
        "grid_imported_kwh": grid_imp_kwh,
        "grid_exported_kwh": grid_exp_kwh,
        "battery_discharged_kwh": batt_disch_kwh,
        "battery_charged_kwh": batt_chg_kwh,
        "battery_solar_charged_kwh": round(solar_to_batt_kwh, 4),
        "battery_grid_charged_kwh": round(grid_to_batt_kwh, 4),
        "solar_origin_discharge_kwh": round(solar_origin_discharge_kwh, 4),
        "grid_origin_discharge_kwh": round(grid_origin_discharge_kwh, 4),
        "generator_kwh": gen_kwh,
        "household_demand_kwh": load_kwh,
        "total_sources_kwh": total_sources_kwh,
        "total_sinks_kwh": total_sinks_kwh,
        "residual_kwh": residual_kwh,
        "residual_percent": residual_percent,
        "contributing_factors": factors,
        "direct_solar_used_kwh": round(direct_solar_used_kwh, 4),
        "solar_self_consumption_ratio": solar_self_consumption_ratio,
        "solar_self_sufficiency_ratio": solar_self_sufficiency_ratio,
        "attribution_status": attribution_status,
        "assumptions": {
            "inverter_efficiency_assumed": eff_clamped,
            "inverter_tare_loss_kw_assumed": tare_kw,
            "modeled_tare_kwh": modeled_unmeasured_tare_kwh,
            "modeled_conversion_loss_kwh": modeled_conversion_loss_kwh,
            "measured_vs_estimated_note": "Energy totals (kWh) are integrated from telemetry; tare, conversion loss, and mixed-source battery attribution are modeled estimates."
        },
        "residuals_kw": residuals_kw,
        "sankey_data": {
            "nodes": sankey_nodes,
            "links": sankey_links
        }
    }
