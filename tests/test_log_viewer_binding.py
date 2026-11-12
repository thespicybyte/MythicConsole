from textual.binding import Binding

from mythic_console.screens.home import Home


def test_f2_binding_is_registered_and_maps_to_toggle_log_viewer():
    bindings = [b for b in Home.BINDINGS if isinstance(b, Binding) and b.action == "toggle_log_viewer"]
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.key == "f2"
    assert binding.key_display == "F2"
    assert binding.show is True
