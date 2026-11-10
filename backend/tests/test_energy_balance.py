import pytest
from backend.app.ingestion.models import CanonicalRecord
from backend.app.energy_balance.reconciliation import reconcile_energy_balance

def test_perfect_balance_zero_residual():
    records = [
        CanonicalRecord(
            timestamp="2025-01-15 12:00:00",
            pv_power_kw=3.0,
            load_power_kw=2.0,
            battery_power_kw=-1.0,
            grid_power_kw=0.0
        ),
        CanonicalRecord(
            timestamp="2025-01-15 13:00:00",
            pv_power_kw=3.0,
            load_power_kw=2.0,
            battery_power_kw=-1.0,
            grid_power_kw=0.0
        )
    ]
    balance = reconcile_energy_balance(records, inverter_tare_loss_kw=0.0, inverter_efficiency=1.0)
    assert balance["residual_kwh"] == 0.0
    assert balance["solar_self_consumption_ratio"] == 1.0
    assert balance["solar_self_sufficiency_ratio"] == 1.0
