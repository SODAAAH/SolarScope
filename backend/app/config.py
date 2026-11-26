import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SolarScope"
    app_version: str = "1.3.0"
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_port: int = 5173
    database_url: str = "sqlite:///./solarscope.db"
    postgres_url: str = ""
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    upload_dir: Path = Path(__file__).resolve().parent.parent / "data" / "uploads"
    reports_dir: Path = Path(__file__).resolve().parent.parent / "data" / "reports"
    sample_dir: Path = Path(__file__).resolve().parent.parent / "data" / "sample"
    default_timezone: str = "Asia/Manila"
    default_currency: str = "PHP"
    gap_threshold_minutes: float = 30.0
    auth_mode: str = "auto"
    auth_required: bool = False
    session_ttl_hours: int = 168
    encryption_key: str = ""
    secret_key: str = ""
    allowed_origins: str = ""
    cookie_secure: str = "auto"

settings = Settings()

def resolve_database_url() -> str:
    for candidate in (
        os.environ.get("DATABASE_URL", ""),
        os.environ.get("POSTGRES_URL", ""),
        os.environ.get("POSTGRES_PRISMA_URL", ""),
        os.environ.get("NEON_DATABASE_URL", ""),
        settings.postgres_url,
        settings.database_url,
    ):
        val = (candidate or "").strip()
        if val:
            return val
    return "sqlite:///./solarscope.db"

def is_postgres_url(url: str) -> bool:
    low = (url or "").strip().lower()
    return low.startswith("postgres://") or low.startswith("postgresql://")

def is_hosted_mode() -> bool:
    mode = (os.environ.get("SOLARSCOPE_AUTH_MODE") or settings.auth_mode or "auto").strip().lower()
    if mode == "hosted":
        return True
    if mode == "local":
        return False
    if os.environ.get("SOLARSCOPE_AUTH_REQUIRED", "").strip() in ("1", "true", "TRUE", "yes"):
        return True
    if settings.auth_required:
        return True
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV") in ("production", "preview"):
        return True
    return False

def get_allowed_origins() -> List[str]:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    raw_extra = (os.environ.get("ALLOWED_ORIGINS") or settings.allowed_origins or "").strip()
    if raw_extra:
        for item in raw_extra.split(","):
            cleaned = item.strip().rstrip("/")
            if cleaned and cleaned not in origins:
                origins.append(cleaned)
    for env_host in (
        os.environ.get("VERCEL_URL", ""),
        os.environ.get("VERCEL_BRANCH_URL", ""),
        os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", ""),
    ):
        host = env_host.strip().rstrip("/")
        if host:
            origin = host if host.startswith("http") else f"https://{host}"
            if origin not in origins:
                origins.append(origin)
    return origins

if os.environ.get("VERCEL"):
    writable_base = Path("/tmp") / "solarscope"
    settings.data_dir = writable_base / "data"
    settings.upload_dir = writable_base / "data" / "uploads"
    settings.reports_dir = writable_base / "data" / "reports"
    settings.sample_dir = writable_base / "data" / "sample"

try:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    settings.sample_dir.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
