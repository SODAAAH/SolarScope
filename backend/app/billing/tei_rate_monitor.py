import io
import json
import hashlib
import datetime
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Any, Optional, Tuple, List
from backend.app.billing.tariff_models import TEIRateSchedule, TEIRateComponent
from backend.app.billing.tariff_defaults import get_default_tei_schedule

OFFICIAL_TEI_URL = "https://tarlacelectric.com/rate-schedule-customer-class"
TEI_WP_POSTS_API = "https://tarlacelectric.com/wp-json/wp/v2/posts?search=Rate+Schedule&orderby=date&order=desc&per_page=10"
_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
}

_MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

def compute_document_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _row_to_schedule(row) -> TEIRateSchedule:
    comps_data = json.loads(row["schedule_data_json"])
    comps = [TEIRateComponent(**c) for c in comps_data]
    return TEIRateSchedule(
        id=row["id"],
        effective_month=row["effective_month"],
        customer_class=row["customer_class"],
        publication_date=row["publication_date"] or "",
        source_url=row["source_url"] or OFFICIAL_TEI_URL,
        document_hash=row["document_hash"] or "",
        verification_status=row["verification_status"] or "unconfigured",
        components=comps,
        created_at=row["created_at"]
    )

def get_active_rate_schedule(
    conn,
    customer_class: Optional[str] = None,
    project_id: str = "default"
) -> TEIRateSchedule:
    target_class = (customer_class or "").strip() or "Residential"
    pref = conn.execute(
        """SELECT s.* FROM project_rate_preferences p
           JOIN tei_rate_schedules s ON s.id = p.active_schedule_id
           WHERE p.project_id = ? AND lower(p.customer_class) = lower(?)
             AND (s.project_id = 'global' OR s.project_id = ?)
           LIMIT 1""",
        (project_id, target_class, project_id)
    ).fetchone()
    if pref:
        return _row_to_schedule(pref)

    row = conn.execute(
        """SELECT * FROM tei_rate_schedules
           WHERE is_active = 1 AND lower(customer_class) = lower(?)
             AND (project_id = 'global' OR project_id = ?)
           ORDER BY CASE WHEN project_id = ? THEN 0 ELSE 1 END, effective_month DESC, created_at DESC LIMIT 1""",
        (target_class, project_id, project_id)
    ).fetchone()
    if not row:
        row = conn.execute(
            """SELECT * FROM tei_rate_schedules
               WHERE is_active = 1 AND (project_id = 'global' OR project_id = ?)
               ORDER BY effective_month DESC, created_at DESC LIMIT 1""",
            (project_id,)
        ).fetchone()
    if row:
        return _row_to_schedule(row)

    default_sched = get_default_tei_schedule()
    default_sched.customer_class = target_class
    save_rate_schedule(default_sched, conn, project_id="global")
    return default_sched

def get_rate_schedule_for_month(
    conn,
    customer_class: Optional[str] = None,
    billing_month: Optional[str] = None,
    project_id: str = "default"
) -> TEIRateSchedule:
    if billing_month and re.match(r"^\d{4}-\d{2}$", billing_month.strip()):
        bm = billing_month.strip()
        if customer_class:
            row = conn.execute(
                """SELECT * FROM tei_rate_schedules
                   WHERE effective_month = ? AND lower(customer_class) = lower(?)
                     AND (project_id = 'global' OR project_id = ?)
                   ORDER BY CASE WHEN project_id = ? THEN 0 ELSE 1 END, is_active DESC, created_at DESC LIMIT 1""",
                (bm, customer_class.strip(), project_id, project_id)
            ).fetchone()
            if row:
                return _row_to_schedule(row)
        row = conn.execute(
            """SELECT * FROM tei_rate_schedules
               WHERE effective_month = ? AND (project_id = 'global' OR project_id = ?)
               ORDER BY is_active DESC, created_at DESC LIMIT 1""",
            (bm, project_id)
        ).fetchone()
        if row:
            return _row_to_schedule(row)
    return get_active_rate_schedule(conn, customer_class=customer_class, project_id=project_id)

