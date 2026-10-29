import pytest
from backend.app.metrics.integrator import integrate_power_series, compare_integration_methods

def test_constant_power_integration():
    timestamps = [
        "2026-10-21 00:00:00",
        "2026-10-21 01:00:00",
        "2026-10-21 02:00:00",
        "2026-10-21 03:00:00"
    ]
    power = [2.0, 2.0, 2.0, 2.0]
    total_e, cum, dur = integrate_power_series(timestamps, power, method="trapezoidal")
    assert dur == 3.0
    assert total_e == 6.0
    assert cum[-1] == 6.0

def test_linear_ramp_integration():
    timestamps = [
        "2026-10-21 00:00:00",
        "2026-10-21 01:00:00",
        "2026-10-21 02:00:00"
    ]
    power = [0.0, 2.0, 4.0]
    total_trap, _, _ = integrate_power_series(timestamps, power, method="trapezoidal")
    assert total_trap == 4.0

def test_irregular_interval_integration():
    timestamps = [
        "2026-10-21 00:00:00",
        "2026-10-21 00:05:00",
        "2026-10-21 00:15:00",
        "2026-10-21 00:30:00"
    ]
    power = [1.0, 2.0, 2.0, 4.0]
    total_trap, _, dur = integrate_power_series(timestamps, power, method="trapezoidal")
    assert dur == 0.5
    comp = compare_integration_methods(timestamps, power)
    assert comp["trapezoidal_kwh"] > 0
