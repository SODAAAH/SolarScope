import os
import json
import urllib.request
import urllib.parse
import urllib.error
import hashlib
import time
import datetime
from typing import Dict, Any, List, Optional
from backend.app.storage.db import get_connection
from backend.app.storage.blob_sync import ensure_hydrated

MANILA_TZ = datetime.timezone(datetime.timedelta(hours=8))

ALLOWED_READ_TOOLS = {
    "get_station_latest",
    "station_history",
    "station_history_power",
    "get_device_latest",
    "device_history",
    "device_alert_list",
    "station_alert_list"
}

class DeyeMCPClient:
    def __init__(self, project_id: str = "default"):
        self.project_id = project_id
        self.base_url = "https://eu1-developer.deyecloud.com"
        self.mcp_endpoint = "https://developer.deyecloud.com/openmcp/mcp"
        self._cached_token = None
        self._token_expiry = None
        self._last_auth_error: Optional[str] = None
        self._cached_live_flows: Dict[str, Dict[str, Any]] = {}
        self._cached_live_flow_times: Dict[str, float] = {}
        self._last_real_flows: Dict[str, Dict[str, Any]] = {}

    def invalidate_cache(self, clear_last_real: bool = False) -> None:
        self._cached_token = None
        self._token_expiry = None
        self._last_auth_error = None
        self._cached_live_flows.clear()
        self._cached_live_flow_times.clear()
        if clear_last_real:
            self._last_real_flows.clear()

    def _cred_signature(self, creds: Dict[str, str]) -> str:
        raw = f"{creds.get('station_id', '')}:{creds.get('app_id', '')}:{creds.get('app_secret', '')}:{creds.get('username', '')}:{creds.get('password', '')}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    def _save_db_last_flow(self, cache_key: str, flow_res: Dict[str, Any]) -> None:
        try:
            clean = dict(flow_res)
            clean.pop("access_token", None)
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn = get_connection()
            conn.execute(
                """INSERT OR REPLACE INTO deye_live_cache (cache_key, payload_json, updated_at)
                   VALUES (?, ?, ?)""",
                (cache_key, json.dumps(clean), now_iso)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _load_db_last_flow(self, cache_key: str) -> Optional[Dict[str, Any]]:
        try:
            conn = get_connection()
            row = conn.execute(
                "SELECT payload_json FROM deye_live_cache WHERE cache_key = ?",
                (cache_key,)
            ).fetchone()
            conn.close()
            if row and row["payload_json"]:
                parsed = json.loads(row["payload_json"])
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass
        return None

    def _get_credentials(self) -> Dict[str, str]:
        ensure_hydrated(force=False)
        conn = get_connection()
        cfg = conn.execute("SELECT * FROM deye_cloud_configs WHERE project_id = ?", (self.project_id,)).fetchone()
        sys_row = conn.execute("SELECT * FROM system_settings WHERE project_id = ?", (self.project_id,)).fetchone()
        conn.close()

        station_id = ((cfg["station_id"] or "").strip() if cfg else "") or os.environ.get("DEYE_STATION_ID", "").strip()
        app_id = ((cfg["app_id"] or "").strip() if cfg else "") or os.environ.get("DEYE_APP_ID", "").strip()
        app_secret = ((cfg["app_secret"] or "").strip() if cfg else "") or os.environ.get("DEYE_APP_SECRET", "").strip()
        username = ((cfg["username"] or "").strip() if cfg else "") or os.environ.get("DEYE_USERNAME", "").strip()
        password = ((cfg["password_encrypted"] or "").strip() if cfg else "") or os.environ.get("DEYE_PASSWORD", "").strip()

        inverter_sn = (sys_row["inverter_serial"] or "").strip() if sys_row else ""
        logger_sn = (sys_row["logger_serial"] or "").strip() if sys_row else ""

        return {
            "station_id": station_id,
            "app_id": app_id,
            "app_secret": app_secret,
            "username": username,
            "password": password,
            "inverter_sn": inverter_sn,
            "logger_sn": logger_sn
        }

    def _get_system_meta(self) -> Dict[str, Any]:
        conn = get_connection()
        row = conn.execute("SELECT * FROM system_settings WHERE project_id = ?", (self.project_id,)).fetchone()
        conn.close()
        if not row:
            return {
                "station_name": "",
                "inverter_model": "",
                "inverter_power_kw": 0.0,
                "battery_model": "",
                "reserve_soc": 20.0,
                "logger_interval_min": 5,
                "latitude": 0.0,
                "longitude": 0.0,
                "timezone": "Asia/Manila",
            }
        keys = row.keys()
        return {
            "station_name": (row["station_name"] or "").strip() if "station_name" in keys else "",
            "inverter_model": (row["inverter_model"] or "").strip() if "inverter_model" in keys else "",
            "inverter_power_kw": float(row["inverter_power_kw"] or 0.0) if "inverter_power_kw" in keys else 0.0,
            "battery_model": (row["battery_model"] or "").strip() if "battery_model" in keys else "",
            "reserve_soc": float(row["reserve_soc"] if row["reserve_soc"] is not None else 20.0) if "reserve_soc" in keys else 20.0,
            "logger_interval_min": int(row["logger_interval_min"] or 5) if "logger_interval_min" in keys else 5,
            "latitude": float(row["latitude"] or 0.0) if "latitude" in keys else 0.0,
            "longitude": float(row["longitude"] or 0.0) if "longitude" in keys else 0.0,
            "timezone": (row["timezone"] or "Asia/Manila").strip() if "timezone" in keys else "Asia/Manila",
        }

    def _has_server_credentials(self, creds: Dict[str, str]) -> bool:
        if creds["app_id"] == "demo" or creds["username"] == "demo":
            return False
        return bool(creds["app_id"] and creds["app_secret"] and creds["username"] and creds["password"])

    def get_auth_token(self, force_refresh: bool = False) -> Optional[str]:
        now = datetime.datetime.now(datetime.timezone.utc)
        if not force_refresh and self._cached_token and self._token_expiry and now < self._token_expiry:
            return self._cached_token

        if force_refresh:
            self._cached_token = None
            self._token_expiry = None

        creds = self._get_credentials()
        if creds["app_id"] == "demo" or creds["username"] == "demo":
            self._last_auth_error = None
            return None

        if not self._has_server_credentials(creds):
            self._last_auth_error = "Deye Cloud credentials not configured."
            return None

        pwd_hash = hashlib.sha256(creds["password"].encode("utf-8")).hexdigest().lower()
        auth_body: Dict[str, Any] = {
            "appSecret": creds["app_secret"],
            "password": pwd_hash
        }
        if "@" in creds["username"]:
            auth_body["email"] = creds["username"]
        else:
            auth_body["username"] = creds["username"]
        payload = json.dumps(auth_body).encode("utf-8")

        token_url = f"{self.base_url}/v1.0/account/token?appId={urllib.parse.quote(creds['app_id'])}"
        for attempt in range(2):
            try:
                req = urllib.request.Request(token_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("success") and "accessToken" in data:
                        self._cached_token = data["accessToken"]
                        expires_sec = data.get("expiresIn")
                        try:
                            ttl = max(300, int(expires_sec)) - 60 if expires_sec else 86400
                        except Exception:
                            ttl = 86400
                        self._token_expiry = now + datetime.timedelta(seconds=ttl)
                        self._last_auth_error = None
                        return self._cached_token
                    self._last_auth_error = data.get("msg") or "Deye authentication rejected"
                    break
            except urllib.error.HTTPError as he:
                try:
                    err_data = json.loads(he.read().decode("utf-8"))
                    self._last_auth_error = err_data.get("msg") or f"HTTP {he.code}: {he.reason}"
                except Exception:
                    self._last_auth_error = f"HTTP {he.code}: {he.reason}"
                if he.code in (500, 502, 503, 504) and attempt == 0:
                    time.sleep(0.3)
                    continue
                break
            except Exception as e:
                self._last_auth_error = str(e)
                if attempt == 0:
                    time.sleep(0.3)
                    continue
        return None

    def execute_read_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in ALLOWED_READ_TOOLS:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is not in the verified read-only allowlist. Write and control operations are strictly prohibited."
            }

        creds = self._get_credentials()
        station_id = arguments.get("station_id") or creds["station_id"]

        if tool_name == "get_station_latest":
            res = self.get_station_latest(station_id)
            res.pop("token_used", None)
            res.pop("token_expired", None)
            return res
        elif tool_name == "station_history":
            start_at = arguments.get("start_at", datetime.datetime.now(MANILA_TZ).strftime("%Y-%m-%d"))
            end_at = arguments.get("end_at", start_at)
            granularity = arguments.get("granularity", 2)
            return self.get_station_history(station_id, start_at, end_at, granularity)
        elif tool_name == "station_history_power":
            start_ts = arguments.get("start_timestamp", int((datetime.datetime.now(MANILA_TZ) - datetime.timedelta(days=1)).timestamp()))
            end_ts = arguments.get("end_timestamp", int(datetime.datetime.now(MANILA_TZ).timestamp()))
            return self.get_station_history_power(station_id, start_ts, end_ts)
        elif tool_name == "get_device_latest":
            device_sn = arguments.get("device_sn") or creds["inverter_sn"]
            return self.get_device_latest(device_sn)
        elif tool_name == "device_history":
            device_sn = arguments.get("device_sn") or creds["inverter_sn"]
            start_at = arguments.get("start_at", datetime.datetime.now(MANILA_TZ).strftime("%Y-%m-%d"))
            end_at = arguments.get("end_at", start_at)
            granularity = arguments.get("granularity", 2)
            return self.get_device_history(device_sn, start_at, end_at, granularity)
        elif tool_name == "device_alert_list":
            device_sn = arguments.get("device_sn") or creds["inverter_sn"]
            start_ts = arguments.get("start_timestamp", int((datetime.datetime.now(MANILA_TZ) - datetime.timedelta(days=7)).timestamp()))
            end_ts = arguments.get("end_timestamp", int(datetime.datetime.now(MANILA_TZ).timestamp()))
            return self.get_device_alerts(device_sn, start_ts, end_ts)
        elif tool_name == "station_alert_list":
            start_ts = arguments.get("start_timestamp", int((datetime.datetime.now(MANILA_TZ) - datetime.timedelta(days=7)).timestamp()))
            end_ts = arguments.get("end_timestamp", int(datetime.datetime.now(MANILA_TZ).timestamp()))
            return self.get_station_alerts(station_id, start_ts, end_ts)

        return {"success": False, "error": "Unhandled tool execution"}

    def _is_auth_failure(self, status_code: Optional[int], data: Optional[Dict[str, Any]]) -> bool:
        if status_code in (401, 403):
            return True
        if not data:
            return False
        code_str = str(data.get("code") or "")
        msg_str = str(data.get("msg") or "").lower()
        return code_str in {"2101001", "2101002", "2101003", "2101014", "1001"} or any(
            k in msg_str for k in ("token", "unauthorized", "auth", "expire")
        )

    def get_station_latest(self, station_id: str, access_token_override: Optional[str] = None) -> Dict[str, Any]:
        override_clean = (access_token_override or "").strip() or None
        token = override_clean or self.get_auth_token()
        if not token:
            return {
                "success": False,
                "error": self._last_auth_error or "Deye Cloud authentication unavailable",
                "token_used": None
            }

        creds = self._get_credentials()
        has_server_creds = self._has_server_credentials(creds)
        if not str(station_id).isdigit():
            return {"success": False, "error": "Station ID is required."}
        st_id = int(station_id)
        url = f"{self.base_url}/v1.0/station/latest"
        payload = json.dumps({"stationId": st_id}).encode("utf-8")

        for attempt in range(2):
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("success") is False:
                        if attempt == 0 and has_server_creds and self._is_auth_failure(None, data):
                            refreshed = self.get_auth_token(force_refresh=True)
                            if refreshed:
                                token = refreshed
                                continue
                        return {
                            "success": False,
                            "error": data.get("msg", "Unknown error"),
                            "token_expired": self._is_auth_failure(None, data) and not has_server_creds,
                            "raw": data
                        }

                    pv_w = data.get("generationPower")
                    load_w = data.get("consumptionPower")
                    grid_w = data.get("wirePower")
                    if grid_w is None:
                        grid_w = data.get("purchasePower")
                    if grid_w is None and data.get("gridPower") is not None:
                        grid_w = -abs(float(data.get("gridPower")))

                    if data.get("chargePower") is not None and float(data.get("chargePower")) > 0:
                        batt_w = -abs(float(data.get("chargePower")))
                    elif data.get("dischargePower") is not None and float(data.get("dischargePower")) > 0:
                        batt_w = abs(float(data.get("dischargePower")))
                    else:
                        batt_w = data.get("batteryPower")

                    soc = data.get("batterySOC")

                    return {
                        "success": True,
                        "station_id": str(st_id),
                        "connection_status": data.get("connectionStatus", "NORMAL"),
                        "last_update_time": data.get("lastUpdateTime"),
                        "measurements": {
                            "pv_power_kw": round(float(pv_w) / 1000.0, 3) if pv_w is not None else None,
                            "household_load_kw": round(float(load_w) / 1000.0, 3) if load_w is not None else None,
                            "grid_power_kw": round(float(grid_w) / 1000.0, 3) if grid_w is not None else None,
                            "battery_power_kw": round(float(batt_w) / 1000.0, 3) if batt_w is not None else None,
                            "battery_charge_level_percent": float(soc) if soc is not None else None
                        },
                        "missing_fields": [k for k, v in [("pv", pv_w), ("load", load_w), ("grid", grid_w), ("battery", batt_w), ("soc", soc)] if v is None],
                        "raw": data,
                        "token_used": token
                    }
            except urllib.error.HTTPError as he:
                err_data = None
                try:
                    err_data = json.loads(he.read().decode("utf-8"))
                except Exception:
                    err_data = None
                if attempt == 0 and has_server_creds and self._is_auth_failure(he.code, err_data):
                    refreshed = self.get_auth_token(force_refresh=True)
                    if refreshed:
                        token = refreshed
                        continue
                if attempt == 0 and he.code in (500, 502, 503, 504):
                    time.sleep(0.3)
                    continue
                err_msg = (err_data.get("msg") if err_data else None) or f"HTTP {he.code}: {he.reason}"
                return {
                    "success": False,
                    "error": err_msg,
                    "token_expired": self._is_auth_failure(he.code, err_data) and not has_server_creds
                }
            except Exception as e:
                if attempt == 0:
                    time.sleep(0.3)
                    continue
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "Deye station query failed"}

    def get_station_history(self, station_id: str, start_at: str, end_at: str, granularity: int = 2) -> Dict[str, Any]:
        token = self.get_auth_token()
        if not token:
            return {"success": False, "error": "Deye Cloud authentication unavailable"}

        if not str(station_id).isdigit():
            return {"success": False, "error": "Station ID is required."}
        st_id = int(station_id)
        url = f"{self.base_url}/v1.0/station/history"
        payload = json.dumps({
            "stationId": st_id,
            "startAt": start_at,
            "endAt": end_at,
            "granularity": granularity
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("stationDataItems", [])
                normalized_items = []
                for it in items:
                    normalized_items.append({
                        "date": f"{it.get('year', '')}-{str(it.get('month', '')).zfill(2)}-{str(it.get('day', '')).zfill(2)}",
                        "solar_produced_kwh": it.get("generationValue", 0.0),
                        "household_consumed_kwh": it.get("consumptionValue", 0.0),
                        "tei_purchased_kwh": it.get("purchaseValue", 0.0),
                        "grid_exported_kwh": it.get("gridValue", 0.0),
                        "battery_charged_kwh": it.get("chargeValue", 0.0),
                        "battery_discharged_kwh": it.get("dischargeValue", 0.0),
                        "full_power_hours": it.get("fullPowerHours", 0.0)
                    })
                return {
                    "success": data.get("success", True),
                    "items": normalized_items,
                    "total_count": len(normalized_items),
                    "raw": data
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_station_history_power(self, station_id: str, start_timestamp: int, end_timestamp: int) -> Dict[str, Any]:
        token = self.get_auth_token()
        if not token:
            return {"success": False, "error": "Deye Cloud authentication unavailable"}

        if not str(station_id).isdigit():
            return {"success": False, "error": "Station ID is required."}
        st_id = int(station_id)
        url = f"{self.base_url}/v1.0/station/history/power"
        payload = json.dumps({
            "stationId": st_id,
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_items = data.get("stationDataItems", [])
                readings = []
                for r in raw_items:
                    sec = r.get("timeStamp")
                    if not sec:
                        continue
                    dt = datetime.datetime.fromtimestamp(sec, tz=MANILA_TZ)
                    readings.append({
                        "timestamp_iso": dt.isoformat(),
                        "time_str": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "solar_power_kw": round((r.get("generationPower") or 0.0) / 1000.0, 3),
                        "household_load_kw": round((r.get("consumptionPower") or 0.0) / 1000.0, 3),
                        "tei_purchase_kw": round((r.get("purchasePower") or r.get("wirePower") or 0.0) / 1000.0, 3),
                        "battery_power_kw": round((r.get("batteryPower") or 0.0) / 1000.0, 3),
                        "battery_charge_level_percent": float(r.get("batterySOC") or 0.0)
                    })
                return {
                    "success": True,
                    "readings": readings,
                    "readings_count": len(readings)
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_device_latest(self, device_sn: str, access_token_override: Optional[str] = None) -> Dict[str, Any]:
        if not (device_sn or "").strip():
            return {"success": False, "error": "Device serial is required."}
        token = (access_token_override or "").strip() or self.get_auth_token()
        if not token:
            return {"success": False, "error": "Deye Cloud authentication unavailable"}

        url = f"{self.base_url}/v1.0/device/latest"
        payload = json.dumps({"deviceList": [device_sn]}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"success": True, "device_data": data.get("deviceDataList", []), "raw": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_device_history(self, device_sn: str, start_at: str, end_at: str, granularity: int = 2) -> Dict[str, Any]:
        if not (device_sn or "").strip():
            return {"success": False, "error": "Device serial is required."}
        token = self.get_auth_token()
        if not token:
            return {"success": False, "error": "Deye Cloud authentication unavailable"}

        url = f"{self.base_url}/v1.0/device/history"
        payload = json.dumps({
            "deviceSn": device_sn,
            "startAt": start_at,
            "endAt": end_at,
            "granularity": granularity
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"success": True, "history": data.get("dataList", []), "raw": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_device_alerts(self, device_sn: str, start_timestamp: int, end_timestamp: int, access_token_override: Optional[str] = None) -> Dict[str, Any]:
        if not (device_sn or "").strip():
            return {"success": False, "error": "Device serial is required.", "alerts": []}
        token = (access_token_override or "").strip() or self.get_auth_token()
        if not token:
            return {"success": False, "error": "Deye Cloud authentication unavailable", "alerts": []}

        url = f"{self.base_url}/v1.0/device/alertList"
        payload = json.dumps({
            "deviceSn": device_sn,
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "page": 1,
            "size": 50
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                alerts = data.get("alertList", [])
                return {
                    "success": True,
                    "alerts": alerts,
                    "alert_count": len(alerts),
                    "device_sn": device_sn
                }
        except Exception as e:
            return {"success": False, "error": str(e), "alerts": []}

    def get_station_alerts(self, station_id: str, start_timestamp: int, end_timestamp: int, access_token_override: Optional[str] = None) -> Dict[str, Any]:
        token = (access_token_override or "").strip() or self.get_auth_token()
        if not token:
            return {"success": False, "error": "Deye Cloud authentication unavailable", "alerts": []}

        if not str(station_id).isdigit():
            return {"success": False, "error": "Station ID is required.", "alerts": []}
        st_id = int(station_id)
        url = f"{self.base_url}/v1.0/station/alertList"
        payload = json.dumps({
            "stationId": st_id,
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "page": 1,
            "size": 50
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                alerts = data.get("alertList", [])
                return {
                    "success": True,
                    "alerts": alerts,
                    "alert_count": len(alerts),
                    "station_id": str(st_id)
                }
        except Exception as e:
            return {"success": False, "error": str(e), "alerts": []}

    def _parse_last_update_time(self, raw_ts: Any) -> str:
        fallback = datetime.datetime.now(MANILA_TZ).strftime("%Y-%m-%d %H:%M:%S")
        if raw_ts is None or raw_ts == "":
            return fallback
        try:
            val = float(raw_ts)
            if val > 1e12:
                val = val / 1000.0
            if val > 1e8:
                return datetime.datetime.fromtimestamp(val, tz=MANILA_TZ).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
        if isinstance(raw_ts, str):
            try:
                dt = datetime.datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=MANILA_TZ)
                else:
                    dt = dt.astimezone(MANILA_TZ)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        return fallback

    def _get_live_weather_temp_c(self) -> Optional[float]:
        meta = self._get_system_meta()
        lat = meta["latitude"]
        lon = meta["longitude"]
        if lat == 0.0 and lon == 0.0:
            return None
        try:
            today_str = datetime.datetime.now(MANILA_TZ).strftime("%Y-%m-%d")
            conn = get_connection()
            cached = conn.execute(
                """SELECT hourly_data_json FROM weather_cache
                   WHERE date_str = ? AND ABS(latitude - ?) < 0.001 AND ABS(longitude - ?) < 0.001
                   ORDER BY fetched_at DESC LIMIT 1""",
                (today_str, lat, lon)
            ).fetchone()
            conn.close()
            if cached and cached["hourly_data_json"]:
                w_data = json.loads(cached["hourly_data_json"])
                temps = w_data.get("hourly", {}).get("temperature_2m", [])
                hour_idx = datetime.datetime.now(MANILA_TZ).hour
                if hour_idx < len(temps) and temps[hour_idx] is not None:
                    return round(float(temps[hour_idx]), 1)
        except Exception:
            pass
        return None

    def _get_dataset_summary_metrics(self) -> Dict[str, Any]:
        from backend.app.api.endpoints import get_historical_daily
        try:
            sums = get_historical_daily("historical")
        except Exception:
            sums = []
        weather_temp_c = self._get_live_weather_temp_c()
        if not sums:
            return {
                "summary": {
                    "accumulative_production_kwh": 0.0,
                    "accumulative_consumption_kwh": 0.0,
                    "daily_production_kwh": 0.0,
                    "weather_temp_c": weather_temp_c
                },
                "utilization": {
                    "consumption_total_kwh": 0.0,
                    "consumption_breakdown": [
                        {"label": "Import", "kwh": 0.0, "pct": 0.0, "color": "#0284C7"},
                        {"label": "Discharge", "kwh": 0.0, "pct": 0.0, "color": "#06B6D4"},
                        {"label": "PV", "kwh": 0.0, "pct": 0.0, "color": "#10B981"}
                    ],
                    "production_total_kwh": 0.0,
                    "production_breakdown": [
                        {"label": "Charge", "kwh": 0.0, "pct": 0.0, "color": "#F59E0B"},
                        {"label": "Consumption", "kwh": 0.0, "pct": 0.0, "color": "#EAB308"}
                    ]
                }
            }

        tot_pv = sum(d.get("pv_kwh", 0.0) for d in sums)
        tot_load = sum(d.get("load_kwh", 0.0) for d in sums)
        tot_import = sum(d.get("grid_import_kwh", 0.0) for d in sums)
        tot_discharge = sum(d.get("battery_discharge_kwh", 0.0) for d in sums)
        tot_charge = sum(d.get("battery_charge_kwh", 0.0) for d in sums)
        tot_pv_self = round(max(0.0, tot_load - tot_import - tot_discharge), 2)
        today_pv = sums[-1].get("pv_kwh", 0.0)

        cons_denom = max(0.01, tot_import + tot_discharge + tot_pv_self) if tot_load > 0 else 1.0
        prod_denom = max(0.01, tot_charge + tot_pv_self) if tot_pv > 0 else 1.0

        return {
            "summary": {
                "accumulative_production_kwh": round(tot_pv, 2),
                "accumulative_consumption_kwh": round(tot_load, 2),
                "daily_production_kwh": round(today_pv, 2),
                "weather_temp_c": weather_temp_c
            },
            "utilization": {
                "consumption_total_kwh": round(tot_load, 2),
                "consumption_breakdown": [
                    {"label": "Import", "kwh": round(tot_import, 2), "pct": round(tot_import / cons_denom * 100.0, 1) if tot_load > 0 else 0.0, "color": "#0284C7"},
                    {"label": "Discharge", "kwh": round(tot_discharge, 2), "pct": round(tot_discharge / cons_denom * 100.0, 1) if tot_load > 0 else 0.0, "color": "#06B6D4"},
                    {"label": "PV", "kwh": round(tot_pv_self, 2), "pct": round(tot_pv_self / cons_denom * 100.0, 1) if tot_load > 0 else 0.0, "color": "#10B981"}
                ],
                "production_total_kwh": round(tot_pv, 2),
                "production_breakdown": [
                    {"label": "Charge", "kwh": round(tot_charge, 2), "pct": round(tot_charge / prod_denom * 100.0, 1) if tot_pv > 0 else 0.0, "color": "#F59E0B"},
                    {"label": "Consumption", "kwh": round(tot_pv_self, 2), "pct": round(tot_pv_self / prod_denom * 100.0, 1) if tot_pv > 0 else 0.0, "color": "#EAB308"}
                ]
            }
        }

    def get_station_health(self, access_token_override: Optional[str] = None, station_id_override: Optional[str] = None, mode_override: Optional[str] = None) -> Dict[str, Any]:
        creds = self._get_credentials()
        meta = self._get_system_meta()
        station_id = (station_id_override or "").strip() or creds["station_id"]
        is_demo = (mode_override == "demo") or (not access_token_override and (creds["app_id"] == "demo" or creds["username"] == "demo"))
        has_server_creds = self._has_server_credentials(creds)
        reserve_threshold = meta["reserve_soc"]

        if is_demo:
            pv_kw = 2.45
            load_kw = 0.85
            batt_kw = -1.60
            grid_kw = 0.0
            soc = 78.0
            conn_status = "NORMAL"
            alerts = []
            is_healthy = True
        elif not access_token_override and not has_server_creds:
            pv_kw = 0.0
            load_kw = 0.0
            batt_kw = 0.0
            grid_kw = 0.0
            soc = 0.0
            conn_status = "OFFLINE"
            alerts = []
            is_healthy = False
        else:
            latest_res = self.get_station_latest(station_id, access_token_override=access_token_override)
            token_for_alerts = latest_res.get("token_used") or access_token_override
            now_sec = int(datetime.datetime.now(MANILA_TZ).timestamp())
            day_ago_sec = now_sec - 86400
            if creds["inverter_sn"]:
                alert_res = self.get_device_alerts(creds["inverter_sn"], day_ago_sec, now_sec, access_token_override=token_for_alerts)
            elif str(station_id).isdigit():
                alert_res = self.get_station_alerts(station_id, day_ago_sec, now_sec, access_token_override=token_for_alerts)
            else:
                alert_res = {"alerts": []}

            if latest_res.get("success"):
                m = latest_res.get("measurements", {})
                pv_kw = m.get("pv_power_kw") or 0.0
                load_kw = m.get("household_load_kw") or 0.0
                batt_kw = m.get("battery_power_kw") or 0.0
                grid_kw = m.get("grid_power_kw") or 0.0
                soc = m.get("battery_charge_level_percent") if m.get("battery_charge_level_percent") is not None else 0.0
                conn_status = latest_res.get("connection_status", "NORMAL")
                alerts = alert_res.get("alerts", [])
                is_healthy = conn_status == "NORMAL" and soc >= reserve_threshold and len(alerts) == 0
            else:
                pv_kw = 0.0
                load_kw = 0.0
                batt_kw = 0.0
                grid_kw = 0.0
                soc = 0.0
                conn_status = "OFFLINE"
                alerts = []
                is_healthy = False

        if conn_status == "OFFLINE":
            status_badge = "Offline"
            rec = "Live Deye Cloud telemetry is not connected. Configure Deye Cloud credentials in Data Library & Cloud."
        elif soc <= reserve_threshold:
            status_badge = "Healthy" if is_healthy else "Attention Needed"
            rec = f"Battery charge level is at or below the {reserve_threshold:.0f}% reserve threshold. Household is drawing power from utility grid."
        elif len(alerts) > 0:
            status_badge = "Healthy" if is_healthy else "Attention Needed"
            rec = f"Inverter alert recorded: {alerts[0].get('alertName', 'Warning')}. Inspect device status."
        elif conn_status != "NORMAL":
            status_badge = "Healthy" if is_healthy else "Attention Needed"
            rec = "Logger or inverter communication anomaly detected. Inspect local network connection."
        else:
            status_badge = "Healthy" if is_healthy else "Attention Needed"
            rec = "All devices operating normally within safe electrical parameters. No action required."

        return {
            "station_id": station_id,
            "station_name": meta["station_name"] or "Station Not Configured",
            "overall_status": status_badge,
            "is_healthy": is_healthy,
            "mcp_endpoint": self.mcp_endpoint,
            "read_only_enforced": True,
            "realtime_power": {
                "pv_kw": pv_kw,
                "load_kw": load_kw,
                "battery_kw": batt_kw,
                "grid_kw": grid_kw,
                "battery_soc_percent": soc
            },
            "device_health": {
                "logger": {
                    "serial": creds["logger_sn"],
                    "status": "Online" if conn_status == "NORMAL" else "Offline",
                    "reporting_interval_min": meta["logger_interval_min"]
                },
                "inverter": {
                    "serial": creds["inverter_sn"],
                    "model": meta["inverter_model"],
                    "status": "Operational" if conn_status == "NORMAL" else "Offline",
                    "rated_output_kw": meta["inverter_power_kw"]
                },
                "battery": {
                    "model": meta["battery_model"],
                    "soc_percent": soc,
                    "status": "Nominal" if soc >= reserve_threshold else ("Standby" if conn_status == "OFFLINE" else "At Reserve")
                }
            },
            "alerts_count": len(alerts),
            "active_alerts": alerts,
            "recommendation": rec
        }

    def _build_flow_payload(
        self,
        success: bool,
        is_live: bool,
        data_source: str,
        error: Optional[str],
        token_expired: bool,
        station_id: str,
        station_name: str,
        inverter_model: str,
        inverter_sn: str,
        conn_status: str,
        last_update_str: str,
        pv_w: float,
        load_w: float,
        batt_w: float,
        grid_w: float,
        soc: float,
        ups_w: float,
        dataset_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        batt_state = "IDLE"
        if batt_w > 10.0:
            batt_state = "DISCHARGING"
        elif batt_w < -10.0:
            batt_state = "CHARGING"

        grid_state = "IDLE"
        if grid_w > 5.0:
            grid_state = "IMPORT"
        elif grid_w < -5.0:
            grid_state = "EXPORT"

        grid_label = "Standby" if conn_status == "OFFLINE" else ("On grid" if conn_status == "NORMAL" else "Off grid")
        inv_status = "OPERATIONAL" if (is_live or data_source in ("demo", "cached")) else "STANDBY"

        payload: Dict[str, Any] = {
            "success": success,
            "is_live": is_live,
            "data_source": data_source,
            "error": error,
            "token_expired": token_expired,
            "station_name": station_name or "Station Not Configured",
            "station_id": station_id,
            "inverter_model": inverter_model,
            "inverter_serial": inverter_sn,
            "connection_status": conn_status,
            "is_on_grid": conn_status == "NORMAL",
            "last_update_time": last_update_str,
            "nodes": {
                "solar": {
                    "power_w": pv_w,
                    "power_kw": round(pv_w / 1000.0, 3),
                    "is_active": pv_w > 10.0
                },
                "battery": {
                    "soc_percent": soc,
                    "power_w": abs(batt_w),
                    "power_kw": round(abs(batt_w) / 1000.0, 3),
                    "state": batt_state,
                    "is_charging": batt_state == "CHARGING",
                    "is_discharging": batt_state == "DISCHARGING"
                },
                "inverter": {
                    "status": inv_status,
                    "throughput_w": max(pv_w, abs(batt_w), load_w),
                    "throughput_kw": round(max(pv_w, abs(batt_w), load_w) / 1000.0, 3)
                },
                "grid": {
                    "power_w": abs(grid_w),
                    "power_kw": round(abs(grid_w) / 1000.0, 3),
                    "status_label": grid_label,
                    "state": grid_state,
                    "is_importing": grid_state == "IMPORT",
                    "is_exporting": grid_state == "EXPORT"
                },
                "load": {
                    "power_w": load_w,
                    "power_kw": round(load_w / 1000.0, 3),
                    "is_active": load_w > 10.0
                },
                "ups": {
                    "power_w": ups_w,
                    "power_kw": round(ups_w / 1000.0, 3),
                    "is_active": ups_w > 10.0
                }
            },
            "summary": dataset_metrics["summary"],
            "utilization": dataset_metrics["utilization"]
        }
        return payload

    def get_live_flow(
        self,
        access_token_override: Optional[str] = None,
        station_id_override: Optional[str] = None,
        mode_override: Optional[str] = None
    ) -> Dict[str, Any]:
        creds = self._get_credentials()
        meta = self._get_system_meta()
        token_override = (access_token_override or "").strip() or None
        station_id = (station_id_override or "").strip() or creds["station_id"]
        mode_clean = (mode_override or "").strip().lower()
        has_server_creds = self._has_server_credentials(creds)

        if token_override and mode_clean != "demo":
            is_demo = False
        elif mode_clean == "demo":
            is_demo = True
        else:
            is_demo = creds["app_id"] == "demo" or creds["username"] == "demo"

        dataset_metrics = self._get_dataset_summary_metrics()

        if not is_demo and not token_override and not has_server_creds:
            return self._build_flow_payload(
                success=False,
                is_live=False,
                data_source="offline",
                error="Deye Cloud not configured",
                token_expired=False,
                station_id=station_id,
                station_name=meta["station_name"],
                inverter_model=meta["inverter_model"],
                inverter_sn=creds["inverter_sn"],
                conn_status="OFFLINE",
                last_update_str="",
                pv_w=0.0,
                load_w=0.0,
                batt_w=0.0,
                grid_w=0.0,
                soc=0.0,
                ups_w=0.0,
                dataset_metrics=dataset_metrics
            )

        if not is_demo and not str(station_id).isdigit():
            return self._build_flow_payload(
                success=False,
                is_live=False,
                data_source="offline",
                error="Station ID is required.",
                token_expired=False,
                station_id=station_id,
                station_name=meta["station_name"],
                inverter_model=meta["inverter_model"],
                inverter_sn=creds["inverter_sn"],
                conn_status="OFFLINE",
                last_update_str="",
                pv_w=0.0,
                load_w=0.0,
                batt_w=0.0,
                grid_w=0.0,
                soc=0.0,
                ups_w=0.0,
                dataset_metrics=dataset_metrics
            )

        if not is_demo:
            cred_sig = self._cred_signature(creds)
            cache_key = f"live:{station_id}:{cred_sig}"
        else:
            cache_key = f"demo:{station_id}"
        now_ts = datetime.datetime.now().timestamp()

        if not is_demo:
            cached_flow = self._cached_live_flows.get(cache_key)
            cached_time = self._cached_live_flow_times.get(cache_key, 0.0)
            if cached_flow is not None and (now_ts - cached_time) < 10.0:
                refreshed_copy = dict(cached_flow)
                refreshed_copy["station_name"] = meta["station_name"] or "Station Not Configured"
                refreshed_copy["inverter_model"] = meta["inverter_model"]
                refreshed_copy["inverter_serial"] = creds["inverter_sn"]
                refreshed_copy["summary"] = dataset_metrics["summary"]
                refreshed_copy["utilization"] = dataset_metrics["utilization"]
                return refreshed_copy

        if is_demo:
            now_manila = datetime.datetime.now(MANILA_TZ)
            h = now_manila.hour + now_manila.minute / 60.0
            is_day = 6.0 <= h <= 17.5
            pv_w = round(max(0.0, 3850.0 * (1.0 - ((h - 12.0) / 6.0) ** 2)), 1) if is_day else 0.0
            load_w = round(920.0 if 7.0 <= h <= 22.0 else 580.0, 1)
            batt_w = round(-(pv_w - load_w) if pv_w > load_w else load_w, 1)
            grid_w = 0.0
            soc = round(min(98.0, max(35.0, 42.0 + (pv_w / 100.0))), 1)
            ups_w = round(load_w * 0.98, 1)
            return self._build_flow_payload(
                success=True,
                is_live=False,
                data_source="demo",
                error=None,
                token_expired=False,
                station_id=station_id or "DEMO",
                station_name=meta["station_name"] or "Demo Station",
                inverter_model=meta["inverter_model"],
                inverter_sn=creds["inverter_sn"],
                conn_status="NORMAL",
                last_update_str=now_manila.strftime("%Y-%m-%d %H:%M:%S"),
                pv_w=pv_w,
                load_w=load_w,
                batt_w=batt_w,
                grid_w=grid_w,
                soc=soc,
                ups_w=ups_w,
                dataset_metrics=dataset_metrics
            )

        latest_res = self.get_station_latest(station_id, access_token_override=token_override)
        if latest_res.get("success"):
            raw = latest_res.get("raw", {})
            pv_w = float(raw["generationPower"]) if raw.get("generationPower") is not None else 0.0
            load_w = float(raw["consumptionPower"]) if raw.get("consumptionPower") is not None else 0.0

            if raw.get("chargePower") is not None and float(raw["chargePower"]) > 0:
                batt_w = -abs(float(raw["chargePower"]))
            elif raw.get("dischargePower") is not None and float(raw["dischargePower"]) > 0:
                batt_w = abs(float(raw["dischargePower"]))
            elif raw.get("batteryPower") is not None:
                batt_w = float(raw["batteryPower"])
            else:
                batt_w = 0.0

            if raw.get("wirePower") is not None:
                grid_w = float(raw["wirePower"])
            elif raw.get("purchasePower") is not None:
                grid_w = float(raw["purchasePower"])
            elif raw.get("gridPower") is not None:
                grid_w = -abs(float(raw["gridPower"]))
            else:
                grid_w = 0.0

            soc = float(raw["batterySOC"]) if raw.get("batterySOC") is not None else 0.0
            ups_w = float(raw["upsPower"]) if raw.get("upsPower") is not None else (round(load_w * 0.98, 1) if load_w > 0 else 0.0)
            conn_status = latest_res.get("connection_status", "NORMAL")
            last_update_str = self._parse_last_update_time(raw.get("lastUpdateTime"))

            flow_res = self._build_flow_payload(
                success=True,
                is_live=True,
                data_source="live",
                error=None,
                token_expired=False,
                station_id=station_id,
                station_name=meta["station_name"],
                inverter_model=meta["inverter_model"],
                inverter_sn=creds["inverter_sn"],
                conn_status=conn_status,
                last_update_str=last_update_str,
                pv_w=pv_w,
                load_w=load_w,
                batt_w=batt_w,
                grid_w=grid_w,
                soc=soc,
                ups_w=ups_w,
                dataset_metrics=dataset_metrics
            )
            self._cached_live_flows[cache_key] = flow_res
            self._cached_live_flow_times[cache_key] = datetime.datetime.now().timestamp()
            self._last_real_flows[cache_key] = flow_res
            self._save_db_last_flow(cache_key, flow_res)
            return flow_res

        last_real = self._last_real_flows.get(cache_key) or self._load_db_last_flow(cache_key)
        if last_real is not None:
            cached_copy = dict(last_real)
            cached_copy["is_live"] = False
            cached_copy["data_source"] = "cached"
            cached_copy["error"] = latest_res.get("error") or "Deye Cloud telemetry temporarily unreachable"
            cached_copy["token_expired"] = bool(latest_res.get("token_expired"))
            cached_copy["station_name"] = meta["station_name"] or "Station Not Configured"
            cached_copy["inverter_model"] = meta["inverter_model"]
            cached_copy["inverter_serial"] = creds["inverter_sn"]
            cached_copy["summary"] = dataset_metrics["summary"]
            cached_copy["utilization"] = dataset_metrics["utilization"]
            return cached_copy

        return self._build_flow_payload(
            success=False,
            is_live=False,
            data_source="offline",
            error=latest_res.get("error") or "Deye Cloud not configured or unreachable",
            token_expired=bool(latest_res.get("token_expired")),
            station_id=station_id,
            station_name=meta["station_name"],
            inverter_model=meta["inverter_model"],
            inverter_sn=creds["inverter_sn"],
            conn_status="OFFLINE",
            last_update_str="",
            pv_w=0.0,
            load_w=0.0,
            batt_w=0.0,
            grid_w=0.0,
            soc=0.0,
            ups_w=0.0,
            dataset_metrics=dataset_metrics
        )

deye_mcp_client = DeyeMCPClient()

def get_station_health(project_id: str = "default") -> Dict[str, Any]:
    return deye_mcp_client.get_station_health()
