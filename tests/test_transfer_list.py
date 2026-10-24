from utils.transfer_list import compute_active_changes, move_all, move_selected


def test_move_selected_moves_only_selected_and_preserves_order():
    src, dst = move_selected(["a", "b", "c"], ["x"], {"b"})
    assert src == ["a", "c"]
    assert dst == ["x", "b"]


def test_move_selected_with_empty_selection_is_a_noop():
    src, dst = move_selected(["a", "b"], ["x"], set())
    assert src == ["a", "b"]
    assert dst == ["x"]


def test_move_selected_preserves_source_order_for_multiple_moves():
    src, dst = move_selected(["a", "b", "c", "d"], [], {"a", "c"})
    assert src == ["b", "d"]
    assert dst == ["a", "c"]


def test_move_all_moves_everything_and_empties_source():
    src, dst = move_all(["a", "b"], ["x"])
    assert src == []
    assert dst == ["x", "a", "b"]


def test_move_all_from_empty_source():
    src, dst = move_all([], ["x"])
    assert src == []
    assert dst == ["x"]


def test_compute_active_changes_only_includes_side_changers():
    initial = {"a": True, "b": True, "c": False}
    final_shown = {"a"}  # b moved to hidden, c stayed hidden

    changes = compute_active_changes(initial, final_shown)

    assert changes == {"b": False}


def test_compute_active_changes_hidden_to_shown_gives_true():
    initial = {"a": False}
    final_shown = {"a"}

    changes = compute_active_changes(initial, final_shown)

    assert changes == {"a": True}


def test_compute_active_changes_moved_out_and_back_yields_no_change():
    initial = {"a": True}
    final_shown = {"a"}  # moved to hidden pane and back to shown before Apply

    changes = compute_active_changes(initial, final_shown)

    assert changes == {}


def test_compute_active_changes_untouched_callbacks_absent_from_result():
    initial = {"a": True, "b": False}
    final_shown = {"a"}

    changes = compute_active_changes(initial, final_shown)

    assert "a" not in changes
    assert "b" not in changes
    assert changes == {}
