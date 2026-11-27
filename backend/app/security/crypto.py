import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional, Dict, Any

from backend.app.config import settings, is_hosted_mode

_ENC_PREFIX = "enc:v1:"
_PBKDF2_ITERATIONS = 310_000

def _resolve_master_key_bytes() -> bytes:
    for env_name in ("SOLARSCOPE_ENCRYPTION_KEY", "SOLARSCOPE_SECRET_KEY", "SESSION_SECRET"):
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return hashlib.sha256(raw.encode("utf-8")).digest()

    cfg_raw = (settings.encryption_key or settings.secret_key or "").strip()
    if cfg_raw:
        return hashlib.sha256(cfg_raw.encode("utf-8")).digest()

    if is_hosted_mode():
        fallback_seed = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
        if fallback_seed:
            return hashlib.sha256(f"solarscope-hosted:{fallback_seed}".encode("utf-8")).digest()
        raise RuntimeError(
            "SOLARSCOPE_ENCRYPTION_KEY or SOLARSCOPE_SECRET_KEY must be configured in hosted mode."
        )

    key_path = Path(settings.base_dir).parent / ".solarscope.key"
    if key_path.exists():
        raw_file = key_path.read_text(encoding="utf-8").strip()
        if raw_file:
            return hashlib.sha256(raw_file.encode("utf-8")).digest()

    generated = secrets.token_urlsafe(48)
    try:
        key_path.write_text(generated, encoding="utf-8")
        try:
            os.chmod(key_path, 0o600)
        except Exception:
            pass
    except Exception:
        pass
    return hashlib.sha256(generated.encode("utf-8")).digest()

def _aes_gcm_encrypt(key: bytes, plaintext: bytes) -> str:
    nonce = secrets.token_bytes(12)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        ct = AESGCM(key).encrypt(nonce, plaintext, b"solarscope-v1")
        token = base64.urlsafe_b64encode(nonce + ct).decode("ascii")
        return f"{_ENC_PREFIX}{token}"
    except ImportError:
        from Cryptodome.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        cipher.update(b"solarscope-v1")
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        token = base64.urlsafe_b64encode(nonce + ciphertext + tag).decode("ascii")
        return f"{_ENC_PREFIX}{token}"

def _aes_gcm_decrypt(key: bytes, payload: str) -> str:
    encoded = payload[len(_ENC_PREFIX):]
    raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
    if len(raw) < 28:
        raise ValueError("Invalid encrypted payload length")
    nonce = raw[:12]
    body = raw[12:]
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        pt = AESGCM(key).decrypt(nonce, body, b"solarscope-v1")
        return pt.decode("utf-8")
    except ImportError:
        from Cryptodome.Cipher import AES
        ciphertext = body[:-16]
        tag = body[-16:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        cipher.update(b"solarscope-v1")
        pt = cipher.decrypt_and_verify(ciphertext, tag)
        return pt.decode("utf-8")

def is_encrypted_secret(value: Optional[str]) -> bool:
    return bool(value and isinstance(value, str) and value.startswith(_ENC_PREFIX))

def encrypt_secret(plaintext: Optional[str]) -> str:
    cleaned = (plaintext or "").strip()
    if not cleaned:
        return ""
    if is_encrypted_secret(cleaned):
        return cleaned
    key = _resolve_master_key_bytes()
    return _aes_gcm_encrypt(key, cleaned.encode("utf-8"))

def decrypt_secret(stored_value: Optional[str]) -> str:
    cleaned = (stored_value or "").strip()
    if not cleaned:
        return ""
    if not is_encrypted_secret(cleaned):
        return cleaned
    key = _resolve_master_key_bytes()
    try:
        return _aes_gcm_decrypt(key, cleaned)
    except Exception:
        return ""

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${base64.b64encode(salt).decode('ascii')}${base64.b64encode(dk).decode('ascii')}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        parts = (stored_hash or "").split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iters = int(parts[1])
        salt = base64.b64decode(parts[2].encode("ascii"))
        expected = base64.b64decode(parts[3].encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)

def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def sign_session_token(payload: Dict[str, Any]) -> Optional[str]:
    try:
        key = _resolve_master_key_bytes()
    except Exception:
        return None
    raw_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = base64.urlsafe_b64encode(raw_json).decode("ascii").rstrip("=")
    sig = hmac.new(key, body.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"ss1.{body}.{sig_b64}"

def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        if not token or not token.startswith("ss1."):
            return None
        parts = token.split(".")
        if len(parts) != 3:
            return None
        _, body, sig_b64 = parts
        key = _resolve_master_key_bytes()
        expected_sig = hmac.new(key, body.encode("ascii"), hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).decode("ascii").rstrip("=")
        if not hmac.compare_digest(sig_b64, expected_b64):
            return None
        padded = body + "=" * (-len(body) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if not isinstance(data, dict):
            return None
        exp = float(data.get("exp") or 0)
        if exp <= time.time():
            return None
        return data
    except Exception:
        return None
