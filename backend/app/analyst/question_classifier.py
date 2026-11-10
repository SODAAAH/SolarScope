import re
import datetime
from typing import Dict, Any, Optional

MANILA_TZ = datetime.timezone(datetime.timedelta(hours=8))

class QuestionClassifier:
    def classify(self, query: str) -> Dict[str, Any]:
        text = query.strip().lower()

        is_investigation = any(kw in text for kw in [
            "why", "what caused", "how come", "reason", "investigate",
            "explain why", "unusual", "unexpected", "alert", "fault",
            "warning", "error", "drop", "dropped", "stopped", "drained",
            "draining", "inefficient", "discharging fast", "purchased even though",
            "bought even though", "buying even though", "operating limit", "clipped", "clipping"
        ])

        is_hybrid = any(kw in text for kw in [
            "compare", "comparison", "difference between", "versus", "vs",
            "should i add", "add battery", "add solar", "upgrade",
            "what happened between", "between"
        ])

        date_info = self._extract_date(text)
        metric_info = self._extract_metric(text)

        if is_investigation:
            path = "DEEP_INVESTIGATION"
            intent = self._detect_investigation_intent(text)
        elif is_hybrid:
            path = "HYBRID"
            intent = "HYBRID_ANALYSIS"
        elif metric_info != "UNKNOWN" or any(kw in text for kw in ["how much", "what is", "what was", "show", "summary", "average", "total", "highest", "peak", "lowest"]):
            path = "FAST_PATH"
            intent = f"METRIC_{metric_info}"
        else:
            if len(text.split()) < 3 and not any(k in text for k in ["solar", "battery", "grid", "bill", "health"]):
                path = "CLARIFICATION_REQUIRED"
                intent = "AMBIGUOUS"
            else:
                path = "FAST_PATH"
                intent = "GENERAL_SUMMARY"

        return {
            "path": path,
            "intent": intent,
            "metric": metric_info,
            "date_info": date_info,
            "raw_query": query
        }

    def _extract_metric(self, text: str) -> str:
        if any(w in text for w in ["station", "health", "system status", "logger", "inverter online", "overview"]):
            return "STATION_HEALTH"
        if any(w in text for w in ["bill", "electricity bill", "cost", "tariff", "estimate", "pesos", "php", "tei bill"]):
            return "BILL_ESTIMATE"
        if any(w in text for w in ["battery", "charge level", "soc", "stored", "usable energy", "reserve"]):
            return "BATTERY"
        if any(w in text for w in ["solar", "generation", "panels", "produced", "production", "sun", "pv"]):
            return "SOLAR"
        if any(w in text for w in ["grid", "tei", "purchased", "bought", "imported", "import", "utility"]):
            return "GRID_IMPORT"
        if any(w in text for w in ["household", "consumption", "load", "used", "consumed", "home"]):
            return "CONSUMPTION"
        if any(w in text for w in ["export", "feed-in", "sold", "feed in"]):
            return "EXPORT"
        return "UNKNOWN"

    def _extract_date(self, text: str) -> Dict[str, Any]:
        now_manila = datetime.datetime.now(MANILA_TZ)
        today_date = now_manila.date()
        yesterday_date = today_date - datetime.timedelta(days=1)

        date_match = re.search(r"\b(202\d[-/]\d{1,2}[-/]\d{1,2})\b", text)
        if date_match:
            d_str = date_match.group(1).replace("/", "-")
            return {"date_str": d_str, "type": "EXACT_DATE"}

        day_num_match = re.search(r"\bday\s*(\d{1,2})\b", text)
        if day_num_match:
            d_num = int(day_num_match.group(1))
            if 1 <= d_num <= 31:
                d_str = f"{now_manila.year}-{now_manila.month:02d}-{d_num:02d}"
                return {"date_str": d_str, "type": "EXACT_DATE"}

        if "yesterday" in text:
            return {"date_str": yesterday_date.isoformat(), "type": "YESTERDAY"}
        if "today" in text or "now" in text or "current" in text:
            return {"date_str": today_date.isoformat(), "type": "TODAY"}
        if "last night" in text or "overnight" in text or "night" in text:
            return {"date_str": yesterday_date.isoformat(), "type": "NIGHTTIME"}
        if "this week" in text:
            return {"date_str": "WEEK", "type": "RANGE_WEEK"}
        if "this month" in text or "monthly" in text:
            return {"date_str": "MONTH", "type": "RANGE_MONTH"}

        return {"date_str": yesterday_date.isoformat(), "type": "DEFAULT_RECENT"}

    def _detect_investigation_intent(self, text: str) -> str:
        if any(w in text for w in ["battery drain", "discharge fast", "draining", "depleted", "ran out", "stop charging", "stopped charging"]):
            return "BATTERY_DRAIN_INVESTIGATION"
        if any(w in text for w in ["grid", "tei", "purchased", "bought", "importing", "even though battery"]):
            return "GRID_IMPORT_INVESTIGATION"
        if any(w in text for w in ["solar low", "production drop", "less solar", "lower yesterday", "low generation"]):
            return "SOLAR_DROP_INVESTIGATION"
        if any(w in text for w in ["alert", "fault", "warning", "error", "recurring"]):
            return "INVERTER_ALERT_INVESTIGATION"
        if any(w in text for w in ["efficiency", "efficient", "using solar efficiently", "loss"]):
            return "EFFICIENCY_INVESTIGATION"
        if any(w in text for w in ["limit", "clipping", "rated", "overload"]):
            return "INVERTER_LIMIT_INVESTIGATION"
        return "GENERAL_ROOT_CAUSE"

