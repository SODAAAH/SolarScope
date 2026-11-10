import os
import sqlite3
import json
import datetime
from pathlib import Path
from backend.app.config import settings

def get_db_path() -> Path:
    if os.environ.get("VERCEL"):
        db_dir = Path("/tmp") / "solarscope"
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "solarscope.db"
    return settings.base_dir / "solarscope.db"

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()), timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(hydrate: bool = True):
    if hydrate:
        try:
            from backend.app.storage.blob_sync import ensure_hydrated
            ensure_hydrated(force=False)
        except Exception:
            pass
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
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
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dataset_conflicts (
        id TEXT PRIMARY KEY,
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
        pv_capacity_kwp REAL DEFAULT 6.2,
        num_modules INTEGER DEFAULT 10,
        module_wattage REAL DEFAULT 620.0,
        panel_model TEXT DEFAULT 'Canadian Solar',
        panel_tech TEXT DEFAULT 'N-Type TOPCon bifacial',
        inverter_model TEXT DEFAULT 'SUN-6K-SG06LP1-EU-CM2',
        inverter_power_kw REAL DEFAULT 6.0,
        inverter_serial TEXT DEFAULT '2604282202',
        inverter_max_apparent_va REAL DEFAULT 6600.0,
        inverter_max_battery_current_a REAL DEFAULT 135.0,
        mppt_voltage_min_v REAL DEFAULT 150.0,
        mppt_voltage_max_v REAL DEFAULT 425.0,
        pv_voltage_max_v REAL DEFAULT 500.0,
        mppt_max_current_a REAL DEFAULT 18.0,
        logger_serial TEXT DEFAULT '1251892903',
        logger_firmware TEXT DEFAULT 'MW4_32_5407_SS_04_00.00.00.13',
        logger_interval_min INTEGER DEFAULT 5,
        battery_model TEXT DEFAULT 'MENRED ESS',
        battery_chemistry TEXT DEFAULT 'LFP',
        battery_voltage REAL DEFAULT 51.2,
        battery_ah REAL DEFAULT 314.0,
        battery_capacity_kwh REAL DEFAULT 16.08,
        usable_capacity_kwh REAL DEFAULT 12.86,
        reserve_soc REAL DEFAULT 20.0,
        bms_max_charge_a REAL DEFAULT 100.0,
        bms_max_discharge_a REAL DEFAULT 100.0,
        max_charge_kw REAL DEFAULT 5.12,
        max_discharge_kw REAL DEFAULT 5.12,
        battery_efficiency REAL DEFAULT 0.95,
        import_tariff REAL DEFAULT 11.50,
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
    CREATE TABLE IF NOT EXISTS tei_billing_profiles (
        id TEXT PRIMARY KEY,
        project_id TEXT UNIQUE NOT NULL,
        customer_class TEXT DEFAULT 'Residential',
        billing_cycle_day INTEGER DEFAULT 18,
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
    CREATE TABLE IF NOT EXISTS deye_cloud_configs (
        id TEXT PRIMARY KEY,
        project_id TEXT UNIQUE NOT NULL,
        station_id TEXT DEFAULT '',
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
        query_hash TEXT UNIQUE NOT NULL,
        query_text TEXT NOT NULL,
        response_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS deye_live_cache (
        cache_key TEXT PRIMARY KEY,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    cursor.execute("PRAGMA table_info(datasets)")
    cols = [row["name"] for row in cursor.fetchall()]
    if "file_hash" not in cols:
        cursor.execute("ALTER TABLE datasets ADD COLUMN file_hash TEXT")
    if "file_format" not in cols:
        cursor.execute("ALTER TABLE datasets ADD COLUMN file_format TEXT")
    if "sampling_interval_median_min" not in cols:
        cursor.execute("ALTER TABLE datasets ADD COLUMN sampling_interval_median_min REAL DEFAULT 5.0")
    if "gap_count" not in cols:
        cursor.execute("ALTER TABLE datasets ADD COLUMN gap_count INTEGER DEFAULT 0")
    if "conflict_status" not in cols:
        cursor.execute("ALTER TABLE datasets ADD COLUMN conflict_status TEXT DEFAULT 'NONE'")
    if "is_included" not in cols:
        cursor.execute("ALTER TABLE datasets ADD COLUMN is_included INTEGER DEFAULT 1")

    cursor.execute("PRAGMA table_info(system_settings)")
    sys_cols = [row["name"] for row in cursor.fetchall()]
    add_sys_cols = {
        "panel_model": "TEXT DEFAULT 'Canadian Solar'",
        "panel_tech": "TEXT DEFAULT 'N-Type TOPCon bifacial'",
        "inverter_model": "TEXT DEFAULT 'SUN-6K-SG06LP1-EU-CM2'",
        "inverter_serial": "TEXT DEFAULT '2604282202'",
        "inverter_max_apparent_va": "REAL DEFAULT 6600.0",
        "inverter_max_battery_current_a": "REAL DEFAULT 135.0",
        "mppt_voltage_min_v": "REAL DEFAULT 150.0",
        "mppt_voltage_max_v": "REAL DEFAULT 425.0",
        "pv_voltage_max_v": "REAL DEFAULT 500.0",
        "mppt_max_current_a": "REAL DEFAULT 18.0",
        "logger_serial": "TEXT DEFAULT '1251892903'",
        "logger_firmware": "TEXT DEFAULT 'MW4_32_5407_SS_04_00.00.00.13'",
        "logger_interval_min": "INTEGER DEFAULT 5",
        "battery_model": "TEXT DEFAULT 'MENRED ESS'",
        "battery_ah": "REAL DEFAULT 314.0",
        "bms_max_charge_a": "REAL DEFAULT 100.0",
        "bms_max_discharge_a": "REAL DEFAULT 100.0"
    }
    for col_name, col_def in add_sys_cols.items():
        if col_name not in sys_cols:
            cursor.execute(f"ALTER TABLE system_settings ADD COLUMN {col_name} {col_def}")

    cursor.execute("SELECT id FROM projects WHERE id = 'default'")
    if not cursor.fetchone():
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("default", "Default Solar Audit", "Standard local solar audit project", now, now)
        )
        cursor.execute(
            """INSERT INTO system_settings (
                id, project_id, pv_capacity_kwp, num_modules, module_wattage,
                panel_model, panel_tech, inverter_model, inverter_power_kw, inverter_serial,
                inverter_max_apparent_va, inverter_max_battery_current_a, mppt_voltage_min_v, mppt_voltage_max_v,
                pv_voltage_max_v, mppt_max_current_a, logger_serial, logger_firmware, logger_interval_min,
                battery_model, battery_chemistry, battery_voltage, battery_ah, battery_capacity_kwh,
                usable_capacity_kwh, reserve_soc, bms_max_charge_a, bms_max_discharge_a, max_charge_kw, max_discharge_kw,
                battery_efficiency, import_tariff, export_tariff, currency, timezone, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "settings-default", "default", 6.2, 10, 620.0,
                "Canadian Solar", "N-Type TOPCon bifacial", "SUN-6K-SG06LP1-EU-CM2", 6.0, "2604282202",
                6600.0, 135.0, 150.0, 425.0,
                500.0, 18.0, "1251892903", "MW4_32_5407_SS_04_00.00.00.13", 5,
                "MENRED ESS", "LFP", 51.2, 314.0, 16.08,
                12.86, 20.0, 100.0, 100.0, 5.12, 5.12,
                0.95, 11.50, 0.0, "PHP", "Asia/Manila", now
            )
        )

    cursor.execute("SELECT id FROM deye_cloud_configs WHERE project_id = 'default'")
    if not cursor.fetchone():
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute(
            """INSERT INTO deye_cloud_configs (
                id, project_id, station_id, app_id, app_secret, username, password_encrypted,
                auto_sync, sync_interval_min, sync_status, sync_message, reconciliation_policy, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "deye-default", "default", "", "", "", "", "",
                0, 5, "IDLE", "Not connected", "MERGE", now_iso
            )
        )

    cursor.execute("SELECT id FROM tei_rate_schedules WHERE is_active = 1")
    if not cursor.fetchone():
        from backend.app.billing.tariff_defaults import get_default_october_2026_schedule
        default_sched = get_default_october_2026_schedule()
        comps_json = json.dumps([c.model_dump() for c in default_sched.components])
        cursor.execute(
            """INSERT INTO tei_rate_schedules
               (id, effective_month, customer_class, publication_date, source_url, document_hash, verification_status, is_active, schedule_data_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
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
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute(
            """INSERT INTO tei_billing_profiles
               (id, project_id, customer_class, billing_cycle_day, cycle_start_date, cycle_end_date, connection_type,
                is_lifeline_eligible, is_senior_eligible, is_prompt_payment_eligible, previous_unpaid_balance,
                payments_received, forecast_method, updated_at)
               VALUES ('profile-default', 'default', 'Residential', 18, '2026-10-18', '2026-11-18', 'behind_meter',
                       0, 0, 0, 0.0, 0.0, '7day', ?)""",
            (now_iso,)
        )

    conn.commit()
    conn.close()
