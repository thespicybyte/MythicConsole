from textual.app import App, ComposeResult

from widgets.transfer_selection import (
    CHECKED,
    UNCHECKED,
    GlyphCheckbox,
    CheckSelection,
    CheckSelectionList,
)


class _App(App):
    def compose(self) -> ComposeResult:
        yield GlyphCheckbox("select all", id="cb")
        sl = CheckSelectionList(id="sl")
        sl.add_option(CheckSelection("first", "a"))
        sl.add_option(CheckSelection("second", "b"))
        yield sl


async def test_glyph_checkbox_empty_box_when_unchecked_filled_when_checked():
    app = _App()
    async with app.run_test() as pilot:
        cb = app.query_one("#cb", GlyphCheckbox)
        assert cb.BUTTON_INNER == UNCHECKED
        cb.value = True
        await pilot.pause()
        assert cb.BUTTON_INNER == CHECKED


async def test_glyph_checkbox_has_no_brackets():
    app = _App()
    async with app.run_test() as pilot:
        cb = app.query_one("#cb", GlyphCheckbox)
        rendered = cb._button.plain
        assert "[" not in rendered
        assert "]" not in rendered


async def test_check_selection_list_rows_are_single_line_and_adjacent():
    app = _App()
    async with app.run_test(size=(40, 10)) as pilot:
        sl = app.query_one("#sl", CheckSelectionList)
        await pilot.pause()

        row0 = "".join(seg.text for seg in sl.render_line(0))
        row1 = "".join(seg.text for seg in sl.render_line(1))

        assert "first" in row0
        assert "second" in row1


async def test_check_selection_list_checkbox_has_no_brackets():
    app = _App()
    async with app.run_test(size=(40, 10)) as pilot:
        sl = app.query_one("#sl", CheckSelectionList)
        await pilot.pause()

        row0 = "".join(seg.text for seg in sl.render_line(0))
        assert "[" not in row0
        assert "]" not in row0


async def test_check_selection_list_shows_check_mark_only_when_selected():
    app = _App()
    async with app.run_test(size=(40, 10)) as pilot:
        sl = app.query_one("#sl", CheckSelectionList)
        await pilot.pause()

        unselected_row = "".join(seg.text for seg in sl.render_line(0))
        assert CHECKED not in unselected_row
        assert UNCHECKED in unselected_row

        sl.select("a")
        await pilot.pause()
        selected_row = "".join(seg.text for seg in sl.render_line(0))
        assert CHECKED in selected_row


async def test_keyboard_navigation_highlights_cursor_row_and_mouse_clears_it():
    app = _App()
    async with app.run_test(size=(40, 10)) as pilot:
        sl = app.query_one("#sl", CheckSelectionList)
        await pilot.pause()

        cursor_bg = sl.get_component_rich_style("check-selection-list--cursor").bgcolor

        assert sl._keyboard_cursor is False
        sl.action_cursor_down()
        await pilot.pause()
        assert sl._keyboard_cursor is True

        highlighted = sl.render_line(sl.highlighted)
        assert any(seg.style and seg.style.bgcolor == cursor_bg for seg in highlighted)

        sl._use_mouse_cursor()
        await pilot.pause()
        assert sl._keyboard_cursor is False
        plain = sl.render_line(sl.highlighted)
        assert not any(seg.style and seg.style.bgcolor == cursor_bg for seg in plain)


async def test_click_selects_row_and_clears_keyboard_cursor():
    app = _App()
    async with app.run_test(size=(40, 10)) as pilot:
        sl = app.query_one("#sl", CheckSelectionList)
        await pilot.pause()

        sl.action_cursor_down()  # keyboard cursor active
        await pilot.pause()
        assert sl._keyboard_cursor is True

        scr = sl.scrollable_content_region
        await pilot.click(offset=(scr.x + 5, scr.y))  # click the first row
        await pilot.pause()

        assert "a" in sl.selected
        assert sl._keyboard_cursor is False
