from textual.binding import Binding

from mythic_console.screens.home import Home


def _bindings_for_key(key: str) -> list[Binding]:
    return [b for b in Home.BINDINGS if isinstance(b, Binding) and b.key == key]


def test_alt_tab_maps_to_next_tab_and_is_hidden():
    bindings = _bindings_for_key("alt+tab")
    assert len(bindings) == 1
    assert bindings[0].action == "next_tab"
    assert bindings[0].show is False


def test_alt_shift_tab_maps_to_previous_tab_and_is_hidden():
    bindings = _bindings_for_key("alt+shift+tab")
    assert len(bindings) == 1
    assert bindings[0].action == "previous_tab"
    assert bindings[0].show is False


def test_existing_pageup_pagedown_tab_bindings_still_present():
    pageup = _bindings_for_key("ctrl+pageup")
    pagedown = _bindings_for_key("ctrl+pagedown")
    assert len(pageup) == 1 and pageup[0].action == "next_tab"
    assert len(pagedown) == 1 and pagedown[0].action == "previous_tab"
