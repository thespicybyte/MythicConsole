from textual.app import App

from mythic_console.utils.severity import Severity, error, severity_style, success, warning


def test_success_returns_plain_text():
    assert success("ok").plain == "ok"


def test_warning_returns_plain_text():
    assert warning("careful").plain == "careful"


def test_error_returns_plain_text():
    assert error("boom").plain == "boom"


def test_severity_style_falls_back_without_running_app():
    assert severity_style(Severity.SUCCESS) == "green"
    assert severity_style(Severity.WARNING) == "yellow"
    assert severity_style(Severity.ERROR) == "red"


async def test_severity_style_tracks_running_app_theme():
    app = App()
    async with app.run_test():
        app.theme = "nord"
        theme = app.current_theme
        assert severity_style(Severity.SUCCESS) == theme.success
        assert severity_style(Severity.WARNING) == theme.warning
        assert severity_style(Severity.ERROR) == theme.error


def test_success_style_matches_severity_style():
    assert success("ok").style == severity_style(Severity.SUCCESS)


def test_warning_style_matches_severity_style():
    assert warning("careful").style == severity_style(Severity.WARNING)


def test_error_style_matches_severity_style():
    assert error("boom").style == severity_style(Severity.ERROR)
