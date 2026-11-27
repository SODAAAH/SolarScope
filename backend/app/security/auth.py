import datetime
import re
import time
import uuid
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from fastapi import Request, Response, HTTPException, Depends

from backend.app.config import settings, is_hosted_mode
from backend.app.storage.db import get_connection, create_project_for_user, init_db
from backend.app.storage.blob_sync import ensure_hydrated, is_sqlite_blob_mode
from backend.app.security.crypto import (
    hash_password,
    verify_password,
    generate_token,
    hash_token,
    sign_session_token,
    verify_session_token,
)

SESSION_COOKIE_NAME = "solarscope_session"
CSRF_COOKIE_NAME = "solarscope_csrf"

@dataclass
class AuthContext:
    user_id: str
    email: str
    display_name: str
    role: str
    project_id: str
    is_authenticated: bool
    is_local_fallback: bool
    hosted_mode: bool
    csrf_token: str = ""

def _cookie_secure_flag(request: Optional[Request] = None) -> bool:
    cfg = (settings.cookie_secure or "auto").strip().lower()
    if cfg in ("1", "true", "yes"):
        return True
    if cfg in ("0", "false", "no"):
        return False
    if request is not None:
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").split(",")[0].strip().lower()
        if proto == "https":
            return True
        if proto == "http":
            return False
    return is_hosted_mode()

def _issue_session_token(
    user_id: str,
    email: str,
    display_name: str,
    role: str,
    project_id: str,
    csrf_token: str,
    ttl_hours: int,
) -> str:
    signed = sign_session_token({
        "uid": user_id,
        "email": email,
        "name": display_name,
        "role": role,
        "pid": project_id,
        "csrf": csrf_token,
        "exp": int(time.time()) + max(3600, int(ttl_hours) * 3600),
    })
    return signed or generate_token(32)

def set_session_cookies(response: Response, raw_token: str, csrf_token: str, request: Optional[Request] = None) -> None:
    secure_flag = _cookie_secure_flag(request)
    max_age = max(3600, int(settings.session_ttl_hours) * 3600)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=secure_flag,
        samesite="lax",
        path="/",
        max_age=max_age,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=secure_flag,
        samesite="lax",
        path="/",
        max_age=max_age,
    )

def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")