def set_project_active_schedule(conn, project_id: str, customer_class: str, schedule_id: str) -> None:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    slug_class = (customer_class or "Residential").strip().lower().replace(" ", "_")
    pref_id = f"pref-{project_id}-{slug_class}"
    conn.execute(
        """INSERT INTO project_rate_preferences (id, project_id, customer_class, active_schedule_id, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(project_id, customer_class) DO UPDATE SET
               active_schedule_id = excluded.active_schedule_id,
               updated_at = excluded.updated_at""",
        (pref_id, project_id, customer_class, schedule_id, now_iso)
    )

def activate_rate_schedule(schedule_id: str, conn, project_id: str = "default") -> Optional[TEIRateSchedule]:
    row = conn.execute(
        "SELECT * FROM tei_rate_schedules WHERE id = ? AND (project_id = 'global' OR project_id = ?)",
        (schedule_id, project_id)
    ).fetchone()
    if not row:
        return None
    sched = _row_to_schedule(row)
    set_project_active_schedule(conn, project_id, sched.customer_class, schedule_id)
    return sched

def get_rate_check_state(conn, project_id: str = "default") -> Dict[str, Any]:
    state_id = f"rate-state-{project_id}"
    row = conn.execute("SELECT * FROM tei_rate_check_state WHERE id = ?", (state_id,)).fetchone()
    if not row:
        row = conn.execute("SELECT * FROM tei_rate_check_state WHERE id = 'default'").fetchone()
    if not row:
        return {
            "status": "pending",
            "message": "Rate schedule not yet verified against TEI.",
            "checked_at": None,
            "rate_change_alert": None
        }
    alert_raw = row["rate_change_alert_json"]
    alert = None
    if alert_raw:
        try:
            alert = json.loads(alert_raw)
        except Exception:
            alert = None
    return {
        "status": row["status"],
        "message": row["message"],
        "checked_at": row["checked_at"],
        "rate_change_alert": alert
    }

def save_rate_check_state(state: Dict[str, Any], conn, project_id: str = "default") -> None:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    alert = state.get("rate_change_alert")
    alert_json = json.dumps(alert) if alert is not None else None
    state_id = f"rate-state-{project_id}"
    conn.execute(
        """INSERT INTO tei_rate_check_state
           (id, project_id, status, message, checked_at, rate_change_alert_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               status = excluded.status,
               message = excluded.message,
               checked_at = excluded.checked_at,
               rate_change_alert_json = excluded.rate_change_alert_json,
               updated_at = excluded.updated_at""",
        (
            state_id,
            project_id,
            str(state.get("status") or "pending"),
            str(state.get("message") or ""),
            state.get("checked_at"),
            alert_json,
            now_iso
        )
    )

def save_rate_schedule(schedule: TEIRateSchedule, conn, project_id: str = "global") -> None:
    if project_id == "global":
        conn.execute(
            "UPDATE tei_rate_schedules SET is_active = 0 WHERE project_id = 'global' AND lower(customer_class) = lower(?)",
            (schedule.customer_class,)
        )
    comps_json = json.dumps([c.model_dump() for c in schedule.components])
    conn.execute(
        """INSERT INTO tei_rate_schedules
           (id, project_id, effective_month, customer_class, publication_date, source_url, document_hash, verification_status, is_active, schedule_data_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               effective_month = excluded.effective_month,
               customer_class = excluded.customer_class,
               publication_date = excluded.publication_date,
               source_url = excluded.source_url,
               document_hash = excluded.document_hash,
               verification_status = excluded.verification_status,
               is_active = excluded.is_active,
               schedule_data_json = excluded.schedule_data_json,
               created_at = excluded.created_at""",
        (
            schedule.id,
            project_id,
            schedule.effective_month,
            schedule.customer_class,
            schedule.publication_date,
            schedule.source_url,
            schedule.document_hash,
            schedule.verification_status,
            comps_json,
            schedule.created_at
        )
    )

