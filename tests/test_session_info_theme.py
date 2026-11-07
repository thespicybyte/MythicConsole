import types
import importlib.resources

import pytest
from textual.app import App, ComposeResult
from textual.content import Content
from textual.widgets import Static

from mythic_console.widgets.session_info import _KEY_STYLE, _VALUE_STYLE, SessionInfo

CSS_PATH = str(importlib.resources.files("mythic_console") / "mythic.tcss")

THEMES = ["textual-dark", "textual-light", "nord"]


class _FakeOperation:
    name = "TestOp"

    async def query(self) -> None:
        pass


def _fake_session_instance():
    async def _get_server_version() -> str:
        return "v3.3"

    return types.SimpleNamespace(
        username="operator1",
        url="https://127.0.0.1:7443",
        mythic=types.SimpleNamespace(current_operation_id=5),
        get_server_version=_get_server_version,
    )


class _SessionInfoHarness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance, operation):
        super().__init__()
        self._instance = instance
        self._operation = operation
        self.session_info: SessionInfo | None = None
        self.ref_key: Static | None = None
        self.ref_value: Static | None = None

    def compose(self) -> ComposeResult:
        self.session_info = SessionInfo(self._instance, self._operation)
        yield self.session_info
        # Independently-built reference content, resolved the same way, to pin down what
        # the theme's $primary/$text actually render to without hardcoding the math.
        self.ref_key = Static(Content.assemble(("REF", _KEY_STYLE)))
        yield self.ref_key
        self.ref_value = Static(Content.assemble(("REF", _VALUE_STYLE)))
        yield self.ref_value


def _first_segment_colors(static: Static):
    segments = static.render_line(0)._segments
    return [segment.style.color for segment in segments]


# ----- builder is theme-token based (unit) -----


async def test_builder_uses_theme_tokens_not_literal_colors():
    async with App().run_test():
        widget = SessionInfo(_fake_session_instance(), _FakeOperation())
        widget.session_info["current_operation"] = "TestOp"
        widget.session_info["mythic_server_version"] = "v3.3"

        content = widget._session_content()

    styles = {span.style for span in content.spans}
    assert styles == {_KEY_STYLE, _VALUE_STYLE}
    for style in styles:
        assert "$" in style


async def test_builder_does_not_parse_value_markup():
    async with App().run_test():
        widget = SessionInfo(_fake_session_instance(), _FakeOperation())
        widget.session_info["current_operation"] = "TestOp"
        widget.session_info["mythic_server_version"] = "v3.3"

        content = widget._session_content()

    assert "server_url: https://127.0.0.1:7443" in content.plain


# ----- literals follow the theme and recolor (Pilot) -----


@pytest.mark.parametrize("theme", THEMES)
async def test_literals_track_theme_colors(theme):
    app = _SessionInfoHarness(_fake_session_instance(), _FakeOperation())
    async with app.run_test() as pilot:
        app.theme = theme
        await pilot.pause()

        inner = app.session_info.query_one(Static)
        key_color, value_color = _first_segment_colors(inner)
        ref_key_color = _first_segment_colors(app.ref_key)[0]
        ref_value_color = _first_segment_colors(app.ref_value)[0]

        assert key_color == ref_key_color
        assert value_color == ref_value_color


async def test_literals_recolor_when_theme_changes():
    app = _SessionInfoHarness(_fake_session_instance(), _FakeOperation())
    async with app.run_test() as pilot:
        inner = app.session_info.query_one(Static)

        colors_by_theme = {}
        for theme in THEMES:
            app.theme = theme
            await pilot.pause()
            colors_by_theme[theme] = tuple(_first_segment_colors(inner))

        assert colors_by_theme["textual-dark"] != colors_by_theme["textual-light"]
        assert colors_by_theme["textual-dark"] != colors_by_theme["nord"]


# ----- not the old fixed colors -----


async def test_literals_are_not_rich_default_green_or_cyan():
    app = _SessionInfoHarness(_fake_session_instance(), _FakeOperation())
    async with app.run_test() as pilot:
        inner = app.session_info.query_one(Static)
        default_green = (0x00, 0x80, 0x00)
        default_cyan = (0x00, 0xFF, 0xFF)

        for theme in THEMES:
            app.theme = theme
            await pilot.pause()
            for color in _first_segment_colors(inner):
                triplet = (color.triplet.red, color.triplet.green, color.triplet.blue)
                assert triplet != default_green
                assert triplet != default_cyan
