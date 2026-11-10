import os
from pathlib import Path
from typing import Optional
from backend.app.config import settings
from backend.app.storage.blob_sync import is_blob_enabled, persist_state

def extract_basename(raw_filepath: str | Path) -> str:
    s = str(raw_filepath).replace("\\", "/")
    return s.rsplit("/", 1)[-1]

def save_uploaded_file(source_filename: str, file_bytes: bytes) -> tuple[str, Path]:
    import uuid
    file_id = str(uuid.uuid4())
    suffix = Path(source_filename).suffix.lower()
    target_filename = f"{file_id}{suffix}"
    target_path = settings.upload_dir / target_filename
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    with open(target_path, "wb") as f:
        f.write(file_bytes)
    return file_id, target_path

def resolve_dataset_path(raw_filepath: Optional[str | Path]) -> Optional[Path]:
    if not raw_filepath:
        return None
    direct = Path(str(raw_filepath))
    if direct.exists():
        return direct
    basename = extract_basename(raw_filepath)
    if not basename:
        return None
    in_upload = settings.upload_dir / basename
    if in_upload.exists():
        return in_upload
    in_sample = settings.sample_dir / basename
    if in_sample.exists():
        return in_sample
    in_static_sample = settings.base_dir / "data" / "sample" / basename
    if in_static_sample.exists():
        return in_static_sample
    if is_blob_enabled():
        from backend.app.storage.blob_sync import ensure_upload_file
        if ensure_upload_file(basename, in_upload) and in_upload.exists():
            return in_upload
    return in_upload

def get_file_path(filename: str) -> Path:
    resolved = resolve_dataset_path(filename)
    return resolved if resolved is not None else (settings.upload_dir / filename)

def delete_file(filepath: str | Path, remove_remote: bool = False) -> bool:
    basename = extract_basename(filepath)
    path = resolve_dataset_path(filepath)
    deleted = False
    if path and path.exists():
        try:
            path.unlink()
            deleted = True
        except Exception:
            deleted = False
    if remove_remote and is_blob_enabled() and basename:
        try:
            persist_state(deleted_filenames=[basename])
        except Exception:
            pass
    return deleted