def get_rate_history(conn, project_id: str = "default") -> List[Dict[str, Any]]:
    pref_rows = conn.execute(
        "SELECT active_schedule_id FROM project_rate_preferences WHERE project_id = ?",
        (project_id,)
    ).fetchall()
    preferred_ids = {r["active_schedule_id"] for r in pref_rows}

    rows = conn.execute(
        """SELECT id, project_id, effective_month, customer_class, publication_date, source_url, document_hash, verification_status, is_active, created_at, schedule_data_json
           FROM tei_rate_schedules
           WHERE project_id = 'global' OR project_id = ?
           ORDER BY effective_month DESC, created_at DESC""",
        (project_id,)
    ).fetchall()
    results = []
    for r in rows:
        comps = json.loads(r["schedule_data_json"])
        gen_rate = next((c["rate_per_kwh"] for c in comps if c["component_id"] == "gen_charge"), 0.0)
        is_active_for_proj = (r["id"] in preferred_ids) if preferred_ids else bool(r["is_active"])
        results.append({
            "id": r["id"],
            "effective_month": r["effective_month"],
            "customer_class": r["customer_class"],
            "publication_date": r["publication_date"],
            "source_url": r["source_url"],
            "document_hash": r["document_hash"],
            "verification_status": r["verification_status"],
            "is_active": is_active_for_proj,
            "is_custom": r["project_id"] == project_id,
            "created_at": r["created_at"],
            "generation_charge": gen_rate,
            "components_count": len(comps)
        })
    return results

