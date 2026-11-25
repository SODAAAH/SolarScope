import json
import datetime
import urllib.request
import urllib.error
import urllib.parse
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional, Tuple
from backend.app.storage.db import get_connection

def _get_station_now(tz_name: str) -> datetime.datetime:
    try:
        return datetime.datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def _describe_wmo_weather(weather_code: Optional[int], cloud_cover: float, is_day: int = 1) -> Tuple[str, str]:
    code = int(weather_code) if weather_code is not None else -1
    if code in (95, 96, 99):
        return "Thunderstorm", "cloud-lightning"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "Rain" if code in (61, 80) else "Heavy Rain", "cloud-rain"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle", "cloud-drizzle"
    if code in (71, 73, 75, 77, 85, 86):
        return "Snow", "cloud"
    if code in (45, 48):
        return "Foggy", "cloud-fog"
    if code == 3 or cloud_cover >= 80.0:
        return "Overcast", "cloud"
    if code == 2 or cloud_cover >= 45.0:
        return "Mostly Cloudy", "cloud"
    if code == 1 or cloud_cover >= 15.0:
        return "Partly Cloudy", "cloud-sun" if is_day else "cloud"
    return "Clear Sky", "sun" if is_day else "moon"

def get_weather_intelligence(
    lat: float = 0.0,
    lon: float = 0.0,
    location_name: str = "",
    timezone_str: str = "Asia/Manila",
    installed_kwp: float = 0.0,
    battery_capacity_kwh: float = 0.0,
    reserve_soc: float = 20.0,
    current_soc: float = 0.0,
    daily_consumption_kwh: float = 0.0,
    force_refresh: bool = False
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
            "hourly_forecast": [],
            "live_hourly_forecast": []
        }

    station_now = _get_station_now(tz_clean)
    today_dt = station_now.date()
    today_str = today_dt.strftime("%Y-%m-%d")
    tomorrow_str = (today_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    current_hour_prefix = station_now.strftime("%Y-%m-%dT%H")

    weather_data = None
    fetched_at_iso = None
    if not force_refresh:
        conn = get_connection()
        cached = conn.execute(
            """SELECT * FROM weather_cache
               WHERE date_str = ? AND ABS(latitude - ?) < 0.001 AND ABS(longitude - ?) < 0.001
               ORDER BY fetched_at DESC LIMIT 1""",
            (today_str, lat, lon)
        ).fetchone()
        conn.close()

        if cached:
            try:
                fetched_dt = datetime.datetime.fromisoformat(cached["fetched_at"])
                if fetched_dt.tzinfo is None:
                    fetched_dt = fetched_dt.replace(tzinfo=datetime.timezone.utc)
                age_sec = (datetime.datetime.now(datetime.timezone.utc) - fetched_dt).total_seconds()
                if age_sec <= 1800:
                    parsed = json.loads(cached["hourly_data_json"])
                    if isinstance(parsed, dict) and "current" in parsed and "weather_code" in (parsed.get("hourly") or {}):
                        weather_data = parsed
                        fetched_at_iso = cached["fetched_at"]
            except Exception:
                weather_data = None

    if not weather_data:
        try:
            tz_param = urllib.parse.quote(tz_clean, safe="")
            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,cloud_cover,precipitation,weather_code,wind_speed_10m,is_day,shortwave_radiation"
                f"&hourly=shortwave_radiation,direct_normal_irradiance,diffuse_radiation,cloud_cover,temperature_2m,precipitation,weather_code,wind_speed_10m"
                f"&forecast_days=2&timezone={tz_param}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "SolarScope/1.0"})
            with urllib.request.urlopen(req, timeout=6) as response:
                weather_data = json.loads(response.read().decode("utf-8"))
                fetched_at_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cache_id = f"weather-{lat:.4f}:{lon:.4f}:{today_str}"
                c_conn = get_connection()
                c_conn.execute(
                    """INSERT OR REPLACE INTO weather_cache (id, latitude, longitude, date_str, hourly_data_json, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (cache_id, lat, lon, today_str, json.dumps(weather_data), fetched_at_iso)
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
            "hourly_forecast": [],
            "live_hourly_forecast": []
        }

    hourly = weather_data.get("hourly", {})
    times = hourly.get("time", [])
    radiations = hourly.get("shortwave_radiation", [])
    cloud_covers = hourly.get("cloud_cover", [])
    temperatures = hourly.get("temperature_2m", [])
    precipitations = hourly.get("precipitation", [])
    weather_codes = hourly.get("weather_code", [])
    wind_speeds = hourly.get("wind_speed_10m", [])

    tomorrow_hours = [i for i, t in enumerate(times) if t.startswith(tomorrow_str)]

    current_hour_idx = next((i for i, t in enumerate(times) if t.startswith(current_hour_prefix)), station_now.hour)
    if current_hour_idx >= len(times):
        current_hour_idx = max(0, len(times) - 1)

    current_block = weather_data.get("current") or {}
    current_cloud = float(
        current_block.get("cloud_cover")
        if current_block.get("cloud_cover") is not None
        else (cloud_covers[current_hour_idx] if current_hour_idx < len(cloud_covers) and cloud_covers[current_hour_idx] is not None else 0.0)
    )
    current_radiation = float(
        current_block.get("shortwave_radiation")
        if current_block.get("shortwave_radiation") is not None
        else (radiations[current_hour_idx] if current_hour_idx < len(radiations) and radiations[current_hour_idx] is not None else 0.0)
    )
    current_temp = float(
        current_block.get("temperature_2m")
        if current_block.get("temperature_2m") is not None
        else (temperatures[current_hour_idx] if current_hour_idx < len(temperatures) and temperatures[current_hour_idx] is not None else 0.0)
    )
    current_precip = float(
        current_block.get("precipitation")
        if current_block.get("precipitation") is not None
        else (precipitations[current_hour_idx] if current_hour_idx < len(precipitations) and precipitations[current_hour_idx] is not None else 0.0)
    )
    current_wind = float(
        current_block.get("wind_speed_10m")
        if current_block.get("wind_speed_10m") is not None
        else (wind_speeds[current_hour_idx] if current_hour_idx < len(wind_speeds) and wind_speeds[current_hour_idx] is not None else 0.0)
    )
    current_wmo = (
        current_block.get("weather_code")
        if current_block.get("weather_code") is not None
        else (weather_codes[current_hour_idx] if current_hour_idx < len(weather_codes) else None)
    )
    is_day_val = int(current_block.get("is_day") if current_block.get("is_day") is not None else (1 if 6 <= station_now.hour < 18 else 0))
    condition_label, icon_key = _describe_wmo_weather(current_wmo, current_cloud, is_day_val)

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

    def _build_hour_item(idx: int, is_now_flag: bool = False) -> Dict[str, Any]:
        t_str = times[idx]
        h = int(t_str[11:13])
        d_str = t_str[:10]
        rad = float(radiations[idx]) if idx < len(radiations) and radiations[idx] is not None else 0.0
        cld = float(cloud_covers[idx]) if idx < len(cloud_covers) and cloud_covers[idx] is not None else 0.0
        tmp = float(temperatures[idx]) if idx < len(temperatures) and temperatures[idx] is not None else 0.0
        prc = float(precipitations[idx]) if idx < len(precipitations) and precipitations[idx] is not None else 0.0
        wmo = weather_codes[idx] if idx < len(weather_codes) else None
        is_day_h = 1 if 6 <= h < 18 else 0
        cond_lbl, ic_key = _describe_wmo_weather(wmo, cld, is_day_h)
        est_pv = round((rad / 1000.0) * installed_kwp * 0.80 * (1.0 - (cld / 100.0) * 0.35), 2) if installed_kwp > 0 else 0.0
        return {
            "time": t_str,
            "date": d_str,
            "hour": h,
            "is_today": d_str == today_str,
            "is_now": is_now_flag,
            "solar_radiation_wm2": round(rad, 1),
            "cloud_cover_percent": round(cld, 1),
            "temperature_c": round(tmp, 1),
            "precipitation_mm": round(prc, 2),
            "weather_code": int(wmo) if wmo is not None else None,
            "condition_label": cond_lbl,
            "icon_key": ic_key,
            "estimated_pv_power_kw": max(0.0, est_pv)
        }

    hourly_forecast = [_build_hour_item(idx) for idx in tomorrow_hours if idx < len(times)]
    live_slice_end = min(len(times), current_hour_idx + 12)
    live_hourly_forecast = [
        _build_hour_item(idx, is_now_flag=(idx == current_hour_idx))
        for idx in range(current_hour_idx, live_slice_end)
    ]

    return {
        "configured": True,
        "status": "ok",
        "location": loc_label or f"{lat:.4f}, {lon:.4f}",
        "latitude": lat,
        "longitude": lon,
        "timezone": tz_clean,
        "fetched_at": fetched_at_iso,
        "current_conditions": {
            "cloud_cover_percent": round(current_cloud, 1),
            "solar_radiation_wm2": round(current_radiation, 1),
            "temperature_c": round(current_temp, 1),
            "precipitation_mm": round(current_precip, 2),
            "wind_speed_kmh": round(current_wind, 1),
            "weather_code": int(current_wmo) if current_wmo is not None else None,
            "condition_label": condition_label,
            "icon_key": icon_key,
            "is_day": bool(is_day_val),
            "observed_at": current_block.get("time") or station_now.strftime("%Y-%m-%dT%H:00")
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
        "hourly_forecast": hourly_forecast,
        "live_hourly_forecast": live_hourly_forecast
    }
