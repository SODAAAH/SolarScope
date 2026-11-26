import uuid
import hashlib
import datetime
from pathlib import Path
from typing import Optional
from backend.app.config import settings
from backend.app.storage.blob_sync import is_blob_enabled, persist_state, upload_file_blob, delete_file_blob

def extract_basename(raw_filepath: str | Path) -> str:
    s = str(raw_filepath).replace("\\", "/")
    return s.rsplit("/", 1)[-1]

def save_uploaded_file(
    source_filename: str,
    file_bytes: bytes,
    dataset_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> tuple[str, Path]:
    file_id = dataset_id or str(uuid.uuid4())
    suffix = Path(source_filename).suffix.lower()
    target_filename = f"{file_id}{suffix}"
    target_path = settings.upload_dir / target_filename
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    with open(target_path, "wb") as f:
        f.write(file_bytes)
    if is_blob_enabled():
        try:
            upload_file_blob(target_filename, file_bytes)
        except Exception:
            pass
    return file_id, target_path

def save_dataset_file_record(
    conn,
    dataset_id: str,
    project_id: str,
    filename: str,
    file_bytes: bytes,
) -> None:
    file_sha = hashlib.sha256(file_bytes).hexdigest()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rec_id = f"df-{dataset_id}"
    conn.execute(
        """INSERT INTO dataset_files (id, dataset_id, project_id, filename, content_sha256, file_bytes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(dataset_id) DO UPDATE SET
               filename = excluded.filename,
               content_sha256 = excluded.content_sha256,
               file_bytes = excluded.file_bytes,
               created_at = excluded.created_at""",
        (rec_id, dataset_id, project_id, filename, file_sha, file_bytes, now_iso)
    )

def resolve_dataset_path(raw_filepath: Optional[str | Path], dataset_id: Optional[str] = None) -> Optional[Path]:
    if not raw_filepath and not dataset_id:
        return None
    if raw_filepath:
        direct = Path(str(raw_filepath))
        if direct.exists():
            return direct
    basename = extract_basename(raw_filepath) if raw_filepath else ""
    if basename:
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

    if dataset_id:
        try:
            from backend.app.storage.db import get_connection
            conn = get_connection()
            row = conn.execute("SELECT filename, file_bytes FROM dataset_files WHERE dataset_id = ?", (dataset_id,)).fetchone()
            conn.close()
            if row and row["file_bytes"]:
                target_name = basename or f"{dataset_id}{Path(row['filename']).suffix.lower()}"
                target_path = settings.upload_dir / target_name
                settings.upload_dir.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(bytes(row["file_bytes"]))
                return target_path
        except Exception:
            pass

    return (settings.upload_dir / basename) if basename else None

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
            delete_file_blob(basename)
            persist_state(deleted_filenames=[basename])
        except Exception:
            pass
    return deleted
