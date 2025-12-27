import json
from pathlib import Path
from typing import Dict, Any


class DesignBriefRegistry:
    """
    Loads lightweight design brief metadata that maps systems to EventTypes
    and JSON-driven hooks. This keeps systems configurable while preserving
    event-driven decoupling.
    """

    def __init__(self, path: Path | None = None):
        base_path = Path(__file__).resolve().parents[2]
        self.path = path or base_path / "config" / "design_briefs.json"
        self.briefs: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}

    def get_brief(self, key: str) -> Dict[str, Any]:
        """Return a brief section or an empty mapping if missing."""
        return self.briefs.get(key, {})

    def event_type_name(self, key: str) -> str | None:
        """Shortcut to get the configured EventType name for a system key."""
        brief = self.get_brief(key)
        return brief.get("event_type")
