from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SolarScope"
    app_version: str = "1.0.0"
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_port: int = 5173
    database_url: str = "sqlite:///./solarscope.db"
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    upload_dir: Path = Path(__file__).resolve().parent.parent / "data" / "uploads"
    reports_dir: Path = Path(__file__).resolve().parent.parent / "data" / "reports"
    sample_dir: Path = Path(__file__).resolve().parent.parent / "data" / "sample"
    default_timezone: str = "Asia/Manila"
    default_currency: str = "PHP"
    gap_threshold_minutes: float = 30.0

settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.reports_dir.mkdir(parents=True, exist_ok=True)
settings.sample_dir.mkdir(parents=True, exist_ok=True)
