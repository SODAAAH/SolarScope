import json
from pathlib import Path
from typing import Dict, Any

def export_json_report(
    data: Dict[str, Any],
    output_path: str | Path
) -> Path:
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return target_path
