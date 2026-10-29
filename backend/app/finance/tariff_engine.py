import datetime
from typing import List, Dict, Any
from backend.app.ingestion.models import CanonicalRecord

class TariffConfig:
    def __init__(
        self,
        tariff_type: str = "flat",
        flat_rate: float = 11.50,
        peak_rate: float = 14.50,
        off_peak_rate: float = 9.00,
        peak_start_hour: int = 17,
        peak_end_hour: int = 21,
        tier1_limit_kwh: float = 100.0,
        tier1_rate: float = 9.50,
        tier2_rate: float = 12.00,
        fixed_charge_monthly: float = 150.0,
        export_rate: float = 0.0,
        currency: str = "PHP"
    ):
        self.tariff_type = tariff_type
        self.flat_rate = flat_rate
        self.peak_rate = peak_rate
        self.off_peak_rate = off_peak_rate
        self.peak_start_hour = peak_start_hour
        self.peak_end_hour = peak_end_hour
        self.tier1_limit_kwh = tier1_limit_kwh
        self.tier1_rate = tier1_rate
        self.tier2_rate = tier2_rate
        self.fixed_charge_monthly = fixed_charge_monthly
        self.export_rate = export_rate
        self.currency = currency

def calculate_grid_cost(
    records: List[CanonicalRecord],
    config: TariffConfig
) -> Dict[str, Any]:
    if not records:
        return {}

    total_import_cost = 0.0
    total_export_credit = 0.0
    peak_cost = 0.0
    off_peak_cost = 0.0
    total_imported_kwh = 0.0
    total_exported_kwh = 0.0

    for i in range(len(records) - 1):
        try:
            t0 = datetime.datetime.strptime(records[i].timestamp, "%Y-%m-%d %H:%M:%S")
            t1 = datetime.datetime.strptime(records[i + 1].timestamp, "%Y-%m-%d %H:%M:%S")
            dt_h = (t1 - t0).total_seconds() / 3600.0
        except Exception:
            dt_h = 5.0 / 60.0

        p_imp = 0.5 * (max(0.0, records[i].grid_power_kw) + max(0.0, records[i + 1].grid_power_kw))
        p_exp = 0.5 * (max(0.0, -records[i].grid_power_kw) + max(0.0, -records[i + 1].grid_power_kw))

        kwh_imp = p_imp * dt_h
        kwh_exp = p_exp * dt_h

        total_imported_kwh += kwh_imp
        total_exported_kwh += kwh_exp

        if config.tariff_type == "tou":
            is_peak = (config.peak_start_hour <= t0.hour < config.peak_end_hour)
            rate = config.peak_rate if is_peak else config.off_peak_rate
            cost = kwh_imp * rate
            total_import_cost += cost
            if is_peak:
                peak_cost += cost
            else:
                off_peak_cost += cost
        else:
            total_import_cost += kwh_imp * config.flat_rate

        total_export_credit += kwh_exp * config.export_rate

    if config.tariff_type == "tiered":
        if total_imported_kwh <= (config.tier1_limit_kwh / 30.0):
            total_import_cost = total_imported_kwh * config.tier1_rate
        else:
            tier1_daily = config.tier1_limit_kwh / 30.0
            tier2_daily = total_imported_kwh - tier1_daily
            total_import_cost = (tier1_daily * config.tier1_rate) + (tier2_daily * config.tier2_rate)

    fixed_daily_charge = config.fixed_charge_monthly / 30.0
    net_daily_bill = total_import_cost + fixed_daily_charge - total_export_credit

    return {
        "total_import_cost": round(total_import_cost, 2),
        "total_export_credit": round(total_export_credit, 2),
        "fixed_daily_charge": round(fixed_daily_charge, 2),
        "net_daily_bill": round(net_daily_bill, 2),
        "estimated_monthly_bill": round(net_daily_bill * 30.0, 2),
        "peak_cost": round(peak_cost, 2),
        "off_peak_cost": round(off_peak_cost, 2),
        "currency": config.currency,
        "tariff_type": config.tariff_type,
        "effective_rate_per_kwh": round(total_import_cost / total_imported_kwh, 2) if total_imported_kwh > 0 else config.flat_rate
    }
