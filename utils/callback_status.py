import json
from datetime import datetime, timezone
from typing import Optional

STREAMING_SENTINEL = "1970-01-01T00:00:00"

STATUS_GLYPHS = {
    "streaming": "[cyan]⇅[/]",
    "alive": "[green]●[/]",
    "late": "[yellow]●[/]",
    "dead": "[red]☠[/]",
}


def parse_mythic_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse a Mythic timestamp (naive UTC, with or without microseconds/Z) into an aware datetime."""
    if not value:
        return None

    text = value.strip().rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def is_streaming(last_checkin: Optional[str]) -> bool:
    return bool(last_checkin) and last_checkin.startswith(STREAMING_SENTINEL)


def _as_aware(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def format_relative(last_checkin: Optional[str], now: datetime) -> str:
    parsed = parse_mythic_timestamp(last_checkin)
    if parsed is None:
        return "?"

    seconds = max(0, int((_as_aware(now) - parsed).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"

    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"

    days = hours // 24
    return f"{days}d"


def checkin_text(last_checkin: Optional[str], now: datetime) -> str:
    if is_streaming(last_checkin):
        return "streaming"
    return format_relative(last_checkin, now)


def display_ip(ip: Optional[list], external_ip: Optional[str] = None) -> str:
    """ip[0] is the operator-selected IP (encoded by list order); remaining entries collapse to +N."""
    if not ip:
        return external_ip or ""

    extra = len(ip) - 1
    if extra > 0:
        return f"{ip[0]} +{extra}"
    return ip[0]


def parse_sleep_window(sleep_info: Optional[str]) -> Optional[float]:
    """sleep_info is a JSON string keyed by C2-profile name. Returns the widest expected sleep
    window (interval * (1 + jitter / 100)) across profiles, or None if empty/unparseable."""
    if not sleep_info:
        return None

    try:
        profiles = json.loads(sleep_info)
    except (TypeError, ValueError):
        return None

    if not isinstance(profiles, dict) or not profiles:
        return None

    windows = []
    for profile in profiles.values():
        if not isinstance(profile, dict):
            continue
        interval = profile.get("interval")
        if not isinstance(interval, (int, float)):
            continue
        jitter = profile.get("jitter", 0)
        if not isinstance(jitter, (int, float)):
            jitter = 0
        windows.append(interval * (1 + jitter / 100))

    if not windows:
        return None
    return max(windows)


def alive_state(dead: bool, last_checkin: Optional[str], sleep_info: Optional[str], now: datetime) -> str:
    """Four-state status: streaming > dead > late > alive."""
    if is_streaming(last_checkin):
        return "streaming"

    if dead:
        return "dead"

    expected = parse_sleep_window(sleep_info)
    if expected is not None:
        parsed = parse_mythic_timestamp(last_checkin)
        if parsed is not None and (_as_aware(now) - parsed).total_seconds() > expected:
            return "late"

    return "alive"


def status_glyph(state: str) -> str:
    return STATUS_GLYPHS.get(state, "")


def count_active(known_callbacks: dict) -> tuple[int, int]:
    """known_callbacks: uuid -> active. Returns (active_count, total_count)."""
    active = sum(1 for is_active in known_callbacks.values() if is_active)
    return active, len(known_callbacks)