def _validate_email(email: str) -> str:
    cleaned = (email or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", cleaned):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    return cleaned

def register_user_account(
    email: str,
    password: str,
    display_name: str = "",
    installation_name: str = "",
) -> Dict[str, Any]:
    clean_email = _validate_email(email)
    if len(password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    clean_name = (display_name or "").strip() or clean_email.split("@")[0]
    proj_name = (installation_name or "").strip() or f"{clean_name}'s Solar System"

    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM users WHERE lower(email) = lower(?)", (clean_email,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")

        user_id = f"usr-{uuid.uuid4().hex[:12]}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        pw_hash = hash_password(password)
        conn.execute(
            """INSERT INTO users (id, email, display_name, password_hash, role, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'member', 1, ?, ?)""",
            (user_id, clean_email, clean_name, pw_hash, now_iso, now_iso)
        )
        project = create_project_for_user(
            user_id=user_id,
            name=proj_name,
            description="Household solar installation",
            is_default=True,
            conn=conn,
        )
        csrf_token = generate_token(24)
        raw_token = _issue_session_token(
            user_id=user_id,
            email=clean_email,
            display_name=clean_name,
            role="member",
            project_id=project["id"],
            csrf_token=csrf_token,
            ttl_hours=int(settings.session_ttl_hours),
        )
        expires_at = (
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=int(settings.session_ttl_hours))
        ).isoformat()
        conn.execute(
            """INSERT INTO user_sessions (id, user_id, token_hash, csrf_token, expires_at, created_at, last_seen_at, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"sess-{uuid.uuid4().hex[:12]}", user_id, hash_token(raw_token), csrf_token, expires_at, now_iso, now_iso, "")
        )
        conn.commit()
        return {
            "user": {
                "id": user_id,
                "email": clean_email,
                "display_name": clean_name,
                "role": "member",
            },
            "projects": [project],
            "active_project_id": project["id"],
            "raw_token": raw_token,
            "csrf_token": csrf_token,
        }
    finally:
        conn.close()

def authenticate_user_account(email: str, password: str, user_agent: str = "") -> Dict[str, Any]:
    clean_email = _validate_email(email)
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE lower(email) = lower(?) AND is_active = 1",
            (clean_email,)
        ).fetchone()
        if not user or not verify_password(password or "", user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        user_id = user["id"]
        projects = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM projects WHERE owner_user_id = ? ORDER BY is_default DESC, created_at ASC",
                (user_id,)
            ).fetchall()
        ]
        if not projects:
            proj = create_project_for_user(
                user_id=user_id,
                name=f"{user['display_name']}'s Solar System",
                description="Household solar installation",
                is_default=True,
                conn=conn,
            )
            projects = [proj]

        csrf_token = generate_token(24)
        raw_token = _issue_session_token(
            user_id=user_id,
            email=user["email"],
            display_name=user["display_name"],
            role=user["role"],
            project_id=projects[0]["id"],
            csrf_token=csrf_token,
            ttl_hours=int(settings.session_ttl_hours),
        )
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        expires_at = (
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=int(settings.session_ttl_hours))
        ).isoformat()
        conn.execute(
            """INSERT INTO user_sessions (id, user_id, token_hash, csrf_token, expires_at, created_at, last_seen_at, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"sess-{uuid.uuid4().hex[:12]}", user_id, hash_token(raw_token), csrf_token, expires_at, now_iso, now_iso, user_agent[:200])
        )
        conn.commit()
        return {
            "user": {
                "id": user_id,
                "email": user["email"],
                "display_name": user["display_name"],
                "role": user["role"],
            },
            "projects": projects,
            "active_project_id": projects[0]["id"],
            "raw_token": raw_token,
            "csrf_token": csrf_token,
        }
    finally:
        conn.close()

def revoke_session(raw_token: Optional[str]) -> None:
    if not raw_token:
        return
    conn = get_connection()
    try:
        conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (hash_token(raw_token),))
        conn.commit()
    finally:
        conn.close()

def _extract_raw_token(request: Request) -> Optional[str]:
    cookie_tok = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_tok:
        return cookie_tok.strip()
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None

