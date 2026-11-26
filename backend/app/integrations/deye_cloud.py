import os
import json
import csv
import time
import hashlib
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.parse
import urllib.error
from backend.app.config import settings, is_hosted_mode
from backend.app.storage.db import get_connection
from backend.app.storage.blob_sync import ensure_hydrated, persist_state
from backend.app.storage.file_store import save_dataset_file_record
from backend.app.security.crypto import encrypt_secret, decrypt_secret
from backend.app.metrics.time_utils import resolve_zoneinfo
from backend.app.ingestion.normalizer import normalize_dataset
from backend.app.validation.quality_scorer import calculate_data_quality_report

_DATA_CENTER_URLS = {
    "eu": "https://eu1-developer.deyecloud.com",
    "am": "https://us1-developer.deyecloud.com",
    "us": "https://us1-developer.deyecloud.com",
    "india": "https://india-developer.deyecloud.com",
}

def resolve_deye_base_url(data_center: Optional[str]) -> str:
    key = (data_center or "eu").strip().lower()
    return _DATA_CENTER_URLS.get(key, _DATA_CENTER_URLS["eu"])

class DeyeCloudClient:
    def __init__(self, project_id: str = "default"):
        self.project_id = project_id
        self._last_token: Optional[str] = None
        self.data_center: str = "eu"
        self.timezone: str = "Asia/Manila"
        self._load_config()

    def _load_config(self):
        ensure_hydrated(force=False)
        conn = get_connection()
        row = conn.execute("SELECT * FROM deye_cloud_configs WHERE project_id = ?", (self.project_id,)).fetchone()
        sys_row = conn.execute("SELECT timezone FROM system_settings WHERE project_id = ?", (self.project_id,)).fetchone()
        conn.close()

        self.timezone = (sys_row["timezone"] or "Asia/Manila").strip() if sys_row else "Asia/Manila"
        allow_env_fallback = (not is_hosted_mode()) and (self.project_id == "default")

        if row:
            keys = row.keys()
            self.data_center = (row["data_center"] or "eu").strip().lower() if "data_center" in keys else "eu"
            self.station_id = (row["station_id"] or "").strip() or (os.environ.get("DEYE_STATION_ID", "").strip() if allow_env_fallback else "")
            self.app_id = (row["app_id"] or "").strip() or (os.environ.get("DEYE_APP_ID", "").strip() if allow_env_fallback else "")
            db_secret = decrypt_secret(row["app_secret"])
            self.app_secret = db_secret or (os.environ.get("DEYE_APP_SECRET", "").strip() if allow_env_fallback else "")
            self.username = (row["username"] or "").strip() or (os.environ.get("DEYE_USERNAME", "").strip() if allow_env_fallback else "")
            db_pwd = decrypt_secret(row["password_encrypted"])
            self.password = db_pwd or (os.environ.get("DEYE_PASSWORD", "").strip() if allow_env_fallback else "")
            self.auto_sync = bool(row["auto_sync"])
            self.sync_interval_min = max(1, int(row["sync_interval_min"] or 5))
            self.last_sync_time = row["last_sync_time"]
            self.sync_status = row["sync_status"] or "IDLE"
            self.sync_message = row["sync_message"] or ""
            self.reconciliation_policy = row["reconciliation_policy"] or "MERGE"
        else:
            self.data_center = "eu"
            self.station_id = os.environ.get("DEYE_STATION_ID", "").strip() if allow_env_fallback else ""
            self.app_id = os.environ.get("DEYE_APP_ID", "").strip() if allow_env_fallback else ""
            self.app_secret = os.environ.get("DEYE_APP_SECRET", "").strip() if allow_env_fallback else ""
            self.username = os.environ.get("DEYE_USERNAME", "").strip() if allow_env_fallback else ""
            self.password = os.environ.get("DEYE_PASSWORD", "").strip() if allow_env_fallback else ""
            self.auto_sync = False
            self.sync_interval_min = 5
            self.last_sync_time = None
            self.sync_status = "IDLE"
            self.sync_message = ""
            self.reconciliation_policy = "MERGE"

    def get_status(self) -> Dict[str, Any]:
        self._load_config()
        conn = get_connection()
        recent_logs = conn.execute(
            "SELECT * FROM deye_sync_logs WHERE project_id = ? ORDER BY sync_time DESC LIMIT 5",
            (self.project_id,)
        ).fetchall()
        settings_row = conn.execute(
            "SELECT station_name, location_name, inverter_serial, inverter_model, inverter_power_kw, logger_serial, logger_firmware, logger_interval_min FROM system_settings WHERE project_id = ?",
            (self.project_id,)
        ).fetchone()
        conn.close()

        is_demo = self.app_id == "demo" or self.username == "demo"
        is_configured = is_demo or bool(self.app_id and self.app_secret and self.username and self.password and self.station_id)

        s_name = (settings_row["station_name"] or "").strip() if settings_row and "station_name" in settings_row.keys() else ""
        loc_name = (settings_row["location_name"] or "").strip() if settings_row and "location_name" in settings_row.keys() else ""
        if s_name and loc_name:
            inst_label = f"{s_name} ({loc_name})"
        else:
            inst_label = s_name or loc_name or "Station Not Configured"

        verified_online = is_configured and self.sync_status in ("CONNECTED", "SUCCESS")
        if not is_configured:
            hw_status = "UNCONFIGURED"
        elif self.sync_status in ("ERROR", "FAILED"):
            hw_status = "ERROR"
        elif verified_online:
            hw_status = "CONNECTED"
        else:
            hw_status = "CONFIGURED_UNVERIFIED"

        device_hierarchy = {
            "installation_name": inst_label,
            "station": {
                "station_id": self.station_id or "",
                "status": "CONFIGURED" if is_configured else "UNCONFIGURED"
            },
            "logger": {
                "logger_serial": (settings_row["logger_serial"] or "") if settings_row else "",
                "firmware_version": (settings_row["logger_firmware"] or "") if settings_row else "",
                "reporting_interval_min": (settings_row["logger_interval_min"] or 5) if settings_row else 5,
                "status": hw_status
            },
            "inverter": {
                "inverter_serial": (settings_row["inverter_serial"] or "") if settings_row else "",
                "model": (settings_row["inverter_model"] or "") if settings_row else "",
                "rated_power_kw": float(settings_row["inverter_power_kw"] or 0.0) if settings_row else 0.0,
                "status": hw_status
            }
        }

        return {
            "is_configured": is_configured,
            "is_demo": is_demo,
            "data_center": self.data_center,
            "has_app_secret": bool(self.app_secret),
            "has_password": bool(self.password),
            "station_id": self.station_id,
            "app_id": self.app_id,
            "username": self.username,
            "auto_sync": self.auto_sync,
            "sync_interval_min": self.sync_interval_min,
            "last_sync_time": self.last_sync_time,
            "sync_status": self.sync_status,
            "sync_message": self.sync_message,
            "reconciliation_policy": self.reconciliation_policy,
            "device_hierarchy": device_hierarchy,
            "recent_logs": [dict(r) for r in recent_logs]
        }

    def save_config(self, config_data: Dict[str, Any]) -> None:
        ensure_hydrated(force=True)
        conn = get_connection()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        raw_secret = (config_data.get("app_secret") or "").strip()
        raw_password = (config_data.get("password") or "").strip()
        enc_secret = encrypt_secret(raw_secret) if raw_secret else ""
        enc_password = encrypt_secret(raw_password) if raw_password else ""
        data_center = (config_data.get("data_center") or "eu").strip().lower()
        if data_center not in _DATA_CENTER_URLS:
            data_center = "eu"

        conn.execute(
            """INSERT INTO deye_cloud_configs (
                id, project_id, station_id, data_center, app_id, app_secret, username, password_encrypted,
                auto_sync, sync_interval_min, reconciliation_policy, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                station_id = CASE WHEN excluded.station_id != '' THEN excluded.station_id ELSE deye_cloud_configs.station_id END,
                data_center = CASE WHEN excluded.data_center != '' THEN excluded.data_center ELSE deye_cloud_configs.data_center END,
                app_id = CASE WHEN excluded.app_id != '' THEN excluded.app_id ELSE deye_cloud_configs.app_id END,
                app_secret = CASE WHEN excluded.app_secret != '' THEN excluded.app_secret ELSE deye_cloud_configs.app_secret END,
                username = CASE WHEN excluded.username != '' THEN excluded.username ELSE deye_cloud_configs.username END,
                password_encrypted = CASE WHEN excluded.password_encrypted != '' THEN excluded.password_encrypted ELSE deye_cloud_configs.password_encrypted END,
                auto_sync = excluded.auto_sync,
                sync_interval_min = excluded.sync_interval_min,
                reconciliation_policy = excluded.reconciliation_policy,
                updated_at = excluded.updated_at
            """,
            (
                f"deye-{self.project_id}",
                self.project_id,
                (config_data.get("station_id") or "").strip(),
                data_center,
                (config_data.get("app_id") or "").strip(),
                enc_secret,
                (config_data.get("username") or "").strip(),
                enc_password,
                1 if config_data.get("auto_sync") else 0,
                max(1, int(config_data.get("sync_interval_min", 5) or 5)),
                config_data.get("reconciliation_policy", "MERGE"),
                now_iso
            )
        )
        conn.commit()
        conn.close()
        try:
            c2 = get_connection()
            c2.execute("DELETE FROM deye_live_cache WHERE project_id = ?", (self.project_id,))
            c2.commit()
            c2.close()
        except Exception:
            pass
        try:
            from backend.app.integrations.deye_mcp import get_deye_mcp_client
            get_deye_mcp_client(self.project_id).invalidate_cache(clear_last_real=True)
        except Exception:
            pass
        persist_state()
        self._load_config()

    def clear_config(self) -> None:
        ensure_hydrated(force=True)
        conn = get_connection()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.execute(
            """UPDATE deye_cloud_configs SET
                station_id = '', data_center = 'eu', app_id = '', app_secret = '',
                username = '', password_encrypted = '',
                auto_sync = 0, sync_status = 'IDLE', sync_message = 'Not connected',
                last_sync_time = NULL, updated_at = ?
               WHERE project_id = ?""",
            (now_iso, self.project_id)
        )
        conn.execute("DELETE FROM deye_sync_logs WHERE project_id = ?", (self.project_id,))
        conn.execute("DELETE FROM deye_live_cache WHERE project_id = ?", (self.project_id,))
        conn.commit()
        conn.close()
        try:
            from backend.app.integrations.deye_mcp import get_deye_mcp_client
            get_deye_mcp_client(self.project_id).invalidate_cache(clear_last_real=True)
        except Exception:
            pass
        persist_state()
        self._load_config()

    def _post_json(self, url: str, payload: bytes, headers: Dict[str, str], timeout: int = 12) -> Dict[str, Any]:
        last_err: Optional[Exception] = None
        for attempt in range(3):
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as he:
                if he.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                try:
                    err_data = json.loads(he.read().decode("utf-8"))
                    raise Exception(err_data.get("msg") or f"HTTP {he.code}: {he.reason}")
                except Exception as inner:
                    if str(inner):
                        raise
                    raise Exception(f"HTTP {he.code}: {he.reason}")
            except Exception as exc:
                last_err = exc
                if attempt < 2:
                    time.sleep(0.4 * (2 ** attempt))
                    continue
                raise
        if last_err:
            raise last_err
        return {}

    def _get_auth_token(self) -> Optional[str]:
        if not (self.app_id and self.app_secret):
            raise Exception("Missing App ID or App Secret.")
        if not (self.username and self.password):
            raise Exception("Missing Account Email/Username or Account Password. Deye Cloud requires both your Developer App credentials and your Deye Cloud account login.")
        pwd_hash = hashlib.sha256(self.password.encode("utf-8")).hexdigest().lower()
        auth_body: Dict[str, Any] = {
            "appSecret": self.app_secret,
            "password": pwd_hash
        }
        if "@" in self.username:
            auth_body["email"] = self.username
        else:
            auth_body["username"] = self.username
        payload = json.dumps(auth_body).encode("utf-8")

        base_url = resolve_deye_base_url(self.data_center)
        endpoint = f"{base_url}/v1.0/account/token?appId={urllib.parse.quote(self.app_id)}"
        data = self._post_json(endpoint, payload, {"Content-Type": "application/json"}, timeout=10)
        if data.get("success") and "accessToken" in data:
            self._last_token = data["accessToken"]
            return data["accessToken"]
        raise Exception(data.get("msg") or "Deye Cloud authentication rejected.")

    def try_get_token(self) -> Optional[str]:
        self._load_config()
        if self.app_id == "demo" or self.username == "demo":
            return None
        if not (self.app_id and self.app_secret and self.username and self.password):
            return None
        try:
            return self._get_auth_token()
        except Exception:
            return None

    def test_connection(self) -> Dict[str, Any]:
        self._load_config()
        if self.app_id == "demo" or self.username == "demo":
            self._update_status("CONNECTED", "Demo mode active with simulated telemetry stream.")
            return {
                "success": True,
                "message": "Demo mode active with simulated telemetry stream.",
                "is_demo": True,
                "station_id": self.station_id or "DEMO"
            }

        if not (self.app_id and self.app_secret and self.username and self.password):
            return {
                "success": False,
                "message": "Incomplete credentials. Enter Station ID, App ID, App Secret, Account Email/Username, and Account Password."
            }

        if not (self.station_id and self.station_id.isdigit()):
            return {
                "success": False,
                "message": "Numeric Station ID is required to test Deye Cloud connection."
            }

        try:
            token = self._get_auth_token()
            if not token:
                return {"success": False, "message": "Authentication failed. Check your App ID, App Secret, email/username, or account password."}

            st_id = int(self.station_id)
            base_url = resolve_deye_base_url(self.data_center)
            latest_data = self._post_json(
                f"{base_url}/v1.0/station/latest",
                json.dumps({"stationId": st_id}).encode("utf-8"),
                {"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                timeout=10
            )

            if latest_data.get("success") is False:
                raise Exception(latest_data.get("msg") or "Station query failed")

            conn_s = get_connection()
            s_row = conn_s.execute("SELECT station_name FROM system_settings WHERE project_id = ?", (self.project_id,)).fetchone()
            conn_s.close()
            station_label = (s_row["station_name"] or "").strip() if s_row else ""
            label_part = f"{station_label} (Station {st_id})" if station_label else f"Station {st_id}"

            conn_status = latest_data.get("connectionStatus") or "UNKNOWN"
            pv_raw = latest_data.get("generationPower")
            soc_raw = latest_data.get("batterySOC")
            pv_text = f"{float(pv_raw) / 1000.0:.2f} kW" if pv_raw is not None else "unavailable"
            soc_text = f"{float(soc_raw):.0f}% SOC" if soc_raw is not None else "SOC unavailable"

            if conn_status != "NORMAL":
                msg = f"Authenticated to {label_part}, but station reports {conn_status}. Live Solar: {pv_text}, Battery: {soc_text}."
                self._update_status("CONNECTED", msg)
            else:
                msg = f"Connected to {label_part} ({conn_status}). Live Solar: {pv_text}, Battery: {soc_text}."
                self._update_status("CONNECTED", msg)
            persist_state()
            return {
                "success": True,
                "message": msg,
                "station_id": str(st_id),
                "connection_status": conn_status,
                "is_demo": False
            }
        except Exception as e:
            msg = str(e)
            self._update_status("ERROR", msg)
            persist_state()
            return {"success": False, "message": msg}

    def get_missing_dates(self) -> List[str]:
        self._load_config()
        conn = get_connection()
        rows = conn.execute(
            "SELECT start_time, end_time FROM datasets WHERE is_included = 1 AND project_id = ?",
            (self.project_id,)
        ).fetchall()
        conn.close()

        covered_days = set()
        min_date = None
        for r in rows:
            if r["start_time"]:
                try:
                    d_start = datetime.date.fromisoformat(str(r["start_time"]).split(" ")[0][:10])
                    if min_date is None or d_start < min_date:
                        min_date = d_start
                    d_end = datetime.date.fromisoformat(str(r["end_time"]).split(" ")[0][:10]) if r["end_time"] else d_start
                    cur = d_start
                    while cur <= d_end:
                        covered_days.add(cur.isoformat())
                        cur += datetime.timedelta(days=1)
                except Exception:
                    continue

        tz = resolve_zoneinfo(self.timezone)
        today = datetime.datetime.now(tz).date()
        two_weeks_ago = today - datetime.timedelta(days=13)
        if not min_date or min_date > two_weeks_ago:
            min_date = two_weeks_ago

        missing = []
        cur = min_date
        while cur <= today:
            iso = cur.isoformat()
            if iso not in covered_days:
                missing.append(iso)
            cur += datetime.timedelta(days=1)
        return missing

    def _parse_date(self, s: str) -> datetime.date:
        s = s.strip()
        if "/" in s:
            parts = s.split("/")
            if len(parts) == 3:
                if len(parts[2]) == 4:
                    return datetime.date(int(parts[2]), int(parts[0]), int(parts[1]))
                elif len(parts[0]) == 4:
                    return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        if "-" in s:
            parts = s.split("-")
            if len(parts) == 3:
                if len(parts[0]) == 4:
                    return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                elif len(parts[2]) == 4:
                    return datetime.date(int(parts[2]), int(parts[0]), int(parts[1]))
        return datetime.date.fromisoformat(s)

    def fetch_range_from_cloud(self, start_date_str: str, end_date_str: str) -> List[Dict[str, Any]]:
        self._load_config()
        tz = resolve_zoneinfo(self.timezone)
        d_start = self._parse_date(start_date_str)
        d_end = self._parse_date(end_date_str)
        now_local = datetime.datetime.now(tz).date()
        d_end = min(d_end, now_local)
        if d_start > d_end:
            d_start = d_end

        if self.app_id == "demo" or self.username == "demo":
            simulated = []
            cur_d = d_start
            while cur_d <= d_end:
                for h in range(24):
                    for m in (0, 30):
                        ts_str = f"{cur_d.isoformat()} {h:02d}:{m:02d}:00"
                        is_day = 6 <= h <= 17
                        pv = round(max(0.0, 4.2 * (1 - ((h - 12)/6)**2)), 3) if is_day else 0.0
                        load = round(0.6 + (0.5 if (11 <= h <= 14 or 18 <= h <= 21) else 0.0), 3)
                        batt = round(pv - load, 3)
                        grid = 0.0
                        soc = round(min(100.0, max(25.0, 25.0 + (pv * 15.0) - (load * 5.0))), 1)
                        simulated.append({
                            "Time": ts_str,
                            "PV Power(kW)": pv,
                            "Load Power(kW)": load,
                            "Grid Power(kW)": grid,
                            "Battery Power(kW)": batt,
                            "Battery SOC(%)": soc,
                            "Generator Power(kW)": 0.0,
                            "Grid-tied Inverter Power(kW)": 0.0
                        })
                cur_d += datetime.timedelta(days=1)
            return simulated

        token = self._get_auth_token()
        if not token:
            raise Exception("Authentication failed. Check your App ID, App Secret, or account password.")

        if not (self.station_id and self.station_id.isdigit()):
            raise Exception("Numeric Station ID is required.")
        st_id = int(self.station_id)
        base_url = resolve_deye_base_url(self.data_center)
        all_records = []
        seen_timestamps = set()
        last_api_error = None

        chunk_start = d_start
        while chunk_start <= d_end:
            chunk_end = min(d_end, chunk_start + datetime.timedelta(days=2))
            dt_start = int(datetime.datetime(chunk_start.year, chunk_start.month, chunk_start.day, 0, 0, 0, tzinfo=tz).timestamp())
            dt_end = int(datetime.datetime(chunk_end.year, chunk_end.month, chunk_end.day, 23, 59, 59, tzinfo=tz).timestamp())

            req_payload = json.dumps({
                "stationId": st_id,
                "startTimestamp": dt_start,
                "endTimestamp": dt_end
            }).encode("utf-8")

            power_url = f"{base_url}/v1.0/station/history/power"
            try:
                res = self._post_json(
                    power_url,
                    req_payload,
                    {"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                    timeout=15
                )
                if res.get("success") is False and res.get("msg"):
                    last_api_error = res["msg"]
            except Exception as e:
                last_api_error = str(e)
                chunk_start = chunk_end + datetime.timedelta(days=1)
                continue

            items = res.get("stationDataItems", [])
            for it in items:
                ts_sec = it.get("timeStamp")
                if not ts_sec or ts_sec in seen_timestamps:
                    continue
                seen_timestamps.add(ts_sec)
                t_str = datetime.datetime.fromtimestamp(ts_sec, tz=tz).strftime("%Y-%m-%d %H:%M:%S")

                pv_raw = it.get("generationPower")
                pv_kw: Any = round(float(pv_raw) / 1000.0, 4) if pv_raw is not None else ""

                load_raw = it.get("consumptionPower")
                load_kw: Any = round(float(load_raw) / 1000.0, 4) if load_raw is not None else ""

                grid_w = it.get("wirePower")
                if grid_w is None:
                    grid_w = it.get("purchasePower")
                grid_kw: Any = round(float(grid_w) / 1000.0, 4) if grid_w is not None else ""

                batt_w = it.get("batteryPower")
                if batt_w is None:
                    if it.get("dischargePower") is not None:
                        batt_w = it.get("dischargePower")
                    elif it.get("chargePower") is not None:
                        batt_w = -abs(float(it.get("chargePower")))
                batt_kw: Any = round(float(batt_w) / 1000.0, 4) if batt_w is not None else ""

                soc_raw = it.get("batterySOC")
                soc: Any = round(float(soc_raw), 1) if soc_raw is not None else ""

                all_records.append({
                    "Time": t_str,
                    "PV Power(kW)": pv_kw,
                    "Load Power(kW)": load_kw,
                    "Grid Power(kW)": grid_kw,
                    "Battery Power(kW)": batt_kw,
                    "Battery SOC(%)": soc,
                    "Generator Power(kW)": 0.0,
                    "Grid-tied Inverter Power(kW)": 0.0
                })
            chunk_start = chunk_end + datetime.timedelta(days=1)

        if not all_records and last_api_error:
            raise Exception(last_api_error)

        all_records.sort(key=lambda r: r["Time"])
        return all_records

    def persist_telemetry_dataset(self, records: List[Dict[str, Any]], start_date_str: str, end_date_str: str) -> Dict[str, Any]:
        if not records:
            return {"status": "SKIPPED", "message": f"No telemetry points available for {start_date_str} to {end_date_str}.", "records_inserted": 0}

        days_dict: Dict[str, List[Dict[str, Any]]] = {}
        for r in records:
            t = r.get("Time") or r.get("timestamp") or ""
            if not t:
                continue
            day_key = str(t).split(" ")[0][:10]
            if day_key not in days_dict:
                days_dict[day_key] = []
            days_dict[day_key].append(r)

        if not days_dict:
            return {"status": "SKIPPED", "message": f"No valid timestamped records found for {start_date_str} to {end_date_str}.", "records_inserted": 0}

        fieldnames = ["Time", "PV Power(kW)", "Load Power(kW)", "Grid Power(kW)", "Battery Power(kW)", "Battery SOC(%)", "Generator Power(kW)", "Grid-tied Inverter Power(kW)"]
        canonical_map = {
            "Time": "timestamp",
            "PV Power(kW)": "pv_power_kw",
            "Load Power(kW)": "load_power_kw",
            "Grid Power(kW)": "grid_power_kw",
            "Battery Power(kW)": "battery_power_kw",
            "Battery SOC(%)": "soc_percent",
            "Generator Power(kW)": "generator_power_kw",
            "Grid-tied Inverter Power(kW)": "grid_tied_inverter_power_kw"
        }
        sign_conventions = {
            "battery_power_kw": "positive_discharge",
            "grid_power_kw": "positive_import"
        }

        conn = get_connection()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        total_rows = 0
        created_datasets = []
        created_files: List[Path] = []
        settings.upload_dir.mkdir(parents=True, exist_ok=True)

        legacy_composite_id = f"deye-{start_date_str}-to-{end_date_str}"
        conn.execute(
            "DELETE FROM datasets WHERE project_id = ? AND (id = ? OR filename LIKE 'Deye Cloud (% to %).csv' OR id LIKE 'deye-%-to-%')",
            (self.project_id, legacy_composite_id)
        )

        is_default_proj = (self.project_id == "default")
        for day_key in sorted(days_dict.keys()):
            day_records = days_dict[day_key]
            day_records.sort(key=lambda x: x.get("Time", ""))
            day_count = len(day_records)
            total_rows += day_count

            if is_default_proj:
                csv_id = f"deye_{day_key}".replace("-", "")
                dataset_id = f"deye-{day_key}"
            else:
                safe_proj = "".join(ch for ch in self.project_id if ch.isalnum() or ch in ("-", "_"))[:24]
                csv_id = f"deye_{safe_proj}_{day_key}".replace("-", "")
                dataset_id = f"deye-{safe_proj}-{day_key}"

            filename = f"Deye Cloud ({day_key}).csv"
            file_path = settings.upload_dir / f"{csv_id}.csv"

            if self.reconciliation_policy == "KEEP_EXISTING":
                existing_row = conn.execute(
                    "SELECT id FROM datasets WHERE id = ? AND project_id = ?",
                    (dataset_id, self.project_id)
                ).fetchone()
                if existing_row and len(day_records) < 10:
                    continue

            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in day_records:
                    writer.writerow(r)

            file_bytes = file_path.read_bytes()
            file_hash = hashlib.sha256(file_bytes).hexdigest()

            canonical_day = normalize_dataset(day_records, canonical_map, sign_conventions, timezone=self.timezone)
            q_rep = calculate_data_quality_report(canonical_day)
            q_score = float(q_rep.get("quality_score") or 0.0)
            sampling_med = float((q_rep.get("sampling_audit") or {}).get("median_interval_minutes") or 5.0)
            gap_cnt = len((q_rep.get("sampling_audit") or {}).get("gaps") or [])

            start_time = day_records[0]["Time"]
            end_time = day_records[-1]["Time"]

            conn.execute(
                """INSERT INTO datasets (
                    id, project_id, filename, file_hash, file_format, filepath, sheet_name,
                    total_rows, start_time, end_time, quality_score, sampling_interval_median_min,
                    gap_count, conflict_status, is_active, is_included, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    total_rows = excluded.total_rows,
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    filepath = excluded.filepath,
                    file_hash = excluded.file_hash,
                    quality_score = excluded.quality_score,
                    sampling_interval_median_min = excluded.sampling_interval_median_min,
                    gap_count = excluded.gap_count,
                    created_at = excluded.created_at
                """,
                (
                    dataset_id, self.project_id, filename, file_hash, "csv", str(file_path), "Telemetry",
                    day_count, start_time, end_time, q_score, sampling_med, gap_cnt, "NONE", 1, 1, now_iso
                )
            )
            save_dataset_file_record(conn, dataset_id, self.project_id, filename, file_bytes)

            mapping_id = f"map-{dataset_id}"
            conn.execute(
                """INSERT INTO column_mappings (
                    id, dataset_id, raw_headers_json, mapping_json, sign_conventions_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(dataset_id) DO UPDATE SET
                    raw_headers_json = excluded.raw_headers_json,
                    mapping_json = excluded.mapping_json,
                    sign_conventions_json = excluded.sign_conventions_json,
                    created_at = excluded.created_at""",
                (mapping_id, dataset_id, json.dumps(fieldnames), json.dumps(canonical_map), json.dumps(sign_conventions), now_iso)
            )
            created_datasets.append(dataset_id)
            created_files.append(file_path)

        conn.commit()
        conn.close()

        try:
            from backend.app.api.endpoints import invalidate_all_caches
            invalidate_all_caches(self.project_id)
        except Exception:
            pass

        msg = f"Synced {len(created_datasets)} daily dataset(s) ({total_rows} records) from {start_date_str} to {end_date_str}."
        log_id = f"log-{self.project_id}-{int(datetime.datetime.now().timestamp() * 1000)}"
        self._record_log(log_id, now_iso, total_rows, total_rows, 0, "SUCCESS", msg)
        self._update_status("SUCCESS", msg, now_iso)
        persist_state(upload_files=created_files)
        return {
            "status": "SUCCESS",
            "datasets_created": created_datasets,
            "days_count": len(created_datasets),
            "records_inserted": total_rows,
            "message": msg
        }

    def sync_range(self, start_date_str: str, end_date_str: str) -> Dict[str, Any]:
        self._update_status("SYNCING", f"Fetching Deye Cloud telemetry for {start_date_str} to {end_date_str}...")
        try:
            records = self.fetch_range_from_cloud(start_date_str, end_date_str)
            res = self.persist_telemetry_dataset(records, start_date_str, end_date_str)
            is_demo = self.app_id == "demo" or self.username == "demo"
            res["is_demo"] = is_demo
            res["station_id"] = self.station_id or ("DEMO" if is_demo else "")
            try:
                from backend.app.integrations.deye_mcp import get_deye_mcp_client
                get_deye_mcp_client(self.project_id).invalidate_cache(clear_last_real=False)
            except Exception:
                pass
            return res
        except Exception as e:
            err = str(e)
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            log_id = f"log-{self.project_id}-{int(datetime.datetime.now().timestamp() * 1000)}"
            self._record_log(log_id, now_iso, 0, 0, 0, "FAILED", err)
            self._update_status("FAILED", err)
            persist_state()
            return {"status": "FAILED", "message": err, "records_inserted": 0}

    def sync_missing_dates(self) -> Dict[str, Any]:
        missing = self.get_missing_dates()
        if not missing:
            return {"status": "SUCCESS", "message": "No missing dates detected. All days up to today are recorded.", "records_inserted": 0, "missing_dates": []}

        spans: List[tuple[str, str]] = []
        span_start = missing[0]
        prev_dt = datetime.date.fromisoformat(missing[0])
        for d_str in missing[1:]:
            cur_dt = datetime.date.fromisoformat(d_str)
            if (cur_dt - prev_dt).days == 1:
                prev_dt = cur_dt
            else:
                spans.append((span_start, prev_dt.isoformat()))
                span_start = d_str
                prev_dt = cur_dt
        spans.append((span_start, prev_dt.isoformat()))

        total_inserted = 0
        details: List[str] = []
        for s_start, s_end in spans:
            res = self.sync_range(s_start, s_end)
            if res.get("status") == "SUCCESS":
                total_inserted += res.get("records_inserted", 0)
                cur_d = datetime.date.fromisoformat(s_start)
                end_d = datetime.date.fromisoformat(s_end)
                while cur_d <= end_d:
                    details.append(cur_d.isoformat())
                    cur_d += datetime.timedelta(days=1)

        msg = f"Backfilled {len(details)} missing dates ({', '.join(details)}): {total_inserted} total records."
        return {
            "status": "SUCCESS",
            "message": msg,
            "records_inserted": total_inserted,
            "backfilled_dates": details
        }

    def sync_now(self) -> Dict[str, Any]:
        self._load_config()
        is_demo = self.app_id == "demo" or self.username == "demo"
        if not is_demo and not (self.app_id and self.app_secret):
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            log_id = f"log-{self.project_id}-{int(datetime.datetime.now().timestamp() * 1000)}"
            msg = "Deye Cloud credentials not configured. Enter App ID and App Secret."
            self._record_log(log_id, now_iso, 0, 0, 0, "SKIPPED", msg)
            self._update_status("IDLE", msg)
            return {"status": "SKIPPED", "message": msg, "records_fetched": 0, "records_inserted": 0}

        tz = resolve_zoneinfo(self.timezone)
        today = datetime.datetime.now(tz).date()
        yesterday = today - datetime.timedelta(days=1)
        return self.sync_range(yesterday.isoformat(), today.isoformat())

    def _update_status(self, status: str, message: str, last_sync: Optional[str] = None):
        conn = get_connection()
        if last_sync:
            conn.execute(
                "UPDATE deye_cloud_configs SET sync_status = ?, sync_message = ?, last_sync_time = ? WHERE project_id = ?",
                (status, message, last_sync, self.project_id)
            )
        else:
            conn.execute(
                "UPDATE deye_cloud_configs SET sync_status = ?, sync_message = ? WHERE project_id = ?",
                (status, message, self.project_id)
            )
        conn.commit()
        conn.close()

    def _record_log(self, log_id: str, sync_time: str, fetched: int, inserted: int, skipped: int, status: str, err: str):
        conn = get_connection()
        conn.execute(
            """INSERT INTO deye_sync_logs (id, project_id, sync_time, records_fetched, records_inserted, records_skipped, status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (log_id, self.project_id, sync_time, fetched, inserted, skipped, status, err)
        )
        conn.commit()
        conn.close()
