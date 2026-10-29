import sqlite3
import json
import datetime
from pathlib import Path
from backend.app.config import settings

def get_db_path() -> Path:
    return settings.base_dir / "solarscope.db"

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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
        pv_capacity_kwp REAL DEFAULT 5.0,
        num_modules INTEGER DEFAULT 10,
        module_wattage REAL DEFAULT 500.0,
        inverter_power_kw REAL DEFAULT 5.0,
        battery_chemistry TEXT DEFAULT 'LFP',
        battery_voltage REAL DEFAULT 51.2,
        battery_capacity_kwh REAL DEFAULT 15.0,
        usable_capacity_kwh REAL DEFAULT 11.25,
        reserve_soc REAL DEFAULT 25.0,
        max_charge_kw REAL DEFAULT 3.0,
        max_discharge_kw REAL DEFAULT 3.0,
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
                inverter_power_kw, battery_chemistry, battery_voltage, battery_capacity_kwh,
                usable_capacity_kwh, reserve_soc, max_charge_kw, max_discharge_kw,
                battery_efficiency, import_tariff, export_tariff, currency, timezone, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "settings-default", "default", 5.0, 10, 500.0,
                5.0, "LFP", 51.2, 15.0,
                11.25, 25.0, 3.0, 3.0,
                0.95, 11.50, 0.0, "PHP", "Asia/Manila", now
            )
        )

    conn.commit()
    conn.close()