def _resolve_user_project(conn, user_id: str, requested_project_id: Optional[str]) -> str:
    if requested_project_id:
        clean_pid = requested_project_id.strip()
        row = conn.execute(
            "SELECT id FROM projects WHERE id = ? AND owner_user_id = ?",
            (clean_pid, user_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=403, detail="You do not have access to the requested installation.")
        return row["id"]

    row = conn.execute(
        "SELECT id FROM projects WHERE owner_user_id = ? ORDER BY is_default DESC, created_at ASC LIMIT 1",
        (user_id,)
    ).fetchone()
    if row:
        return row["id"]

    proj = create_project_for_user(
        user_id=user_id,
        name="Primary Solar Installation",
        description="Household solar installation",
        is_default=True,
        conn=conn,
    )
    conn.commit()
    return proj["id"]

def list_user_projects(user_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM projects WHERE owner_user_id = ? ORDER BY is_default DESC, created_at ASC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def _verify_csrf_if_cookie_session(request: Request, session_csrf: str) -> None:
    if request.method.upper() in ("GET", "HEAD", "OPTIONS"):
        return
    if not request.cookies.get(SESSION_COOKIE_NAME):
        return
    header_csrf = (request.headers.get("X-CSRF-Token") or "").strip()
    if not header_csrf or header_csrf != session_csrf:
        raise HTTPException(status_code=403, detail="CSRF token validation failed.")

def get_auth_context(request: Request) -> AuthContext:
    hosted = is_hosted_mode()
    raw_token = _extract_raw_token(request)
    requested_project = request.headers.get("X-Project-Id") or request.query_params.get("project_id")

    if raw_token:
        if is_sqlite_blob_mode():
            if ensure_hydrated(force=False):
                init_db(hydrate=False)
        tok_hash = hash_token(raw_token)
        conn = get_connection()
        try:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            sess = conn.execute(
                """SELECT s.user_id, s.csrf_token, s.expires_at, u.email, u.display_name, u.role, u.is_active
                   FROM user_sessions s
                   JOIN users u ON u.id = s.user_id
                   WHERE s.token_hash = ?""",
                (tok_hash,)
            ).fetchone()
            if not sess and is_sqlite_blob_mode():
                conn.close()
                if ensure_hydrated(force=True):
                    init_db(hydrate=False)
                    conn = get_connection()
                    sess = conn.execute(
                        """SELECT s.user_id, s.csrf_token, s.expires_at, u.email, u.display_name, u.role, u.is_active
                           FROM user_sessions s
                           JOIN users u ON u.id = s.user_id
                           WHERE s.token_hash = ?""",
                        (tok_hash,)
                    ).fetchone()
                else:
                    conn = get_connection()
            if not sess:
                token_claims = verify_session_token(raw_token)
                if token_claims:
                    claim_uid = str(token_claims.get("uid") or "")
                    claim_csrf = str(token_claims.get("csrf") or "")
                    _verify_csrf_if_cookie_session(request, claim_csrf)
                    user_row = conn.execute(
                        "SELECT id, email, display_name, role, is_active FROM users WHERE id = ?",
                        (claim_uid,)
                    ).fetchone()
                    if not user_row and is_sqlite_blob_mode():
                        conn.close()
                        if ensure_hydrated(force=True):
                            init_db(hydrate=False)
                        conn = get_connection()
                        user_row = conn.execute(
                            "SELECT id, email, display_name, role, is_active FROM users WHERE id = ?",
                            (claim_uid,)
                        ).fetchone()
                    if user_row and not user_row["is_active"]:
                        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
                    if user_row:
                        project_id = _resolve_user_project(conn, user_row["id"], requested_project)
                        return AuthContext(
                            user_id=user_row["id"],
                            email=user_row["email"],
                            display_name=user_row["display_name"],
                            role=user_row["role"],
                            project_id=project_id,
                            is_authenticated=True,
                            is_local_fallback=False,
                            hosted_mode=hosted,
                            csrf_token=claim_csrf,
                        )
                raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
            if not sess["is_active"] or sess["expires_at"] <= now_iso:
                conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (tok_hash,))
                conn.commit()
                raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")

            _verify_csrf_if_cookie_session(request, sess["csrf_token"])
            project_id = _resolve_user_project(conn, sess["user_id"], requested_project)
            return AuthContext(
                user_id=sess["user_id"],
                email=sess["email"],
                display_name=sess["display_name"],
                role=sess["role"],
                project_id=project_id,
                is_authenticated=True,
                is_local_fallback=False,
                hosted_mode=hosted,
                csrf_token=sess["csrf_token"],
            )
        finally:
            conn.close()

    if hosted:
        raise HTTPException(status_code=401, detail="Authentication required.")

    if is_sqlite_blob_mode():
        if ensure_hydrated(force=False):
            init_db(hydrate=False)

    conn = get_connection()
    try:
        project_id = _resolve_user_project(conn, "user-local", requested_project)
        return AuthContext(
            user_id="user-local",
            email="local@solarscope.device",
            display_name="Local Household",
            role="owner",
            project_id=project_id,
            is_authenticated=True,
            is_local_fallback=True,
            hosted_mode=False,
            csrf_token="",
        )
    finally:
        conn.close()

def get_optional_auth_state(request: Request) -> Optional[AuthContext]:
    try:
        raw_token = _extract_raw_token(request)
        if not raw_token:
            if not is_hosted_mode():
                return get_auth_context(request)
            return None
        return get_auth_context(request)
    except HTTPException:
        return None


def authenticate_demo_account(user_agent: str = "") -> Dict[str, Any]:
    demo_email = "demo@solarscope.app"
    demo_user_id = "usr-demo-solarscope"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn = get_connection()
    project_id = ""
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE lower(email) = lower(?) AND is_active = 1",
            (demo_email,)
        ).fetchone()
        if not user:
            pw_hash = hash_password(generate_token(24))
            conn.execute(
                """INSERT INTO users (id, email, display_name, password_hash, role, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'member', 1, ?, ?)""",
                (demo_user_id, demo_email, "Demo Visitor", pw_hash, now_iso, now_iso)
            )
            proj = create_project_for_user(
                user_id=demo_user_id,
                name="Demo Residence Solar (Tarlac)",
                description="Pre-seeded 7-day sample solar and Tarlac Electric Inc. workspace",
                is_default=True,
                conn=conn,
            )
            project_id = proj["id"]
            user_id = demo_user_id
            display_name = "Demo Visitor"
            role = "member"
            projects = [proj]
        else:
            user_id = user["id"]
            display_name = user["display_name"]
            role = user["role"]
            projects = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM projects WHERE owner_user_id = ? ORDER BY is_default DESC, created_at ASC",
                    (user_id,)
                ).fetchall()
            ]
            if not projects:
                proj = create_project_for_user(
                    user_id=user_id,
                    name="Demo Residence Solar (Tarlac)",
                    description="Pre-seeded 7-day sample solar and Tarlac Electric Inc. workspace",
                    is_default=True,
                    conn=conn,
                )
                projects = [proj]
            project_id = projects[0]["id"]

        settings_row = conn.execute(
            "SELECT pv_capacity_kwp FROM system_settings WHERE project_id = ?",
            (project_id,)
        ).fetchone()
        if not settings_row or float(settings_row["pv_capacity_kwp"] or 0.0) <= 0.0:
            conn.execute(
                """UPDATE system_settings
                   SET station_name = ?, location_name = ?, latitude = ?, longitude = ?,
                       pv_capacity_kwp = ?, num_modules = ?, module_wattage = ?,
                       inverter_model = ?, inverter_power_kw = ?,
                       battery_capacity_kwh = ?, usable_capacity_kwh = ?, reserve_soc = ?,
                       import_tariff = ?, updated_at = ?
                   WHERE project_id = ?""",
                (
                    "Demo Residence · Tarlac",
                    "Tarlac City, Philippines",
                    15.4755,
                    120.5963,
                    5.5,
                    10,
                    550.0,
                    "Deye SUN-5K-SG03LP1-EU",
                    5.0,
                    10.24,
                    8.19,
                    20.0,
                    11.45,
                    now_iso,
                    project_id,
                )
            )

        dataset_count_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM datasets WHERE project_id = ?",
            (project_id,)
        ).fetchone()
        has_datasets = bool(dataset_count_row and int(dataset_count_row["cnt"] or 0) > 0)

        csrf_token = generate_token(24)
        raw_token = _issue_session_token(
            user_id=user_id,
            email=demo_email,
            display_name=display_name,
            role=role,
            project_id=project_id,
            csrf_token=csrf_token,
            ttl_hours=int(settings.session_ttl_hours),
        )
        expires_at = (
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=int(settings.session_ttl_hours))
        ).isoformat()
        conn.execute(
            """INSERT INTO user_sessions (id, user_id, token_hash, csrf_token, expires_at, created_at, last_seen_at, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"sess-{uuid.uuid4().hex[:12]}", user_id, hash_token(raw_token), csrf_token, expires_at, now_iso, now_iso, user_agent[:200])
        )
        conn.commit()
    finally:
        conn.close()

    if not has_datasets:
        try:
            from backend.app.integrations.deye_cloud import DeyeCloudClient
            client = DeyeCloudClient(project_id=project_id)
            client.save_config({
                "station_id": "DEMO_STATION",
                "data_center": "eu",
                "app_id": "demo",
                "app_secret": "demo",
                "username": "demo",
                "password": "demo",
                "auto_sync": False,
                "sync_interval_min": 5,
                "reconciliation_policy": "MERGE",
            })
            today = datetime.date.today()
            start_day = today - datetime.timedelta(days=6)
            client.sync_range(start_day.isoformat(), today.isoformat())
        except Exception:
            pass

    return {
        "user": {
            "id": user_id,
            "email": demo_email,
            "display_name": display_name,
            "role": role,
        },
        "projects": projects,
        "active_project_id": project_id,
        "raw_token": raw_token,
        "csrf_token": csrf_token,
    }
