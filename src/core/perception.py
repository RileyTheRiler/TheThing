"""Shared helpers for perception-related event payloads.

These utilities keep event payloads consistent across systems by
standardizing actor/observer fields, location data, noise levels, and
derived severity labels.
"""

from typing import Dict, Optional, Tuple


def _resolve_location(payload: Dict) -> Optional[Tuple[int, int]]:
    """Extract a best-effort location tuple from a payload."""

    # Direct fields should win first
    if payload.get("location"):
        return payload["location"]

    if payload.get("target_location"):
        return payload["target_location"]

    actor_ref = payload.get("actor_ref") or payload.get("player_ref")
    if actor_ref is not None and hasattr(actor_ref, "location"):
        return getattr(actor_ref, "location")

    opponent_ref = payload.get("observer_ref") or payload.get("opponent_ref")
    if opponent_ref is not None and hasattr(opponent_ref, "location"):
        return getattr(opponent_ref, "location")

    return None


def _calculate_noise(payload: Dict) -> int:
    """Determine the noise level for a perception payload."""

    if payload.get("noise_level") is not None:
        return int(payload["noise_level"])

    actor_ref = payload.get("actor_ref") or payload.get("player_ref")
    if actor_ref is not None and hasattr(actor_ref, "get_noise_level"):
        try:
            return int(actor_ref.get_noise_level())
        except Exception:
            return 0

    return 0


def severity_from_noise(noise_level: Optional[int]) -> str:
    """Normalize severity strings based on a noise level.

    Returns one of: "low", "medium", "high", "extreme".
    """

    if noise_level is None:
        return "low"

    if noise_level >= 10:
        return "extreme"
    if noise_level >= 6:
        return "high"
    if noise_level >= 3:
        return "medium"
    return "low"


def normalize_perception_payload(payload: Dict) -> Dict:
    """Return a copy of the payload with normalized perception fields.

    The normalized payload always includes:
    - actor/opponent names and references
    - room and location when resolvable
    - noise_level and a derived severity label
    """

    normalized = dict(payload)

    actor_ref = payload.get("actor_ref") or payload.get("player_ref")
    opponent_ref = payload.get("observer_ref") or payload.get("opponent_ref")

    if actor_ref and "actor" not in normalized:
        normalized["actor"] = getattr(actor_ref, "name", None)
    if opponent_ref and "observer" not in normalized:
        normalized["observer"] = getattr(opponent_ref, "name", None)

    # Preserve legacy keys while also ensuring the normalized ones exist
    normalized.setdefault("actor_ref", actor_ref)
    normalized.setdefault("player_ref", actor_ref)
    normalized.setdefault("opponent_ref", opponent_ref)
    normalized.setdefault("observer_ref", opponent_ref)
    if opponent_ref and "opponent" not in normalized:
        normalized["opponent"] = getattr(opponent_ref, "name", None)

    location = _resolve_location(normalized)
    if location:
        normalized["location"] = location

    if "room" not in normalized and location and payload.get("game_state"):
        station_map = getattr(payload["game_state"], "station_map", None)
        if station_map and hasattr(station_map, "get_room_name"):
            normalized["room"] = station_map.get_room_name(*location)

    noise_level = _calculate_noise(normalized)
    normalized["noise_level"] = noise_level
    normalized["severity"] = severity_from_noise(noise_level)

    if "source" not in normalized:
        normalized["source"] = "perception"

    return normalized
