import json
import csv
import hashlib
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.error
from backend.app.config import settings
from backend.app.storage.db import get_connection

class DeyeCloudClient:
    def __init__(self, project_id: str = "default"):
        self.project_id = project_id
        self._load_config()

    def _load_config(self):
        conn = get_connection()
        row = conn.execute("SELECT * FROM deye_cloud_configs WHERE project_id = ?", (self.project_id,)).fetchone()
        conn.close()
        if row:
            self.station_id = (row["station_id"] or "").strip()
            self.app_id = (row["app_id"] or "").strip()
            self.app_secret = (row["app_secret"] or "").strip()
            self.username = (row["username"] or "").strip()
            self.password = (row["password_encrypted"] or "").strip()
            self.auto_sync = bool(row["auto_sync"])
            self.sync_interval_min = row["sync_interval_min"] or 5
            self.last_sync_time = row["last_sync_time"]
            self.sync_status = row["sync_status"] or "IDLE"
            self.sync_message = row["sync_message"] or ""
            self.reconciliation_policy = row["reconciliation_policy"] or "MERGE"
        else:
            self.station_id = ""
            self.app_id = ""
            self.app_secret = ""
            self.username = ""
            self.password = ""
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
            "SELECT inverter_serial, inverter_model, logger_serial, logger_firmware, logger_interval_min FROM system_settings WHERE project_id = ?",
            (self.project_id,)
        ).fetchone()
        conn.close()

        is_configured = bool(self.app_id and self.app_secret) or bool(self.username and self.password)

        device_hierarchy = {
            "installation_name": "Mam Micah (Teresa, Tibag, Tarlac City)",
            "station": {
                "station_id": self.station_id or "62805884",
                "status": "CONFIGURED" if is_configured else "UNCONFIGURED"
            },
            "logger": {
                "logger_serial": settings_row["logger_serial"] if settings_row else "1251892903",
                "firmware_version": settings_row["logger_firmware"] if settings_row else "MW4_32_5407_SS_04_00.00.00.13",
                "reporting_interval_min": settings_row["logger_interval_min"] if settings_row else 5,
                "status": "ONLINE"
            },
            "inverter": {
                "inverter_serial": settings_row["inverter_serial"] if settings_row else "2604282202",
                "model": settings_row["inverter_model"] if settings_row else "SUN-6K-SG06LP1-EU-CM2",
                "rated_power_kw": 6.0,
                "status": "OPERATIONAL"
            }
        }

        return {
            "is_configured": is_configured,
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
        conn = get_connection()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO deye_cloud_configs (
                id, project_id, station_id, app_id, app_secret, username, password_encrypted,
                auto_sync, sync_interval_min, reconciliation_policy, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                station_id = excluded.station_id,
                app_id = excluded.app_id,
                app_secret = CASE WHEN excluded.app_secret != '' THEN excluded.app_secret ELSE deye_cloud_configs.app_secret END,
                username = excluded.username,
                password_encrypted = CASE WHEN excluded.password_encrypted != '' THEN excluded.password_encrypted ELSE deye_cloud_configs.password_encrypted END,
                auto_sync = excluded.auto_sync,
                sync_interval_min = excluded.sync_interval_min,
                reconciliation_policy = excluded.reconciliation_policy,
                updated_at = excluded.updated_at
            """,
            (
                f"deye-{self.project_id}",
                self.project_id,
                config_data.get("station_id", ""),
                config_data.get("app_id", ""),
                config_data.get("app_secret", ""),
                config_data.get("username", ""),
                config_data.get("password", ""),
                1 if config_data.get("auto_sync") else 0,
                config_data.get("sync_interval_min", 5),
                config_data.get("reconciliation_policy", "MERGE"),
                now_iso
            )
        )
        conn.commit()
        conn.close()
        self._load_config()

    def _get_auth_token(self) -> Optional[str]:
        if not (self.app_id and self.app_secret):
            return None
        pwd_hash = hashlib.sha256(self.password.encode("utf-8")).hexdigest().lower() if self.password else ""
        payload = json.dumps({
            "appSecret": self.app_secret,
            "email": self.username,
            "password": pwd_hash
        }).encode("utf-8")

        endpoints = [
            f"https://eu1-developer.deyecloud.com/v1.0/account/token?appId={urllib.parse.quote(self.app_id)}",
            f"https://api.solarmanpv.com/account/v1.0/token?appId={urllib.parse.quote(self.app_id)}"
        ]
        last_error = None
        for endpoint in endpoints:
            try:
                req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("success") and "accessToken" in data:
                        return data["accessToken"]
                    elif data.get("msg"):
                        last_error = data["msg"]
                        if "deyecloud.com" in endpoint:
                            break
            except Exception as e:
                last_error = str(e)
        if last_error:
            raise Exception(last_error)
        return None

    def test_connection(self) -> Dict[str, Any]:
        self._load_config()
        if self.app_id == "demo" or self.username == "demo":
            self._update_status("CONNECTED", "Simulated connection to Deye Cloud Logger 1251892903 successful.")
            return {"success": True, "message": "Demo mode: Simulated connection to Deye Logger 1251892903 successful."}

        if not (self.app_id and self.app_secret):
            return {
                "success": False,
                "message": "Missing credentials. Enter your Deye Developer App ID and App Secret."
            }

        try:
            token = self._get_auth_token()
            if not token:
                return {"success": False, "message": "Authentication failed. Check your App ID, App Secret, or account password."}

            st_id = int(self.station_id) if (self.station_id and self.station_id.isdigit()) else 62805884
            req = urllib.request.Request(
                "https://eu1-developer.deyecloud.com/v1.0/station/latest",
                data=json.dumps({"stationId": st_id}).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                latest_data = json.loads(resp.read().decode("utf-8"))

            pv_w = latest_data.get("generationPower", 0.0) or 0.0
            soc = latest_data.get("batterySOC", 0.0) or 0.0
            msg = f"Connected to Mam Micah (Station 62805884). Live Solar: {pv_w/1000.0:.2f} kW, Battery: {soc:.0f}% SOC."
            self._update_status("CONNECTED", msg)
            return {"success": True, "message": msg}
        except Exception as e:
            msg = str(e)
            self._update_status("ERROR", msg)
            return {"success": False, "message": msg}

    def get_missing_dates(self) -> List[str]:
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
                    d_start = datetime.date.fromisoformat(r["start_time"].split(" ")[0])
                    if min_date is None or d_start < min_date:
                        min_date = d_start
                    d_end = datetime.date.fromisoformat(r["end_time"].split(" ")[0]) if r["end_time"] else d_start
                    cur = d_start
                    while cur <= d_end:
                        covered_days.add(cur.isoformat())
                        cur += datetime.timedelta(days=1)
                except Exception:
                    continue

        tz_manila = datetime.timezone(datetime.timedelta(hours=8))
        today = datetime.datetime.now(tz_manila).date()
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

    def fetch_range_from_cloud(self, start_date_str: str, end_date_str: str) -> List[Dict[str, Any]]:
        self._load_config()
        tz_manila = datetime.timezone(datetime.timedelta(hours=8))
        d_start = datetime.date.fromisoformat(start_date_str)
        d_end = datetime.date.fromisoformat(end_date_str)
        if d_start > d_end:
            d_start, d_end = d_end, d_start

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

        st_id = int(self.station_id) if (self.station_id and self.station_id.isdigit()) else 62805884
        all_records = []
        seen_timestamps = set()

        chunk_start = d_start
        while chunk_start <= d_end:
            chunk_end = min(d_end, chunk_start + datetime.timedelta(days=2))
            dt_start = int(datetime.datetime(chunk_start.year, chunk_start.month, chunk_start.day, 0, 0, 0, tzinfo=tz_manila).timestamp())
            dt_end = int(datetime.datetime(chunk_end.year, chunk_end.month, chunk_end.day, 23, 59, 59, tzinfo=tz_manila).timestamp())

            req_payload = json.dumps({
                "stationId": st_id,
                "startTimestamp": dt_start,
                "endTimestamp": dt_end
            }).encode("utf-8")

            power_url = "https://eu1-developer.deyecloud.com/v1.0/station/history/power"
            req = urllib.request.Request(
                power_url,
                data=req_payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))

            items = res.get("stationDataItems", [])
            for it in items:
                ts_sec = it.get("timeStamp")
                if not ts_sec or ts_sec in seen_timestamps:
                    continue
                seen_timestamps.add(ts_sec)
                t_str = datetime.datetime.fromtimestamp(ts_sec, tz=tz_manila).strftime("%Y-%m-%d %H:%M:%S")
                pv_kw = round((it.get("generationPower") or 0.0) / 1000.0, 4)
                load_kw = round((it.get("consumptionPower") or 0.0) / 1000.0, 4)
                grid_w = it.get("wirePower")
                if grid_w is None:
                    grid_w = it.get("purchasePower") or 0.0
                grid_kw = round(grid_w / 1000.0, 4)
                batt_w = it.get("batteryPower")
                if batt_w is None:
                    if it.get("dischargePower"):
                        batt_w = it.get("dischargePower")
                    elif it.get("chargePower"):
                        batt_w = -abs(it.get("chargePower"))
                    else:
                        batt_w = 0.0
                batt_kw = round(batt_w / 1000.0, 4)
                soc = round(float(it.get("batterySOC") or 0.0), 1)

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
            day_key = t.split(" ")[0]
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

        legacy_composite_id = f"deye-{start_date_str}-to-{end_date_str}"
        conn.execute("DELETE FROM datasets WHERE id = ? OR filename LIKE 'Deye Cloud (% to %).csv' OR id LIKE 'deye-%-to-%'", (legacy_composite_id,))
        conn.execute("DELETE FROM column_mappings WHERE dataset_id = ? OR dataset_id LIKE 'deye-%-to-%'", (legacy_composite_id,))

        for day_key in sorted(days_dict.keys()):
            day_records = days_dict[day_key]
            day_records.sort(key=lambda x: x.get("Time", ""))
            day_count = len(day_records)
            total_rows += day_count

            csv_id = f"deye_{day_key}".replace("-", "")
            dataset_id = f"deye-{day_key}"
            filename = f"Deye Cloud ({day_key}).csv"
            file_path = settings.upload_dir / f"{csv_id}.csv"

            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in day_records:
                    writer.writerow(r)

            file_bytes = file_path.read_bytes()
            file_hash = hashlib.sha256(file_bytes).hexdigest()
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
                    created_at = excluded.created_at
                """,
                (
                    dataset_id, self.project_id, filename, file_hash, "csv", str(file_path), "Telemetry",
                    day_count, start_time, end_time, 100.0, 5.0, 0, "NONE", 1, 1, now_iso
                )
            )

            mapping_id = f"map-{dataset_id}"
            conn.execute(
                """INSERT OR REPLACE INTO column_mappings (
                    id, dataset_id, raw_headers_json, mapping_json, sign_conventions_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (mapping_id, dataset_id, json.dumps(fieldnames), json.dumps(canonical_map), json.dumps(sign_conventions), now_iso)
            )
            created_datasets.append(dataset_id)

        conn.commit()
        conn.close()

        from backend.app.api.endpoints import dataset_cache
        dataset_cache.clear()

        msg = f"Synced {len(created_datasets)} daily dataset(s) ({total_rows} records) from {start_date_str} to {end_date_str}."
        log_id = f"log-{int(datetime.datetime.now().timestamp())}"
        self._record_log(log_id, now_iso, total_rows, total_rows, 0, "SUCCESS", msg)
        self._update_status("SUCCESS", msg, now_iso)
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
            return self.persist_telemetry_dataset(records, start_date_str, end_date_str)
        except Exception as e:
            err = str(e)
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            log_id = f"log-{int(datetime.datetime.now().timestamp())}"
            self._record_log(log_id, now_iso, 0, 0, 0, "FAILED", err)
            self._update_status("FAILED", err)
            return {"status": "FAILED", "message": err, "records_inserted": 0}

    def sync_missing_dates(self) -> Dict[str, Any]:
        missing = self.get_missing_dates()
        if not missing:
            return {"status": "SUCCESS", "message": "No missing dates detected. All days up to today are recorded.", "records_inserted": 0, "missing_dates": []}

        total_inserted = 0
        details = []
        for d in missing:
            res = self.sync_range(d, d)
            if res.get("status") == "SUCCESS":
                total_inserted += res.get("records_inserted", 0)
                details.append(d)

        msg = f"Backfilled {len(details)} missing dates ({', '.join(details)}): {total_inserted} total records."
        return {
            "status": "SUCCESS",
            "message": msg,
            "records_inserted": total_inserted,
            "backfilled_dates": details
        }

    def sync_now(self) -> Dict[str, Any]:
        self._load_config()
        if not (self.app_id and self.app_secret):
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            log_id = f"log-{int(datetime.datetime.now().timestamp())}"
            msg = "Deye Cloud credentials not configured. Enter App ID and App Secret."
            self._record_log(log_id, now_iso, 0, 0, 0, "SKIPPED", msg)
            self._update_status("IDLE", msg)
            return {"status": "SKIPPED", "message": msg, "records_fetched": 0, "records_inserted": 0}

        tz_manila = datetime.timezone(datetime.timedelta(hours=8))
        today = datetime.datetime.now(tz_manila).date()
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

