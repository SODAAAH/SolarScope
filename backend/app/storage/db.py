import os
import re
import sqlite3
import json
import datetime
import threading
from pathlib import Path
from typing import Any, Optional, List, Dict

from backend.app.config import settings, resolve_database_url, is_postgres_url, is_hosted_mode

_pg_pool = None
_pg_pool_lock = threading.Lock()
_init_lock = threading.Lock()
_initialized = False

def is_postgres() -> bool:
    return is_postgres_url(resolve_database_url())

def get_db_path() -> Path:
    db_url = resolve_database_url()
    if db_url.startswith("sqlite:///"):
        raw_path = db_url[len("sqlite:///"):]
        p = Path(raw_path)
        if not p.is_absolute():
            if os.environ.get("VERCEL"):
                db_dir = Path("/tmp") / "solarscope"
                db_dir.mkdir(parents=True, exist_ok=True)
                return db_dir / p.name
            return (settings.base_dir.parent / p).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    if os.environ.get("VERCEL"):
        db_dir = Path("/tmp") / "solarscope"
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "solarscope.db"
    return settings.base_dir / "solarscope.db"

def _translate_qmarks_to_percent(sql: str) -> str:
    out: List[str] = []
    in_single = False
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":
            out.append(ch)
            if in_single and i + 1 < n and sql[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            in_single = not in_single
        elif ch == "?" and not in_single:
            out.append("%s")
        else:
            out.append(ch)
        i += 1
    return "".join(out)

class DictRow(dict):
    def keys(self):
        return super().keys()

class PgCursorWrapper:
    def __init__(self, cur):
        self._cur = cur

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    def _wrap_row(self, row: Any) -> Optional[DictRow]:
        if row is None:
            return None
        if isinstance(row, dict):
            return DictRow(row)
        desc = self._cur.description
        if not desc:
            return DictRow()
        return DictRow({col.name: row[idx] for idx, col in enumerate(desc)})

    def fetchone(self) -> Optional[DictRow]:
        row = self._cur.fetchone()
        return self._wrap_row(row)

    def fetchall(self) -> List[DictRow]:
        rows = self._cur.fetchall()
        return [r for r in (self._wrap_row(x) for x in rows) if r is not None]

    def execute(self, sql: str, params: Any = None):
        translated = _translate_qmarks_to_percent(sql)
        if params is None:
            self._cur.execute(translated)
        else:
            self._cur.execute(translated, params)
        return self

    def close(self) -> None:
        try:
            self._cur.close()
        except Exception:
            pass

class PgConnectionWrapper:
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._closed = False

    def cursor(self) -> PgCursorWrapper:
        return PgCursorWrapper(self._conn.cursor())

    def execute(self, sql: str, params: Any = None) -> PgCursorWrapper:
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if not self._conn.closed:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                self._pool.putconn(self._conn)
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass

def _get_pg_pool():
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    with _pg_pool_lock:
        if _pg_pool is not None:
            return _pg_pool
        import psycopg
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        conninfo = resolve_database_url()
        try:
            _pg_pool = ConnectionPool(
                conninfo=conninfo,
                min_size=1,
                max_size=10,
                kwargs={"row_factory": dict_row},
                open=True,
            )
            return _pg_pool
        except Exception:
            _pg_pool = None
            raise

class SimplePgPool:
    def __init__(self, conninfo: str):
        self._conninfo = conninfo

    def getconn(self):
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(self._conninfo, row_factory=dict_row)

    def putconn(self, conn):
        try:
            conn.close()
        except Exception:
            pass

_simple_pg_pool: Optional[SimplePgPool] = None

def get_connection():
    if is_postgres():
        global _simple_pg_pool
        try:
            pool = _get_pg_pool()
            conn = pool.getconn()
            return PgConnectionWrapper(conn, pool)
        except ImportError:
            if _simple_pg_pool is None:
                _simple_pg_pool = SimplePgPool(resolve_database_url())
            return PgConnectionWrapper(_simple_pg_pool.getconn(), _simple_pg_pool)

    conn = sqlite3.connect(str(get_db_path()), timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        if not os.environ.get("VERCEL"):
            conn.execute("PRAGMA journal_mode = WAL")
    except Exception:
        pass
    return conn

def _ensure_column(cursor, table_name: str, col_name: str, col_def: str, pg: bool) -> None:
    if pg:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
    else:
        cursor.execute(f"PRAGMA table_info({table_name})")
        cols = [row["name"] for row in cursor.fetchall()]
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")

def init_db(hydrate: bool = True):
    global _initialized
    pg = is_postgres()
    if hydrate and not pg:
        try:
            from backend.app.storage.blob_sync import ensure_hydrated
            ensure_hydrated(force=False)
        except Exception:
            pass

    with _init_lock:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token_hash TEXT UNIQUE NOT NULL,
            csrf_token TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            user_agent TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            owner_user_id TEXT DEFAULT 'user-local',
            installation_type TEXT DEFAULT 'residential',
            is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_hash TEXT,
            file_format TEXT,
            filepath TEXT NOT NULL,
            sheet_name TEXT,
            total_rows INTEGER DEFAULT 0,
            start_time TEXT,
            end_time TEXT,
            quality_score REAL DEFAULT 0.0,
            sampling_interval_median_min REAL DEFAULT 5.0,
            gap_count INTEGER DEFAULT 0,
            conflict_status TEXT DEFAULT 'NONE',
            is_active INTEGER DEFAULT 1,
            is_included INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)

        blob_col_type = "BYTEA" if pg else "BLOB"
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS dataset_files (
            id TEXT PRIMARY KEY,
            dataset_id TEXT UNIQUE NOT NULL,
            project_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            file_bytes {blob_col_type} NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dataset_conflicts (
            id TEXT PRIMARY KEY,
            project_id TEXT DEFAULT 'default',
            dataset_a_id TEXT NOT NULL,
            dataset_b_id TEXT NOT NULL,
            overlap_start TEXT NOT NULL,
            overlap_end TEXT NOT NULL,
            conflict_count INTEGER DEFAULT 0,
            resolution_policy TEXT DEFAULT 'KEEP_EXISTING',
            resolved INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS column_mappings (
            id TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL UNIQUE,
            raw_headers_json TEXT NOT NULL,
            mapping_json TEXT NOT NULL,
            sign_conventions_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL UNIQUE,
            station_name TEXT DEFAULT '',
            location_name TEXT DEFAULT '',
            latitude REAL DEFAULT 0.0,
            longitude REAL DEFAULT 0.0,
            pv_capacity_kwp REAL DEFAULT 0.0,
            num_modules INTEGER DEFAULT 0,
            module_wattage REAL DEFAULT 0.0,
            panel_model TEXT DEFAULT '',
            panel_tech TEXT DEFAULT '',
            inverter_model TEXT DEFAULT '',
            inverter_power_kw REAL DEFAULT 0.0,
            inverter_serial TEXT DEFAULT '',
            inverter_max_apparent_va REAL DEFAULT 0.0,
            inverter_max_battery_current_a REAL DEFAULT 0.0,
            mppt_voltage_min_v REAL DEFAULT 0.0,
            mppt_voltage_max_v REAL DEFAULT 0.0,
            pv_voltage_max_v REAL DEFAULT 0.0,
            mppt_max_current_a REAL DEFAULT 0.0,
            logger_serial TEXT DEFAULT '',
            logger_firmware TEXT DEFAULT '',
            logger_interval_min INTEGER DEFAULT 5,
            battery_model TEXT DEFAULT '',
            battery_chemistry TEXT DEFAULT 'LFP',
            battery_voltage REAL DEFAULT 0.0,
            battery_ah REAL DEFAULT 0.0,
            battery_capacity_kwh REAL DEFAULT 0.0,
            usable_capacity_kwh REAL DEFAULT 0.0,
            reserve_soc REAL DEFAULT 20.0,
            bms_max_charge_a REAL DEFAULT 0.0,
            bms_max_discharge_a REAL DEFAULT 0.0,
            max_charge_kw REAL DEFAULT 0.0,
            max_discharge_kw REAL DEFAULT 0.0,
            battery_efficiency REAL DEFAULT 0.95,
            import_tariff REAL DEFAULT 0.0,
            export_tariff REAL DEFAULT 0.0,
            currency TEXT DEFAULT 'PHP',
            timezone TEXT DEFAULT 'Asia/Manila',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_reports (
            id TEXT PRIMARY KEY,
            project_id TEXT DEFAULT 'default',
            dataset_id TEXT NOT NULL,
            report_type TEXT NOT NULL,
            filepath TEXT NOT NULL,
            filesize INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tei_rate_schedules (
            id TEXT PRIMARY KEY,
            project_id TEXT DEFAULT 'global',
            effective_month TEXT NOT NULL,
            customer_class TEXT NOT NULL DEFAULT 'Residential',
            publication_date TEXT,
            source_url TEXT,
            document_hash TEXT,
            verification_status TEXT DEFAULT 'verified',
            is_active INTEGER DEFAULT 1,
            schedule_data_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_rate_preferences (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            customer_class TEXT NOT NULL DEFAULT 'Residential',
            active_schedule_id TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(project_id, customer_class)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tei_billing_profiles (
            id TEXT PRIMARY KEY,
            project_id TEXT UNIQUE NOT NULL,
            customer_class TEXT DEFAULT 'Residential',
            billing_cycle_day INTEGER DEFAULT 25,
            billing_month TEXT,
            cycle_start_date TEXT,
            cycle_end_date TEXT,
            prev_meter_reading REAL,
            latest_meter_reading REAL,
            meter_reading_date TEXT,
            connection_type TEXT DEFAULT 'behind_meter',
            is_lifeline_eligible INTEGER DEFAULT 0,
            is_senior_eligible INTEGER DEFAULT 0,
            is_prompt_payment_eligible INTEGER DEFAULT 0,
            previous_unpaid_balance REAL DEFAULT 0.0,
            payments_received REAL DEFAULT 0.0,
            forecast_method TEXT DEFAULT '7day',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tei_historical_bills (
            id TEXT PRIMARY KEY,
            project_id TEXT DEFAULT 'default',
            billing_period_start TEXT NOT NULL,
            billing_period_end TEXT NOT NULL,
            billed_kwh REAL NOT NULL,
            actual_amount_due REAL NOT NULL,
            predicted_amount_due REAL,
            notes TEXT,
            created_at TEXT NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tei_monthly_estimates (
            id TEXT PRIMARY KEY,
            project_id TEXT DEFAULT 'default',
            billing_month TEXT NOT NULL,
            billing_cycle_start TEXT NOT NULL,
            billing_cycle_end TEXT NOT NULL,
            customer_class TEXT NOT NULL,
            rate_effective_month TEXT NOT NULL,
            generation_charge REAL NOT NULL,
            actual_imported_kwh REAL NOT NULL,
            projected_kwh REAL NOT NULL,
            lower_estimate_amount REAL NOT NULL,
            expected_estimate_amount REAL NOT NULL,
            higher_estimate_amount REAL NOT NULL,
            solar_savings_pesos REAL NOT NULL,
            savings_percentage REAL NOT NULL,
            effective_average_rate REAL NOT NULL,
            is_completed_cycle INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            UNIQUE(project_id, billing_month)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tei_rate_check_state (
            id TEXT PRIMARY KEY,
            project_id TEXT DEFAULT 'global',
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            checked_at TEXT,
            rate_change_alert_json TEXT,
            updated_at TEXT NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS deye_cloud_configs (
            id TEXT PRIMARY KEY,
            project_id TEXT UNIQUE NOT NULL,
            station_id TEXT DEFAULT '',
            data_center TEXT DEFAULT 'eu',
            app_id TEXT DEFAULT '',
            app_secret TEXT DEFAULT '',
            username TEXT DEFAULT '',
            password_encrypted TEXT DEFAULT '',
            auto_sync INTEGER DEFAULT 0,
            sync_interval_min INTEGER DEFAULT 5,
            last_sync_time TEXT,
            sync_status TEXT DEFAULT 'IDLE',
            sync_message TEXT,
            reconciliation_policy TEXT DEFAULT 'MERGE',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS deye_sync_logs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            sync_time TEXT NOT NULL,
            records_fetched INTEGER DEFAULT 0,
            records_inserted INTEGER DEFAULT 0,
            records_skipped INTEGER DEFAULT 0,
            status TEXT NOT NULL,
            error_message TEXT
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_cache (
            id TEXT PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            date_str TEXT NOT NULL,
            hourly_data_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyst_cache (
            id TEXT PRIMARY KEY,
            project_id TEXT DEFAULT 'default',
            query_hash TEXT UNIQUE NOT NULL,
            query_text TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS deye_live_cache (
            cache_key TEXT PRIMARY KEY,
            project_id TEXT DEFAULT 'default',
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)

        _ensure_column(cursor, "projects", "owner_user_id", "TEXT DEFAULT 'user-local'", pg)
        _ensure_column(cursor, "projects", "installation_type", "TEXT DEFAULT 'residential'", pg)
        _ensure_column(cursor, "projects", "is_default", "INTEGER DEFAULT 0", pg)

        _ensure_column(cursor, "datasets", "file_hash", "TEXT", pg)
        _ensure_column(cursor, "datasets", "file_format", "TEXT", pg)
        _ensure_column(cursor, "datasets", "sampling_interval_median_min", "REAL DEFAULT 5.0", pg)
        _ensure_column(cursor, "datasets", "gap_count", "INTEGER DEFAULT 0", pg)
        _ensure_column(cursor, "datasets", "conflict_status", "TEXT DEFAULT 'NONE'", pg)
        _ensure_column(cursor, "datasets", "is_included", "INTEGER DEFAULT 1", pg)

        _ensure_column(cursor, "dataset_conflicts", "project_id", "TEXT DEFAULT 'default'", pg)
        _ensure_column(cursor, "audit_reports", "project_id", "TEXT DEFAULT 'default'", pg)
        _ensure_column(cursor, "tei_rate_schedules", "project_id", "TEXT DEFAULT 'global'", pg)
        _ensure_column(cursor, "tei_rate_check_state", "project_id", "TEXT DEFAULT 'global'", pg)
        _ensure_column(cursor, "deye_cloud_configs", "data_center", "TEXT DEFAULT 'eu'", pg)
        _ensure_column(cursor, "analyst_cache", "project_id", "TEXT DEFAULT 'default'", pg)
        _ensure_column(cursor, "deye_live_cache", "project_id", "TEXT DEFAULT 'default'", pg)

        add_sys_cols = {
            "station_name": "TEXT DEFAULT ''",
            "location_name": "TEXT DEFAULT ''",
            "latitude": "REAL DEFAULT 0.0",
            "longitude": "REAL DEFAULT 0.0",
            "panel_model": "TEXT DEFAULT ''",
            "panel_tech": "TEXT DEFAULT ''",
            "inverter_model": "TEXT DEFAULT ''",
            "inverter_serial": "TEXT DEFAULT ''",
            "inverter_max_apparent_va": "REAL DEFAULT 0.0",
            "inverter_max_battery_current_a": "REAL DEFAULT 0.0",
            "mppt_voltage_min_v": "REAL DEFAULT 0.0",
            "mppt_voltage_max_v": "REAL DEFAULT 0.0",
            "pv_voltage_max_v": "REAL DEFAULT 0.0",
            "mppt_max_current_a": "REAL DEFAULT 0.0",
            "logger_serial": "TEXT DEFAULT ''",
            "logger_firmware": "TEXT DEFAULT ''",
            "logger_interval_min": "INTEGER DEFAULT 5",
            "battery_model": "TEXT DEFAULT ''",
            "battery_ah": "REAL DEFAULT 0.0",
            "bms_max_charge_a": "REAL DEFAULT 0.0",
            "bms_max_discharge_a": "REAL DEFAULT 0.0",
        }
        for col_name, col_def in add_sys_cols.items():
            _ensure_column(cursor, "system_settings", col_name, col_def, pg)

        _ensure_column(cursor, "tei_billing_profiles", "billing_month", "TEXT", pg)

        index_ddls = [
            "CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_user_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_datasets_project ON datasets(project_id, is_included, start_time)",
            "CREATE INDEX IF NOT EXISTS idx_dataset_files_project ON dataset_files(project_id, dataset_id)",
            "CREATE INDEX IF NOT EXISTS idx_reports_project ON audit_reports(project_id, dataset_id)",
            "CREATE INDEX IF NOT EXISTS idx_hist_bills_project ON tei_historical_bills(project_id, billing_period_start)",
            "CREATE INDEX IF NOT EXISTS idx_monthly_est_project ON tei_monthly_estimates(project_id, billing_month)",
            "CREATE INDEX IF NOT EXISTS idx_deye_logs_project ON deye_sync_logs(project_id, sync_time)",
            "CREATE INDEX IF NOT EXISTS idx_rate_sched_scope ON tei_rate_schedules(project_id, customer_class, effective_month)",
        ]
        for ddl in index_ddls:
            cursor.execute(ddl)

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("SELECT id FROM users WHERE id = 'user-local'")
        if not cursor.fetchone():
            cursor.execute(
                """INSERT INTO users (id, email, display_name, password_hash, role, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("user-local", "local@solarscope.device", "Local Household", "local-only", "owner", 1, now_iso, now_iso)
            )

        cursor.execute("SELECT id, owner_user_id FROM projects WHERE id = 'default'")
        default_proj = cursor.fetchone()
        if not default_proj:
            cursor.execute(
                """INSERT INTO projects (id, name, description, owner_user_id, installation_type, is_default, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("default", "Default Solar Audit", "Standard local solar audit project", "user-local", "residential", 1, now_iso, now_iso)
            )
            cursor.execute(
                """INSERT INTO system_settings (
                    id, project_id, station_name, location_name, latitude, longitude,
                    pv_capacity_kwp, num_modules, module_wattage,
                    panel_model, panel_tech, inverter_model, inverter_power_kw, inverter_serial,
                    inverter_max_apparent_va, inverter_max_battery_current_a, mppt_voltage_min_v, mppt_voltage_max_v,
                    pv_voltage_max_v, mppt_max_current_a, logger_serial, logger_firmware, logger_interval_min,
                    battery_model, battery_chemistry, battery_voltage, battery_ah, battery_capacity_kwh,
                    usable_capacity_kwh, reserve_soc, bms_max_charge_a, bms_max_discharge_a, max_charge_kw, max_discharge_kw,
                    battery_efficiency, import_tariff, export_tariff, currency, timezone, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "settings-default", "default", "", "", 0.0, 0.0,
                    0.0, 0, 0.0,
                    "", "", "", 0.0, "",
                    0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, "", "", 5,
                    "", "LFP", 0.0, 0.0, 0.0,
                    0.0, 20.0, 0.0, 0.0, 0.0, 0.0,
                    0.95, 0.0, 0.0, "PHP", "Asia/Manila", now_iso
                )
            )
        elif not dict(default_proj).get("owner_user_id"):
            cursor.execute("UPDATE projects SET owner_user_id = 'user-local' WHERE id = 'default'")

        cursor.execute("SELECT id FROM deye_cloud_configs WHERE project_id = 'default'")
        if not cursor.fetchone():
            cursor.execute(
                """INSERT INTO deye_cloud_configs (
                    id, project_id, station_id, data_center, app_id, app_secret, username, password_encrypted,
                    auto_sync, sync_interval_min, sync_status, sync_message, reconciliation_policy, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "deye-default", "default", "", "eu", "", "", "", "",
                    0, 5, "IDLE", "Not connected", "MERGE", now_iso
                )
            )

        cursor.execute("SELECT id FROM tei_rate_schedules WHERE is_active = 1")
        if not cursor.fetchone():
            from backend.app.billing.tariff_defaults import get_default_tei_schedule
            default_sched = get_default_tei_schedule()
            comps_json = json.dumps([c.model_dump() for c in default_sched.components])
            cursor.execute(
                """INSERT INTO tei_rate_schedules
                   (id, project_id, effective_month, customer_class, publication_date, source_url, document_hash, verification_status, is_active, schedule_data_json, created_at)
                   VALUES (?, 'global', ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    default_sched.id,
                    default_sched.effective_month,
                    default_sched.customer_class,
                    default_sched.publication_date,
                    default_sched.source_url,
                    default_sched.document_hash,
                    default_sched.verification_status,
                    comps_json,
                    default_sched.created_at
                )
            )

        cursor.execute("SELECT id FROM tei_billing_profiles WHERE project_id = 'default'")
        if not cursor.fetchone():
            from backend.app.billing.billing_profile import compute_cycle_dates
            start_dt, end_dt = compute_cycle_dates(25)
            cursor.execute(
                """INSERT INTO tei_billing_profiles
                   (id, project_id, customer_class, billing_cycle_day, cycle_start_date, cycle_end_date, connection_type,
                    is_lifeline_eligible, is_senior_eligible, is_prompt_payment_eligible, previous_unpaid_balance,
                    payments_received, forecast_method, updated_at)
                   VALUES ('profile-default', 'default', 'Residential', 25, ?, ?, 'behind_meter',
                           0, 0, 0, 0.0, 0.0, '7day', ?)""",
                (start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"), now_iso)
            )

        try:
            from backend.app.security.crypto import encrypt_secret, is_encrypted_secret
            cfg_rows = cursor.execute("SELECT id, app_secret, password_encrypted FROM deye_cloud_configs").fetchall()
            for cfg in cfg_rows:
                raw_secret = (cfg["app_secret"] or "").strip()
                raw_pwd = (cfg["password_encrypted"] or "").strip()
                updates: Dict[str, str] = {}
                if raw_secret and not is_encrypted_secret(raw_secret):
                    updates["app_secret"] = encrypt_secret(raw_secret)
                if raw_pwd and not is_encrypted_secret(raw_pwd):
                    updates["password_encrypted"] = encrypt_secret(raw_pwd)
                if updates:
                    if "app_secret" in updates and "password_encrypted" in updates:
                        cursor.execute(
                            "UPDATE deye_cloud_configs SET app_secret = ?, password_encrypted = ? WHERE id = ?",
                            (updates["app_secret"], updates["password_encrypted"], cfg["id"])
                        )
                    elif "app_secret" in updates:
                        cursor.execute(
                            "UPDATE deye_cloud_configs SET app_secret = ? WHERE id = ?",
                            (updates["app_secret"], cfg["id"])
                        )
                    elif "password_encrypted" in updates:
                        cursor.execute(
                            "UPDATE deye_cloud_configs SET password_encrypted = ? WHERE id = ?",
                            (updates["password_encrypted"], cfg["id"])
                        )
        except Exception:
            pass

        conn.commit()
        conn.close()
        _initialized = True

def create_project_for_user(
    user_id: str,
    name: str,
    description: str = "",
    installation_type: str = "residential",
    is_default: bool = False,
    conn: Any = None,
) -> Dict[str, Any]:
    import uuid
    from backend.app.billing.billing_profile import compute_cycle_dates

    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    project_id = f"proj-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO projects (id, name, description, owner_user_id, installation_type, is_default, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, name.strip() or "Primary Solar Array", description, user_id, installation_type, 1 if is_default else 0, now_iso, now_iso)
    )
    conn.execute(
        """INSERT INTO system_settings (
            id, project_id, station_name, location_name, latitude, longitude,
            pv_capacity_kwp, num_modules, module_wattage,
            panel_model, panel_tech, inverter_model, inverter_power_kw, inverter_serial,
            inverter_max_apparent_va, inverter_max_battery_current_a, mppt_voltage_min_v, mppt_voltage_max_v,
            pv_voltage_max_v, mppt_max_current_a, logger_serial, logger_firmware, logger_interval_min,
            battery_model, battery_chemistry, battery_voltage, battery_ah, battery_capacity_kwh,
            usable_capacity_kwh, reserve_soc, bms_max_charge_a, bms_max_discharge_a, max_charge_kw, max_discharge_kw,
            battery_efficiency, import_tariff, export_tariff, currency, timezone, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            f"settings-{project_id}", project_id, name.strip() or "", "", 0.0, 0.0,
            0.0, 0, 0.0,
            "", "", "", 0.0, "",
            0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, "", "", 5,
            "", "LFP", 0.0, 0.0, 0.0,
            0.0, 20.0, 0.0, 0.0, 0.0, 0.0,
            0.95, 0.0, 0.0, "PHP", "Asia/Manila", now_iso
        )
    )
    conn.execute(
        """INSERT INTO deye_cloud_configs (
            id, project_id, station_id, data_center, app_id, app_secret, username, password_encrypted,
            auto_sync, sync_interval_min, sync_status, sync_message, reconciliation_policy, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            f"deye-{project_id}", project_id, "", "eu", "", "", "", "",
            0, 5, "IDLE", "Not connected", "MERGE", now_iso
        )
    )
    start_dt, end_dt = compute_cycle_dates(25)
    conn.execute(
        """INSERT INTO tei_billing_profiles
           (id, project_id, customer_class, billing_cycle_day, cycle_start_date, cycle_end_date, connection_type,
            is_lifeline_eligible, is_senior_eligible, is_prompt_payment_eligible, previous_unpaid_balance,
            payments_received, forecast_method, updated_at)
           VALUES (?, ?, 'Residential', 25, ?, ?, 'behind_meter',
                   0, 0, 0, 0.0, 0.0, '7day', ?)""",
        (f"profile-{project_id}", project_id, start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"), now_iso)
    )
    if own_conn:
        conn.commit()
        conn.close()
    return {
        "id": project_id,
        "name": name.strip() or "Primary Solar Array",
        "description": description,
        "owner_user_id": user_id,
        "installation_type": installation_type,
        "is_default": is_default,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
