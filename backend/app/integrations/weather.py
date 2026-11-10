import json
import datetime
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, List, Optional
from backend.app.storage.db import get_connection

def get_weather_intelligence(
    lat: float = 0.0,
    lon: float = 0.0,
    location_name: str = "",
    timezone_str: str = "Asia/Manila",
    installed_kwp: float = 0.0,
    battery_capacity_kwh: float = 0.0,
    reserve_soc: float = 20.0,
    current_soc: float = 0.0,
    daily_consumption_kwh: float = 0.0
) -> Dict[str, Any]:
    tz_clean = (timezone_str or "Asia/Manila").strip()
    loc_label = (location_name or "").strip()

    if lat == 0.0 and lon == 0.0:
        return {
            "configured": False,
            "status": "unconfigured",
            "message": "Set latitude and longitude in System Settings to load local solar irradiance forecasts.",
            "location": loc_label or "Location Not Configured",
            "latitude": 0.0,
            "longitude": 0.0,
            "timezone": tz_clean,
            "current_conditions": None,
            "tomorrow_forecast": None,
            "hourly_forecast": []
        }

    today_dt = datetime.datetime.now().date()
    today_str = today_dt.strftime("%Y-%m-%d")
    tomorrow_str = (today_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    conn = get_connection()
    cached = conn.execute(
        """SELECT * FROM weather_cache
           WHERE date_str = ? AND ABS(latitude - ?) < 0.001 AND ABS(longitude - ?) < 0.001
           ORDER BY fetched_at DESC LIMIT 1""",
        (today_str, lat, lon)
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
            tz_param = urllib.parse.quote(tz_clean, safe="")
            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                f"&hourly=shortwave_radiation,direct_normal_irradiance,diffuse_radiation,cloud_cover,temperature_2m,precipitation"
                f"&forecast_days=2&timezone={tz_param}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "SolarScope/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                weather_data = json.loads(response.read().decode("utf-8"))
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cache_id = f"weather-{lat:.4f}:{lon:.4f}:{today_str}"
                c_conn = get_connection()
                c_conn.execute(
                    """INSERT OR REPLACE INTO weather_cache (id, latitude, longitude, date_str, hourly_data_json, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (cache_id, lat, lon, today_str, json.dumps(weather_data), now_iso)
                )
                c_conn.commit()
                c_conn.close()
        except Exception:
            weather_data = None

    if not weather_data or "hourly" not in weather_data:
        return {
            "configured": True,
            "status": "error",
            "message": "Unable to fetch local irradiance data from Open-Meteo.",
            "location": loc_label or f"{lat:.4f}, {lon:.4f}",
            "latitude": lat,
            "longitude": lon,
            "timezone": tz_clean,
            "current_conditions": None,
            "tomorrow_forecast": None,
            "hourly_forecast": []
        }

    hourly = weather_data.get("hourly", {})
    times = hourly.get("time", [])
    radiations = hourly.get("shortwave_radiation", [])
    cloud_covers = hourly.get("cloud_cover", [])
    temperatures = hourly.get("temperature_2m", [])

    tomorrow_hours = [i for i, t in enumerate(times) if t.startswith(tomorrow_str)]

    current_hour_idx = datetime.datetime.now().hour
    current_cloud = float(cloud_covers[current_hour_idx]) if current_hour_idx < len(cloud_covers) and cloud_covers[current_hour_idx] is not None else 0.0
    current_radiation = float(radiations[current_hour_idx]) if current_hour_idx < len(radiations) and radiations[current_hour_idx] is not None else 0.0
    current_temp = float(temperatures[current_hour_idx]) if current_hour_idx < len(temperatures) and temperatures[current_hour_idx] is not None else 0.0

    tomorrow_rad_vals = [float(radiations[i]) for i in tomorrow_hours if i < len(radiations) and radiations[i] is not None]
    tomorrow_cld_vals = [float(cloud_covers[i]) for i in tomorrow_hours if i < len(cloud_covers) and cloud_covers[i] is not None]

    tomorrow_radiation_sum = sum(tomorrow_rad_vals)
    tomorrow_avg_cloud = (sum(tomorrow_cld_vals) / len(tomorrow_cld_vals)) if tomorrow_cld_vals else 0.0

    if installed_kwp > 0:
        raw_solar_kwh = (tomorrow_radiation_sum / 1000.0) * installed_kwp * 0.78
        cloud_penalty = 1.0 - (tomorrow_avg_cloud / 100.0) * 0.35
        expected_pv_kwh = max(0.0, round(raw_solar_kwh * cloud_penalty, 2))
        conservative_pv_kwh = round(expected_pv_kwh * 0.82, 2)
        optimistic_pv_kwh = round(expected_pv_kwh * 1.15, 2)
    else:
        expected_pv_kwh = 0.0
        conservative_pv_kwh = 0.0
        optimistic_pv_kwh = 0.0

    daytime_load_kwh = daily_consumption_kwh * 0.55 if daily_consumption_kwh > 0 else 0.0
    surplus_for_battery = max(0.0, expected_pv_kwh - daytime_load_kwh)

    if battery_capacity_kwh > 0:
        energy_needed_for_full_battery = max(0.0, ((100.0 - current_soc) / 100.0) * battery_capacity_kwh)
        if surplus_for_battery >= energy_needed_for_full_battery and expected_pv_kwh > 0:
            prob_full_charge = min(98.0, round(85.0 + (surplus_for_battery - energy_needed_for_full_battery) * 2.0, 1))
            projected_sunset_soc = 100.0
        elif energy_needed_for_full_battery > 0:
            fraction = surplus_for_battery / energy_needed_for_full_battery
            prob_full_charge = max(0.0, min(95.0, round(fraction * 80.0, 1)))
            added_soc = (surplus_for_battery / battery_capacity_kwh) * 100.0
            projected_sunset_soc = min(100.0, round(current_soc + added_soc, 1))
        else:
            prob_full_charge = 0.0
            projected_sunset_soc = round(current_soc, 1)
    else:
        prob_full_charge = 0.0
        projected_sunset_soc = 0.0

    night_load_kwh = daily_consumption_kwh * 0.45 if daily_consumption_kwh > 0 else 0.0
    avg_night_power_kw = night_load_kwh / 12.0 if night_load_kwh > 0 else 0.0
    if battery_capacity_kwh > 0 and avg_night_power_kw > 0:
        usable_at_sunset = max(0.0, ((projected_sunset_soc - reserve_soc) / 100.0) * battery_capacity_kwh)
        night_autonomy_hours = min(24.0, round(usable_at_sunset / avg_night_power_kw, 1))
        whole_h = int(night_autonomy_hours)
        mins = int(round((night_autonomy_hours - whole_h) * 60))
        autonomy_formatted = f"{whole_h}h {mins}m"
    else:
        night_autonomy_hours = 0.0
        autonomy_formatted = "--"

    hourly_forecast = []
    for idx in tomorrow_hours:
        if idx < len(times):
            t_str = times[idx]
            h = int(t_str[11:13])
            rad = float(radiations[idx]) if idx < len(radiations) and radiations[idx] is not None else 0.0
            cld = float(cloud_covers[idx]) if idx < len(cloud_covers) and cloud_covers[idx] is not None else 0.0
            tmp = float(temperatures[idx]) if idx < len(temperatures) and temperatures[idx] is not None else 0.0
            est_pv = round((rad / 1000.0) * installed_kwp * 0.80 * (1.0 - (cld / 100.0) * 0.35), 2) if installed_kwp > 0 else 0.0
            hourly_forecast.append({
                "time": t_str,
                "hour": h,
                "solar_radiation_wm2": round(rad, 1),
                "cloud_cover_percent": round(cld, 1),
                "temperature_c": round(tmp, 1),
                "estimated_pv_power_kw": max(0.0, est_pv)
            })

    return {
        "configured": True,
        "status": "ok",
        "location": loc_label or f"{lat:.4f}, {lon:.4f}",
        "latitude": lat,
        "longitude": lon,
        "timezone": tz_clean,
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