def _http_get_bytes(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(url, headers=_HTTP_HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def _parse_month_text(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(
        r"(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    month_num = _MONTH_MAP.get(m.group(1).lower())
    year_num = int(m.group(2))
    if month_num and 2020 <= year_num <= 2100:
        return f"{year_num:04d}-{month_num:02d}"
    return None

def _parse_numeric_token(tok: str) -> Tuple[Optional[float], Optional[str]]:
    clean = tok.strip().replace(",", "")
    if clean.endswith("%"):
        return None, clean
    neg = False
    if clean.startswith("(") and clean.endswith(")"):
        neg = True
        clean = clean[1:-1]
    val = float(clean)
    return (-val if neg else val), None

def _build_component_from_row(
    desc_text: str,
    rate_val: Optional[float],
    vat_num: Optional[float],
    vat_pct: Optional[str],
    seen_ids: set
) -> Optional[TEIRateComponent]:
    if rate_val is None:
        return None
    d_lower = re.sub(r"\s+", " ", desc_text).strip().lower()
    is_per_kw = "php/kw" in d_lower and "php/kwh" not in d_lower
    is_per_month = "customer/month" in d_lower or "/month" in d_lower
    if is_per_kw:
        return None

    if vat_pct is not None:
        if vat_pct == "12%":
            vat_treatment = "vatable"
            vat_rate_per_kwh = 0.0
        else:
            vat_treatment = "exempt"
            vat_rate_per_kwh = 0.0
    elif vat_num is not None and vat_num > 0.0:
        vat_treatment = "fixed_rate"
        vat_rate_per_kwh = round(float(vat_num), 6)
    else:
        vat_treatment = "exempt"
        vat_rate_per_kwh = 0.0

    spec: Optional[Tuple[str, str, str, str, str]] = None
    if "generation charge" in d_lower:
        spec = ("gen_charge", "Generation Charge", "generation_transmission", "₱/kWh", "Cost of electricity TEI purchases from power suppliers.")
    elif "daa" in d_lower:
        spec = ("daa_adjustment", "DAA (GRAM & ICERA)", "generation_transmission", "₱/kWh", "Approved deferred fuel and purchased power adjustments.")
    elif "power act reduction" in d_lower:
        spec = ("power_act_reduction", "Power Act Reduction", "generation_transmission", "₱/kWh", "Statutory residential power act rate reduction.")
    elif "transmission charge" in d_lower:
        spec = ("trans_charge", "Transmission Delivery Charge", "generation_transmission", "₱/kWh", "Cost of delivering power through the NGCP national grid.")
    elif "ancillary service" in d_lower:
        spec = ("ancillary_charge", "Ancillary Service Charge", "generation_transmission", "₱/kWh", "Grid frequency and voltage stability support services.")
    elif "system loss" in d_lower:
        spec = ("system_loss_charge", "System Loss Charge", "generation_transmission", "₱/kWh", "Technical and non-technical energy lost in distribution lines.")
    elif "distribution charge" in d_lower:
        spec = ("dist_charge", "Distribution Network Charge", "distribution", "₱/kWh", "Operating, building, and maintaining TEI local poles and transformers.")
    elif "supply charge" in d_lower and is_per_month:
        spec = ("supply_fixed_charge", "Supply Charge (Monthly Fixed)", "distribution", "₱/cust/mo", "Fixed monthly account management charge.")
    elif "supply charge" in d_lower:
        spec = ("supply_kwh_charge", "Supply Charge (Per kWh)", "distribution", "₱/kWh", "Billing, customer care, and energy account services per kWh.")
    elif "metering charge" in d_lower and is_per_month:
        spec = ("metering_fixed_charge", "Metering Charge (Monthly Fixed)", "distribution", "₱/cust/mo", "Fixed monthly meter device maintenance fee.")
    elif "metering charge" in d_lower:
        spec = ("metering_kwh_charge", "Metering Charge (Per kWh)", "distribution", "₱/kWh", "Meter maintenance, testing, and periodic data logging per kWh.")
    elif "regulatory reset" in d_lower:
        spec = ("reg_reset_adj", "Regulatory Reset Cost Adjustment", "other", "₱/kWh", "ERC regulatory reset rate adjustments.")
    elif "subsidy on lifeline" in d_lower:
        spec = ("lifeline_subsidy", "Subsidy on Lifeline Rate", "other", "₱/kWh", "Uniform cross-subsidy supporting marginalized low-income households.")
    elif "subsidy on senior" in d_lower:
        spec = ("senior_subsidy", "Subsidy on Senior Citizen Rate", "other", "₱/kWh", "Statutory cross-subsidy funding qualified senior citizen discounts.")
    elif "franchise tax" in d_lower:
        spec = ("local_franchise_tax", "Local Franchise Tax", "taxes", "% of Gross", "Municipal franchise tax assessed on electrical distribution revenue.")
    elif "real property tax" in d_lower:
        spec = ("real_property_tax", "Real Property Tax (RPT)", "taxes", "₱/kWh", "Pass-through local government tax assessed on utility infrastructure assets.")
    elif "missionary electrification-spug" in d_lower or "spug" in d_lower:
        spec = ("missionary_spug", "Universal Charge - ME (SPUG)", "other", "₱/kWh", "Missionary electrification charge for Small Power Utilities Group areas.")
    elif "missionary electrification-red" in d_lower or "me-red" in d_lower or re.search(r"\bred\b", d_lower):
        spec = ("missionary_red", "Universal Charge - ME (RED)", "other", "₱/kWh", "Missionary electrification charge for Renewable Energy Developers.")
    elif "missionary electrification" in d_lower:
        spec = ("missionary_electrification", "Universal Charge - Missionary Electrification", "other", "₱/kWh", "Government charge funding electricity to remote unserved off-grid islands.")
    elif "environmental charge" in d_lower:
        spec = ("environmental_charge", "Universal Charge - Environmental Charge", "other", "₱/kWh", "Government fee for watershed rehabilitation and clean energy management.")
    elif "npc-scc" in d_lower:
        spec = ("npc_scc", "Universal Charge - NPC Stranded Contract Costs", "other", "₱/kWh", "Universal charge recovery for NPC stranded contract costs.")
    elif "npc-sd" in d_lower:
        spec = ("npc_sd", "Universal Charge - NPC Stranded Debts", "other", "₱/kWh", "Universal charge recovery for NPC stranded debt obligations.")
    elif "fit-all" in d_lower:
        spec = ("fit_all", "Feed-in Tariff Allowance (FIT-All)", "other", "₱/kWh", "Uniform national subsidy supporting grid-connected renewable solar and wind.")
    elif "gea-all" in d_lower:
        spec = ("gea_all", "Green Energy Auction Allowance (GEA-All)", "other", "₱/kWh", "Green energy auction program support allowance.")

    if not spec:
        return None

    comp_id, name, category, unit, desc = spec
    if comp_id in seen_ids:
        return None
    seen_ids.add(comp_id)

    rate_kwh = round(float(rate_val), 6) if not is_per_month else 0.0
    fixed_mo = round(float(rate_val), 6) if is_per_month else 0.0

    return TEIRateComponent(
        component_id=comp_id,
        name=name,
        category=category,
        rate_per_kwh=rate_kwh,
        fixed_monthly=fixed_mo,
        vat_treatment=vat_treatment,
        vat_rate_per_kwh=vat_rate_per_kwh,
        unit=unit,
        description=desc
    )

def _extract_tei_pdf_schedule(
    pdf_bytes: bytes,
    customer_class: str = "Residential"
) -> Tuple[Optional[str], List[TEIRateComponent]]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if not full_text.strip():
        return None, []

    eff_match = re.search(r"FOR\s+THE\s+MONTH\s+OF\s+([A-Za-z]+\s+\d{4})", full_text, re.IGNORECASE)
    extracted_month = _parse_month_text(eff_match.group(1)) if eff_match else _parse_month_text(full_text)

    logical_lines: List[str] = []
    in_table = False
    for raw_line in full_text.splitlines():
        s = raw_line.strip()
        if not s:
            continue
        if s.lower().startswith("footnotes"):
            break
        if re.match(r"^1\s+Generation", s, re.IGNORECASE):
            in_table = True
        if not in_table:
            if re.match(r"^Rate\s+VA\s*T", s, re.IGNORECASE):
                in_table = True
            continue
        if s.lower().startswith("other charges"):
            continue
        if re.match(r"^\d+\s+", s):
            logical_lines.append(s)
        elif logical_lines:
            logical_lines[-1] = logical_lines[-1] + " " + s

    col_pair_idx = 1 if "small commercial" in customer_class.lower() else 0
    num_tok_re = re.compile(r"\(?-?\d[\d,]*\.\d+\)?|\d+%")

    components: List[TEIRateComponent] = []
    seen_ids: set = set()
    for line in logical_lines:
        normalized_line = re.sub(r"(?<=\.\d{4})\s+(?=\d\b)", "", line)
        toks = num_tok_re.findall(normalized_line)
        if len(toks) < 4:
            continue
        first_num = num_tok_re.search(normalized_line)
        desc_part = normalized_line[:first_num.start()].strip() if first_num else normalized_line
        pair_start = col_pair_idx * 2
        if pair_start + 1 >= len(toks):
            continue
        rate_val, _ = _parse_numeric_token(toks[pair_start])
        vat_num, vat_pct = _parse_numeric_token(toks[pair_start + 1])
        comp = _build_component_from_row(desc_part, rate_val, vat_num, vat_pct, seen_ids)
        if comp is not None:
            components.append(comp)

    return extracted_month, components

def _discover_tei_rate_candidates() -> List[Dict[str, Optional[str]]]:
    candidates: List[Dict[str, Optional[str]]] = []
    seen_pdf_urls: set = set()

    try:
        wp_raw = _http_get_bytes(TEI_WP_POSTS_API, timeout=10)
        posts = json.loads(wp_raw.decode("utf-8", errors="ignore"))
        if isinstance(posts, list):
            for p in posts:
                title = (p.get("title") or {}).get("rendered", "")
                if "rate schedule" not in title.lower():
                    continue
                content_html = (p.get("content") or {}).get("rendered", "")
                pdfs = re.findall(r'(?:https?://tarlacelectric\.com)?/wp-content/uploads/[^"\'\s<>]+\.pdf', content_html, re.IGNORECASE)
                if not pdfs:
                    continue
                pdf_url = urllib.parse.urljoin(OFFICIAL_TEI_URL, pdfs[0])
                if pdf_url in seen_pdf_urls:
                    continue
                seen_pdf_urls.add(pdf_url)
                pub_raw = str(p.get("date") or "")[:10]
                candidates.append({
                    "pdf_url": pdf_url,
                    "post_url": str(p.get("link") or OFFICIAL_TEI_URL),
                    "pub_date": pub_raw or None,
                    "month_hint": _parse_month_text(title) or _parse_month_text(pdf_url),
                })
    except Exception:
        pass

    if not candidates:
        index_bytes = _http_get_bytes(OFFICIAL_TEI_URL, timeout=12)
        index_html = index_bytes.decode("utf-8", errors="ignore")
        post_urls = re.findall(r'https?://tarlacelectric\.com/rate-schedule-of-[a-z0-9-]+', index_html, re.IGNORECASE)
        unique_posts: List[str] = []
        for u in post_urls:
            if u not in unique_posts:
                unique_posts.append(u)
        for post_url in unique_posts[:4]:
            try:
                post_html = _http_get_bytes(post_url, timeout=12).decode("utf-8", errors="ignore")
                pdfs = re.findall(r'(?:https?://tarlacelectric\.com)?/wp-content/uploads/[^"\'\s<>]+\.pdf', post_html, re.IGNORECASE)
                for raw_pdf_url in pdfs:
                    pdf_url = urllib.parse.urljoin(OFFICIAL_TEI_URL, raw_pdf_url)
                    if pdf_url in seen_pdf_urls:
                        continue
                    seen_pdf_urls.add(pdf_url)
                    candidates.append({
                        "pdf_url": pdf_url,
                        "post_url": post_url,
                        "pub_date": None,
                        "month_hint": _parse_month_text(post_url.replace("-", " ")) or _parse_month_text(pdf_url),
                    })
                    break
            except Exception:
                continue

    return candidates

def check_official_tei_rates(
    conn,
    force_fetch: bool = False,
    customer_class: Optional[str] = None,
    project_id: str = "default"
) -> Dict[str, Any]:
    target_class = (customer_class or "").strip() or "Residential"
    active_sched = get_active_rate_schedule(conn, customer_class=target_class, project_id=project_id)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    prev_gen_rate = 0.0
    for c in active_sched.components:
        if c.component_id == "gen_charge":
            prev_gen_rate = c.rate_per_kwh

    try:
        candidates = _discover_tei_rate_candidates()
        for cand in candidates[:3]:
            pdf_url = cand.get("pdf_url")
            if not pdf_url:
                continue
            try:
                pdf_bytes = _http_get_bytes(pdf_url, timeout=15)
            except Exception:
                continue

            doc_hash = compute_document_hash(pdf_bytes)
            extracted_month, parsed_comps = _extract_tei_pdf_schedule(pdf_bytes, customer_class=target_class)
            gen_comp = next((c for c in parsed_comps if c.component_id == "gen_charge"), None)
            if not gen_comp or gen_comp.rate_per_kwh <= 0.0 or len(parsed_comps) < 10:
                continue

            extracted_gen = gen_comp.rate_per_kwh
            effective_month = extracted_month or cand.get("month_hint") or datetime.datetime.now().strftime("%Y-%m")
            pub_date = cand.get("pub_date") or datetime.datetime.now().strftime("%Y-%m-%d")

            is_unconfigured = (
                active_sched.verification_status == "unconfigured"
                or prev_gen_rate <= 0.0
            )
            has_changes = (
                is_unconfigured
                or doc_hash != active_sched.document_hash
                or effective_month != active_sched.effective_month
                or active_sched.customer_class.lower() != target_class.lower()
                or abs(extracted_gen - prev_gen_rate) > 0.00001
            )

            if has_changes:
                slug_class = target_class.lower().replace(" ", "_")
                new_sched = TEIRateSchedule(
                    id=f"tei-rate-{effective_month}-{slug_class}",
                    effective_month=effective_month,
                    customer_class=target_class,
                    publication_date=pub_date,
                    source_url=pdf_url,
                    document_hash=doc_hash,
                    verification_status="verified",
                    components=parsed_comps,
                    created_at=now_iso
                )
                save_rate_schedule(new_sched, conn, project_id="global")
                set_project_active_schedule(conn, project_id, target_class, new_sched.id)

                diff = round(extracted_gen - prev_gen_rate, 5)
                direction = "increased" if diff > 0 else "decreased"
                if prev_gen_rate > 0:
                    summary_msg = f"TEI published a new electricity rate ({effective_month}). Generation Charge {direction} by ₱{abs(diff):.5f}/kWh to ₱{extracted_gen:.5f}/kWh. SolarScope updated your estimated bill."
                else:
                    summary_msg = f"Loaded official TEI {effective_month} {target_class} schedule (Generation Charge ₱{extracted_gen:.5f}/kWh)."
                alert = {
                    "has_changed": True,
                    "previous_rate": prev_gen_rate,
                    "new_rate": extracted_gen,
                    "difference_per_kwh": diff,
                    "effective_month": effective_month,
                    "publication_date": pub_date,
                    "summary": summary_msg
                }
                res_payload = {
                    "status": "updated",
                    "message": summary_msg,
                    "active_schedule": new_sched,
                    "rate_change_alert": alert,
                    "checked_at": now_iso
                }
                save_rate_check_state(res_payload, conn, project_id=project_id)
                return res_payload

            res_payload = {
                "status": "verified_current",
                "message": f"TEI official rate schedule ({effective_month}) checked. Current rates are up to date.",
                "active_schedule": active_sched,
                "rate_change_alert": None,
                "checked_at": now_iso
            }
            save_rate_check_state(res_payload, conn, project_id=project_id)
            return res_payload

        if prev_gen_rate <= 0.0 or active_sched.verification_status == "unconfigured":
            res_payload = {
                "status": "offline_unconfigured",
                "message": "Unable to extract rate schedule from tarlacelectric.com. Try again shortly or add a custom rate schedule below.",
                "active_schedule": active_sched,
                "rate_change_alert": None,
                "checked_at": now_iso
            }
            save_rate_check_state(res_payload, conn, project_id=project_id)
            return res_payload

        res_payload = {
            "status": "offline_retained_verified",
            "message": "Unable to parse latest TEI schedule right now. Retained your active schedule.",
            "active_schedule": active_sched,
            "rate_change_alert": None,
            "checked_at": now_iso
        }
        save_rate_check_state(res_payload, conn, project_id=project_id)
        return res_payload

    except Exception:
        if prev_gen_rate <= 0.0 or active_sched.verification_status == "unconfigured":
            res_payload = {
                "status": "offline_unconfigured",
                "message": "Unable to connect to tarlacelectric.com right now. Try again shortly or enter a custom rate schedule.",
                "active_schedule": active_sched,
                "rate_change_alert": None,
                "checked_at": now_iso
            }
            save_rate_check_state(res_payload, conn, project_id=project_id)
            return res_payload
        res_payload = {
            "status": "offline_retained_verified",
            "message": "Unable to check for new TEI rates. Your estimate is using the last verified rate schedule.",
            "active_schedule": active_sched,
            "rate_change_alert": None,
            "checked_at": now_iso
        }
        save_rate_check_state(res_payload, conn, project_id=project_id)
        return res_payload
