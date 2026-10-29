import datetime
from typing import List, Tuple, Dict, Any

def parse_iso(ts: str) -> datetime.datetime:
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return datetime.datetime.fromtimestamp(0)

def integrate_power_series(
    timestamps: List[str],
    power_kw: List[float],
    method: str = "trapezoidal",
    max_gap_hours: float = 2.0
) -> Tuple[float, List[float], float]:
    if len(timestamps) < 2 or len(power_kw) < 2:
        return 0.0, [0.0] * len(power_kw), 0.0

    dts = [parse_iso(t) for t in timestamps]
    total_energy_kwh = 0.0
    cumulative: List[float] = [0.0]
    total_duration_hours = 0.0

    for i in range(len(dts) - 1):
        dt_hours = (dts[i + 1] - dts[i]).total_seconds() / 3600.0
        
        if dt_hours <= 0:
            cumulative.append(total_energy_kwh)
            continue
            
        if dt_hours > max_gap_hours:
            cumulative.append(total_energy_kwh)
            continue

        total_duration_hours += dt_hours

        p0 = power_kw[i]
        p1 = power_kw[i + 1]

        if method == "forward_hold" or method == "rectangular":
            delta_e = p0 * dt_hours
        elif method == "backward_hold":
            delta_e = p1 * dt_hours
        else:
            delta_e = 0.5 * (p0 + p1) * dt_hours

        total_energy_kwh += delta_e
        cumulative.append(round(total_energy_kwh, 5))

    return round(total_energy_kwh, 4), cumulative, round(total_duration_hours, 2)

def compare_integration_methods(
    timestamps: List[str],
    power_kw: List[float]
) -> Dict[str, Any]:
    trap_e, _, dur = integrate_power_series(timestamps, power_kw, method="trapezoidal")
    rect_e, _, _ = integrate_power_series(timestamps, power_kw, method="rectangular")
    back_e, _, _ = integrate_power_series(timestamps, power_kw, method="backward_hold")

    diff_percent = abs(trap_e - rect_e) / trap_e * 100.0 if trap_e > 0 else 0.0

    return {
        "trapezoidal_kwh": trap_e,
        "forward_hold_kwh": rect_e,
        "backward_hold_kwh": back_e,
        "difference_kwh": round(abs(trap_e - rect_e), 4),
        "difference_percent": round(diff_percent, 2),
        "duration_hours": dur
    }
