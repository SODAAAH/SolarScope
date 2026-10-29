import os
import shutil
import uuid
from pathlib import Path
from backend.app.config import settings

def save_uploaded_file(source_filename: str, file_bytes: bytes) -> tuple[str, Path]:
    file_id = str(uuid.uuid4())
    suffix = Path(source_filename).suffix.lower()
    target_filename = f"{file_id}{suffix}"
    target_path = settings.upload_dir / target_filename
    with open(target_path, "wb") as f:
        f.write(file_bytes)
    return file_id, target_path

def get_file_path(filename: str) -> Path:
    direct = settings.upload_dir / filename
    if direct.exists():
        return direct
    sample = settings.sample_dir / filename
    if sample.exists():
        return sample
    return direct

def delete_file(filepath: str | Path) -> bool:
    path = Path(filepath)
    if path.exists():
        try:
            path.unlink()
            return True
        except Exception:
            return False
    return False
