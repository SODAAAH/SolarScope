from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord
from backend.app.metrics.integrator import integrate_power_series

def reconcile_energy_balance(
    records: List[CanonicalRecord],
    inverter_efficiency: float = 0.95,
    inverter_tare_loss_kw: float = 0.07,
    method: str = "trapezoidal"
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

    pv_kwh, _, dur_h = integrate_power_series(timestamps, pv_series, method=method)
    load_kwh, _, _ = integrate_power_series(timestamps, load_series, method=method)
    grid_imp_kwh, _, _ = integrate_power_series(timestamps, grid_imp_series, method=method)
    grid_exp_kwh, _, _ = integrate_power_series(timestamps, grid_exp_series, method=method)
    batt_disch_kwh, _, _ = integrate_power_series(timestamps, batt_disch_series, method=method)
    batt_chg_kwh, _, _ = integrate_power_series(timestamps, batt_chg_series, method=method)
    gen_kwh, _, _ = integrate_power_series(timestamps, gen_series, method=method)

    total_sources_kwh = round(pv_kwh + grid_imp_kwh + batt_disch_kwh + gen_kwh, 4)
    total_sinks_kwh = round(load_kwh + batt_chg_kwh + grid_exp_kwh, 4)
    residual_kwh = round(total_sources_kwh - total_sinks_kwh, 4)
    residual_percent = round((residual_kwh / total_sources_kwh) * 100.0, 2) if total_sources_kwh > 0 else 0.0

    modeled_unmeasured_tare_kwh = round(inverter_tare_loss_kw * dur_h, 4)
    conversion_loss_basis = pv_kwh + batt_disch_kwh + batt_chg_kwh
    modeled_conversion_loss_kwh = round(conversion_loss_basis * (1.0 - inverter_efficiency), 4)

    direct_solar_used_kwh = max(0.0, min(pv_kwh - batt_chg_kwh - grid_exp_kwh, load_kwh))
    solar_self_consumption_ratio = round((direct_solar_used_kwh + batt_chg_kwh) / pv_kwh, 4) if pv_kwh > 0 else 0.0
    solar_self_sufficiency_ratio = round((direct_solar_used_kwh + batt_disch_kwh) / load_kwh, 4) if load_kwh > 0 else 0.0

    residuals_kw = [r.residual_power_kw for r in records]

    factors = [
        {
            "factor": "Inverter Standby / Auxiliary Tare Consumption",
            "estimated_impact_kwh": modeled_unmeasured_tare_kwh,
            "description": "Continuous internal power consumption by inverter control circuits, display, communication radios, and sensor electronics (observed ~70 W baseline even when solar is idle)."
        },
        {
            "factor": "AC/DC Power Conversion & Roundtrip Losses",
            "estimated_impact_kwh": modeled_conversion_loss_kwh,
            "description": "Dissipation losses across bidirectional DC-DC charge controllers and DC-AC inversion bridges during daytime PV generation and battery cycling."
        },
        {
            "factor": "Measurement Topology & Sensor Boundary Skew",
            "estimated_impact_kwh": round(max(0.0, residual_kwh - modeled_unmeasured_tare_kwh - modeled_conversion_loss_kwh), 4),
            "description": "Discrepancies arising from differing physical measurement points (DC bus terminals vs AC breaker panel CT clamps) and telemetry polling delays across channels."
        }
    ]

    sankey_nodes = [
        {"name": "Solar PV"},
        {"name": "Grid Import"},
        {"name": "Battery Discharge"},
        {"name": "Hybrid Inverter"},
        {"name": "Household Consumption"},
        {"name": "Battery Charge"},
        {"name": "Reconciliation Residual"}
    ]
    
    sankey_links = [
        {"source": "Solar PV", "target": "Hybrid Inverter", "value": round(pv_kwh, 2)},
        {"source": "Grid Import", "target": "Hybrid Inverter", "value": round(grid_imp_kwh, 2)},
        {"source": "Battery Discharge", "target": "Hybrid Inverter", "value": round(batt_disch_kwh, 2)},
        {"source": "Hybrid Inverter", "target": "Household Consumption", "value": round(load_kwh, 2)},
        {"source": "Hybrid Inverter", "target": "Battery Charge", "value": round(batt_chg_kwh, 2)},
        {"source": "Hybrid Inverter", "target": "Reconciliation Residual", "value": max(0.01, round(residual_kwh, 2))}
    ]

    return {
        "pv_kwh": pv_kwh,
        "grid_imported_kwh": grid_imp_kwh,
        "grid_exported_kwh": grid_exp_kwh,
        "battery_discharged_kwh": batt_disch_kwh,
        "battery_charged_kwh": batt_chg_kwh,
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
        "residuals_kw": residuals_kw,
        "sankey_data": {
            "nodes": sankey_nodes,
            "links": sankey_links
        }
    }
