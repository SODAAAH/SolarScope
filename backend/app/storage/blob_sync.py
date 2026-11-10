import os
import json
import time
import shutil
import sqlite3
import hashlib
import datetime
import threading
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from backend.app.config import settings

_lock = threading.RLock()
_hydrated_version: Optional[int] = None
_last_check_monotonic: float = 0.0

_MANIFEST_PATH = "solarscope/manifest.json"
_DB_BLOB_PATH = "solarscope/solarscope.db"
_UPLOAD_PREFIX = "solarscope/uploads/"
_API_BASE = "https://vercel.com/api/blob"
_API_VERSION = "12"

def is_blob_enabled() -> bool:
    token = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
    if not token:
        return False
    return bool(os.environ.get("VERCEL") or os.environ.get("SOLARSCOPE_FORCE_BLOB_SYNC") == "1")

def _get_auth() -> Optional[Tuple[str, str]]:
    if not is_blob_enabled():
        return None
    token = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
    parts = token.split("_")
    store_id = parts[3] if len(parts) >= 4 else ""
    if not store_id:
        return None
    return token, store_id

def _get_local_db_path() -> Path:
    if os.environ.get("VERCEL"):
        db_dir = Path("/tmp") / "solarscope"
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "solarscope.db"
    return settings.base_dir / "solarscope.db"

def _private_blob_url(store_id: str, pathname: str, no_cache: bool = True) -> str:
    clean = pathname.lstrip("/")
    quoted = urllib.parse.quote(clean, safe="/")
    base = f"https://{store_id}.private.blob.vercel-storage.com/{quoted}"
    return f"{base}?t={int(time.time() * 1000)}" if no_cache else base

