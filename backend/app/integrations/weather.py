import json
import datetime
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from backend.app.storage.db import get_connection

DEFAULT_LAT = 15.48
DEFAULT_LON = 120.60
DEFAULT_TZ = "Asia/Manila"

def get_weather_intelligence(
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    installed_kwp: float = 6.2,
    battery_capacity_kwh: float = 16.08,
    reserve_soc: float = 20.0,
    current_soc: float = 50.0,
    daily_consumption_kwh: float = 22.0
) -> Dict[str, Any]:
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    tomorrow_str = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    conn = get_connection()
    cached = conn.execute(
        "SELECT * FROM weather_cache WHERE date_str = ? ORDER BY fetched_at DESC LIMIT 1",
        (today_str,)
    ).fetchone()
    conn.close()

    weather_data = None
    if cached:
        try:
            weather_data = json.loads(cached["hourly_data_json"])
        except Exception:
            weather_data = None

    if not weather_data:
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                f"&hourly=shortwave_radiation,direct_normal_irradiance,diffuse_radiation,cloud_cover,temperature_2m,precipitation"
                f"&forecast_days=2&timezone=Asia%2FManila"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "SolarScope/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                weather_data = json.loads(response.read().decode("utf-8"))
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                c_conn = get_connection()
                c_conn.execute(
                    """INSERT INTO weather_cache (id, latitude, longitude, date_str, hourly_data_json, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"weather-{today_str}", lat, lon, today_str, json.dumps(weather_data), now_iso)
                )
                c_conn.commit()
                c_conn.close()
        except Exception:
            weather_data = None

    if not weather_data or "hourly" not in weather_data:
        weather_data = _generate_synthetic_weather(today_str, tomorrow_str)

    hourly = weather_data.get("hourly", {})
    times = hourly.get("time", [])
    radiations = hourly.get("shortwave_radiation", [])
    cloud_covers = hourly.get("cloud_cover", [])
    temperatures = hourly.get("temperature_2m", [])

    today_hours = [i for i, t in enumerate(times) if t.startswith(today_str)]
    tomorrow_hours = [i for i, t in enumerate(times) if t.startswith(tomorrow_str)]

    current_hour_idx = datetime.datetime.now().hour
    current_cloud = cloud_covers[current_hour_idx] if current_hour_idx < len(cloud_covers) else 25.0
    current_radiation = radiations[current_hour_idx] if current_hour_idx < len(radiations) else 450.0
    current_temp = temperatures[current_hour_idx] if current_hour_idx < len(temperatures) else 30.5

    tomorrow_radiation_sum = sum(radiations[i] for i in tomorrow_hours if i < len(radiations)) if tomorrow_hours else 5500.0
    tomorrow_avg_cloud = (sum(cloud_covers[i] for i in tomorrow_hours if i < len(cloud_covers)) / len(tomorrow_hours)) if tomorrow_hours else 30.0

    raw_solar_kwh = (tomorrow_radiation_sum / 1000.0) * (installed_kwp / 1.0) * 0.78
    cloud_penalty = 1.0 - (tomorrow_avg_cloud / 100.0) * 0.35
    expected_pv_kwh = max(8.0, round(raw_solar_kwh * cloud_penalty, 2))
    conservative_pv_kwh = round(expected_pv_kwh * 0.82, 2)
    optimistic_pv_kwh = round(expected_pv_kwh * 1.15, 2)

    daytime_load_kwh = daily_consumption_kwh * 0.55
    surplus_for_battery = max(0.0, expected_pv_kwh - daytime_load_kwh)
    energy_needed_for_full_battery = max(0.0, ((100.0 - current_soc) / 100.0) * battery_capacity_kwh)

    if surplus_for_battery >= energy_needed_for_full_battery:
        prob_full_charge = min(98.0, round(85.0 + (surplus_for_battery - energy_needed_for_full_battery) * 2.0, 1))
        projected_sunset_soc = 100.0
    else:
        fraction = surplus_for_battery / energy_needed_for_full_battery if energy_needed_for_full_battery > 0 else 1.0
        prob_full_charge = max(15.0, round(fraction * 80.0, 1))
        added_soc = (surplus_for_battery / battery_capacity_kwh) * 100.0
        projected_sunset_soc = min(100.0, round(current_soc + added_soc, 1))

    night_load_kwh = daily_consumption_kwh * 0.45
    avg_night_power_kw = night_load_kwh / 12.0 if night_load_kwh > 0 else 0.8
    usable_at_sunset = max(0.0, ((projected_sunset_soc - reserve_soc) / 100.0) * battery_capacity_kwh)
    night_autonomy_hours = round(usable_at_sunset / avg_night_power_kw, 1) if avg_night_power_kw > 0 else 12.0
    night_autonomy_hours = min(24.0, night_autonomy_hours)

    whole_h = int(night_autonomy_hours)
    mins = int(round((night_autonomy_hours - whole_h) * 60))
    autonomy_formatted = f"{whole_h}h {mins}m"

    hourly_forecast = []
    for idx in tomorrow_hours:
        if idx < len(times):
            t_str = times[idx]
            h = int(t_str[11:13])
            rad = radiations[idx] if idx < len(radiations) else 0.0
            cld = cloud_covers[idx] if idx < len(cloud_covers) else 0.0
            tmp = temperatures[idx] if idx < len(temperatures) else 28.0
            est_pv = round((rad / 1000.0) * installed_kwp * 0.80 * (1.0 - (cld / 100.0) * 0.35), 2)
            hourly_forecast.append({
                "time": t_str,
                "hour": h,
                "solar_radiation_wm2": round(rad, 1),
                "cloud_cover_percent": round(cld, 1),
                "temperature_c": round(tmp, 1),
                "estimated_pv_power_kw": max(0.0, est_pv)
            })

    return {
        "location": "Tarlac City, Central Luzon, Philippines",
        "latitude": lat,
        "longitude": lon,
        "timezone": DEFAULT_TZ,
        "current_conditions": {
            "cloud_cover_percent": round(current_cloud, 1),
            "solar_radiation_wm2": round(current_radiation, 1),
            "temperature_c": round(current_temp, 1)
        },
        "tomorrow_forecast": {
            "date": tomorrow_str,
            "average_cloud_cover_percent": round(tomorrow_avg_cloud, 1),
            "expected_solar_kwh": expected_pv_kwh,
            "conservative_solar_kwh": conservative_pv_kwh,
            "optimistic_solar_kwh": optimistic_pv_kwh,
            "probability_full_charge_percent": prob_full_charge,
            "projected_sunset_soc_percent": projected_sunset_soc,
            "projected_night_autonomy_hours": night_autonomy_hours,
            "projected_night_autonomy_formatted": autonomy_formatted
        },
        "hourly_forecast": hourly_forecast
    }

def _generate_synthetic_weather(today_str: str, tomorrow_str: str) -> Dict[str, Any]:
    times = []
    radiations = []
    cloud_covers = []
    temperatures = []
    for day in [today_str, tomorrow_str]:
        for h in range(24):
            times.append(f"{day}T{h:02d}:00")
            if 6 <= h <= 18:
                zenith_factor = 1.0 - abs(h - 12) / 6.0
                rad = max(0.0, zenith_factor * 850.0)
                cld = 25.0 + abs(h - 14) * 3.0
                tmp = 26.0 + zenith_factor * 8.0
            else:
                rad = 0.0
                cld = 35.0
                tmp = 24.5
            radiations.append(rad)
            cloud_covers.append(cld)
            temperatures.append(tmp)

    return {
        "hourly": {
            "time": times,
            "shortwave_radiation": radiations,
            "cloud_cover": cloud_covers,
            "temperature_2m": temperatures
        }
    }

