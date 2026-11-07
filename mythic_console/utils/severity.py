from enum import Enum

from rich.text import Text
from textual.app import active_app


class Severity(str, Enum):
    """The three outcome severities a console message can carry."""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


_FALLBACK = {
    Severity.SUCCESS: "green",
    Severity.WARNING: "yellow",
    Severity.ERROR: "red",
}


def severity_style(severity: Severity) -> str:
    """The Rich style string for a severity: the active Textual theme's matching color, or a
    named fallback when no app is running."""
    try:
        color = getattr(active_app.get().current_theme, severity.value)
    except LookupError:
        color = None
    return color or _FALLBACK[severity]


def styled(severity: Severity, message: str) -> Text:
    """`message` rendered as a Rich Text styled for the given severity."""
    return Text(message, style=severity_style(severity))


def success(message: str) -> Text:
    """`message` styled as a success outcome."""
    return styled(Severity.SUCCESS, message)


def warning(message: str) -> Text:
    """`message` styled as a warning outcome."""
    return styled(Severity.WARNING, message)


def error(message: str) -> Text:
    """`message` styled as an error outcome."""
    return styled(Severity.ERROR, message)
