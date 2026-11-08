import types

from mythic_console.backend.operation.operation import Operation


def test_update_populates_disabled_commands_profiles_without_raising():
    operation = Operation(types.SimpleNamespace(mythic=None), operation_id=1)

    operation._update({"disabledcommandsprofiles": [{"id": 3}, {"id": 4}, {}]})

    assert operation.disabled_commands_profiles == [3, 4]
