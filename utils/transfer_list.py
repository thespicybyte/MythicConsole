def move_selected(src: list[str], dst: list[str], selected: set[str]) -> tuple[list[str], list[str]]:
    moved = [x for x in src if x in selected]
    return [x for x in src if x not in selected], dst + moved


def move_all(src: list[str], dst: list[str]) -> tuple[list[str], list[str]]:
    return [], dst + src


def compute_active_changes(initial_active: dict[str, bool], final_shown: set[str]) -> dict[str, bool]:
    """initial_active: uuid -> was it active at open. final_shown: uuids now in the LEFT (Shown) pane.
    Returns uuid -> new_active ONLY for callbacks whose active value changed (the mutations to issue)."""
    return {u: (u in final_shown) for u, was in initial_active.items() if (u in final_shown) != was}
