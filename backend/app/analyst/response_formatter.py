from typing import Dict, Any, List

def format_diagnostic_response(diag: Dict[str, Any]) -> str:
    parts = []

    main_finding = diag.get("main_finding", "")
    if main_finding:
        parts.append(f"**Key Finding:** {main_finding}\n")

    explanation = diag.get("detailed_explanation", "")
    if explanation:
        parts.append(f"**What Happened & Why:**\n{explanation}\n")

    evidence: List[str] = diag.get("supporting_evidence", [])
    if evidence:
        parts.append("**Supporting Evidence & Measurements:**")
        for ev in evidence:
            parts.append(f"- {ev}")
        parts.append("")

    other_causes = diag.get("other_possible_causes", [])
    if other_causes:
        parts.append("**Other Possibilities Evaluated:**")
        for oc in other_causes:
            cause_name = oc.get("cause", "")
            cause_conf = oc.get("confidence", "Possible")
            parts.append(f"- **{cause_name}** ({cause_conf}): {oc.get('explanation', '')}")
        parts.append("")

    recs: List[str] = diag.get("recommendations", [])
    if recs:
        parts.append("**Practical Recommendations:**")
        for r in recs:
            parts.append(f"- {r}")
        parts.append("")

    conf = diag.get("confidence_level", "Confirmed")
    parts.append(f"**Diagnostic Confidence:** `{conf}` (Grounded in physical inverter measurements & Deye Open MCP records)")

    return "\n".join(parts)