def _api_headers(token: str, store_id: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    headers = {
        "authorization": f"Bearer {token}",
        "x-api-version": _API_VERSION,
        "x-vercel-blob-store-id": store_id,
    }
    if extra:
        headers.update(extra)
    return headers

def _upload_bytes(pathname: str, data: bytes, content_type: str = "application/octet-stream") -> Optional[Dict[str, Any]]:
    auth = _get_auth()
    if not auth:
        return None
    token, store_id = auth
    qs = urllib.parse.urlencode({"pathname": pathname})
    url = f"{_API_BASE}/?{qs}"
    headers = _api_headers(token, store_id, {
        "x-vercel-blob-access": "private",
        "x-add-random-suffix": "0",
        "x-allow-overwrite": "1",
        "x-cache-control-max-age": "0",
        "x-content-type": content_type,
        "content-type": content_type,
    })
    last_err: Optional[Exception] = None
    for attempt in range(2):
        req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last_err = exc
            if attempt == 0:
                time.sleep(0.25)
    if last_err is not None:
        raise last_err
    return None

def _download_bytes(pathname: str) -> Optional[bytes]:
    auth = _get_auth()
    if not auth:
        return None
    token, store_id = auth
    url = _private_blob_url(store_id, pathname, no_cache=True)
    req = urllib.request.Request(
        url,
        headers={
            "authorization": f"Bearer {token}",
            "cache-control": "no-cache, no-store, max-age=0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read()
    except urllib.error.HTTPError as he:
        if he.code == 404:
            return None
        raise

def _delete_blobs(pathnames: List[str]) -> None:
    auth = _get_auth()
    if not auth or not pathnames:
        return
    token, store_id = auth
    urls = [_private_blob_url(store_id, p, no_cache=False) for p in pathnames if p]
    if not urls:
        return
    payload = json.dumps({"urls": urls}).encode("utf-8")
    headers = _api_headers(token, store_id, {"content-type": "application/json"})
    req = urllib.request.Request(f"{_API_BASE}/delete", data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except Exception:
        pass

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def _make_sqlite_snapshot(db_path: Path) -> bytes:
    snap_path = db_path.with_suffix(".snap.tmp")
    src = None
    dst = None
    try:
        src = sqlite3.connect(str(db_path), timeout=15.0)
        dst = sqlite3.connect(str(snap_path), timeout=15.0)
        src.backup(dst)
        dst.commit()
        dst.close()
        dst = None
        src.close()
        src = None
        return snap_path.read_bytes()
    finally:
        if dst is not None:
            try:
                dst.close()
            except Exception:
                pass
        if src is not None:
            try:
                src.close()
            except Exception:
                pass
        if snap_path.exists():
            try:
                snap_path.unlink()
            except Exception:
                pass

def _atomic_write(target_path: Path, data: bytes) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_name(f".{target_path.name}.{os.getpid()}.tmp")
    try:
        tmp_path.write_bytes(data)
        os.replace(str(tmp_path), str(target_path))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

def _download_manifest() -> Optional[Dict[str, Any]]:
    raw = _download_bytes(_MANIFEST_PATH)
    if not raw:
        return None
    try:
        parsed = json.loads(raw.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None

def ensure_hydrated(force: bool = False) -> bool:
    global _hydrated_version, _last_check_monotonic
    if not _get_auth():
        return False

    with _lock:
        now_mono = time.monotonic()
        db_path = _get_local_db_path()
        if not force and _hydrated_version is not None and db_path.exists() and (now_mono - _last_check_monotonic) < 0.5:
            return False

        _last_check_monotonic = now_mono
        try:
            manifest = _download_manifest()
        except Exception:
            return False

        if not manifest:
            return False

        remote_ver = manifest.get("version")
        if _hydrated_version is not None and remote_ver == _hydrated_version and db_path.exists():
            return False

        try:
            db_bytes = _download_bytes(_DB_BLOB_PATH)
        except Exception:
            return False

        if not db_bytes:
            return False

        _atomic_write(db_path, db_bytes)

        uploads_meta = manifest.get("uploads") or {}
        if isinstance(uploads_meta, dict):
            settings.upload_dir.mkdir(parents=True, exist_ok=True)
            for fname, expected_hash in uploads_meta.items():
                if not fname or "/" in fname or "\\" in fname:
                    continue
                local_file = settings.upload_dir / fname
                needs_download = True
                if local_file.exists():
                    try:
                        if not expected_hash or _sha256_file(local_file) == expected_hash:
                            needs_download = False
                    except Exception:
                        needs_download = True
                if needs_download:
                    try:
                        f_bytes = _download_bytes(f"{_UPLOAD_PREFIX}{fname}")
                        if f_bytes is not None:
                            _atomic_write(local_file, f_bytes)
                    except Exception:
                        pass

            for existing in settings.upload_dir.iterdir():
                if existing.is_file() and not existing.name.startswith(".") and existing.name not in uploads_meta:
                    try:
                        existing.unlink()
                    except Exception:
                        pass

        _hydrated_version = remote_ver
        return True

def ensure_upload_file(basename: str, target_path: Path) -> bool:
    if not basename or not _get_auth():
        return False
    with _lock:
        if target_path.exists():
            return True
        try:
            data = _download_bytes(f"{_UPLOAD_PREFIX}{basename}")
        except Exception:
            return False
        if data is None:
            return False
        _atomic_write(target_path, data)
        return True

def persist_state(
    upload_files: Optional[List[Path]] = None,
    deleted_filenames: Optional[List[str]] = None,
    sync_all_uploads: bool = False,
    source_db_path: Optional[Path] = None,
) -> bool:
    global _hydrated_version, _last_check_monotonic
    if not _get_auth():
        return False

    with _lock:
        db_path = source_db_path or _get_local_db_path()
        if not db_path.exists():
            return False

        try:
            manifest = _download_manifest() or {}
        except Exception:
            manifest = {}

        uploads_map: Dict[str, str] = {}
        raw_uploads = manifest.get("uploads")
        if isinstance(raw_uploads, dict):
            uploads_map.update({str(k): str(v) for k, v in raw_uploads.items()})

        if deleted_filenames:
            clean_deleted = [name for name in deleted_filenames if name and not name.startswith(".")]
            if clean_deleted:
                _delete_blobs([f"{_UPLOAD_PREFIX}{name}" for name in clean_deleted])
                for name in clean_deleted:
                    uploads_map.pop(name, None)

        candidates: List[Path] = []
        if sync_all_uploads and settings.upload_dir.exists():
            for p in sorted(settings.upload_dir.iterdir()):
                if p.is_file() and not p.name.startswith(".") and not p.name.endswith(".tmp"):
                    candidates.append(p)
        elif upload_files:
            for p in upload_files:
                if p and p.exists() and p.is_file():
                    candidates.append(p)

        for file_path in candidates:
            fname = file_path.name
            file_bytes = file_path.read_bytes()
            file_hash = _sha256_bytes(file_bytes)
            if uploads_map.get(fname) != file_hash:
                ctype = "text/csv" if fname.lower().endswith(".csv") else "application/octet-stream"
                _upload_bytes(f"{_UPLOAD_PREFIX}{fname}", file_bytes, content_type=ctype)
                uploads_map[fname] = file_hash

        snap_bytes = _make_sqlite_snapshot(db_path)
        _upload_bytes(_DB_BLOB_PATH, snap_bytes, content_type="application/x-sqlite3")

        prev_ver = manifest.get("version") or 0
        try:
            prev_ver_int = int(prev_ver)
        except Exception:
            prev_ver_int = 0
        new_ver = max(int(time.time() * 1000), prev_ver_int + 1)
        new_manifest = {
            "version": new_ver,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "uploads": uploads_map,
        }
        _upload_bytes(_MANIFEST_PATH, json.dumps(new_manifest).encode("utf-8"), content_type="application/json")
        _hydrated_version = new_ver
        _last_check_monotonic = time.monotonic()
        return True
