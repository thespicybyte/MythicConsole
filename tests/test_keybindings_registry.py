from textual.binding import Binding

from mythic_console.screens.build_summary import BuildSummary
from mythic_console.screens.forms import ParamForm
from mythic_console.screens.home import Home
from mythic_console.screens.login import LoginScreen
from mythic_console.screens.manage_callbacks import ManageCallbacks
from mythic_console.screens.prompts import ChoicePrompt, FilePrompt, YesNoPrompt
from mythic_console.screens.select_commands import SelectCommands
from mythic_console.utils.keybindings import REBINDABLE_ACTIONS
from mythic_console.widgets.callbacks import CallbackTable


def _bindings(namespace) -> list[Binding]:
    return [binding for binding in namespace.BINDINGS if isinstance(binding, Binding)]


def _all_rebindable_bindings() -> list[Binding]:
    bindings = []
    bindings.extend(_bindings(Home))
    bindings.extend(_bindings(LoginScreen))
    bindings.extend(_bindings(CallbackTable))
    return bindings


def test_every_registry_id_maps_to_binding_with_matching_default_key():
    bindings_by_id: dict[str, list[Binding]] = {}
    for binding in _all_rebindable_bindings():
        if binding.id is None:
            continue
        bindings_by_id.setdefault(binding.id, []).append(binding)

    for action in REBINDABLE_ACTIONS:
        matches = bindings_by_id.get(action.id, [])
        assert matches, f"no binding found for registry id '{action.id}'"
        expected_count = 2 if action.id == "manage_callbacks" else 1
        assert len(matches) == expected_count, f"'{action.id}' expected {expected_count} binding(s), found {len(matches)}"
        for binding in matches:
            assert binding.key == action.default_key, (
                f"'{action.id}' binding key '{binding.key}' does not match registry default '{action.default_key}'"
            )


def test_every_binding_with_id_is_in_registry():
    registry_ids = {action.id for action in REBINDABLE_ACTIONS}
    for binding in _all_rebindable_bindings():
        if binding.id is None:
            continue
        assert binding.id in registry_ids, f"binding id '{binding.id}' is not in the rebindable registry"


def test_home_and_login_and_callbacktable_bindings_all_carry_ids():
    for binding in _all_rebindable_bindings():
        assert binding.id is not None, f"binding for action '{binding.action}' has no id"


def test_fixed_modal_bindings_carry_no_id():
    fixed_namespaces = (ParamForm, FilePrompt, YesNoPrompt, ChoicePrompt, ManageCallbacks, SelectCommands,
                        BuildSummary)
    for namespace in fixed_namespaces:
        for binding in _bindings(namespace):
            assert binding.id is None, f"{namespace.__name__} binding for '{binding.action}' should have no id"


def test_no_two_registry_ids_share_a_default_key_within_a_namespace():
    keys_by_namespace: dict[str, dict[str, str]] = {}
    for action in REBINDABLE_ACTIONS:
        namespace_keys = keys_by_namespace.setdefault(action.namespace, {})
        assert action.default_key not in namespace_keys.values(), (
            f"'{action.id}' default key '{action.default_key}' clashes with another id "
            f"in namespace '{action.namespace}'"
        )
        namespace_keys[action.id] = action.default_key
