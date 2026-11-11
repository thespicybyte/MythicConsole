from mythic_console.backend.mythic_agent.mythic_agent import MythicCommands
from mythic_console.backend.mythic_instance.mythic_instance import MythicInstance
from mythic_console.screens.home import Home


def test_monitor_operation_updates_removed_from_instance():
    assert not hasattr(MythicInstance, "monitor_operation_updates")


def test_home_no_longer_starts_an_operation_monitor_worker():
    assert not hasattr(Home, "_monitor_operation_updates")


def test_set_operation_cache_replaces_in_place():
    cache_id = id(MythicCommands._operation_cache)

    MythicCommands.set_operation_cache(["op1", "op2"])

    assert MythicCommands._operation_cache == ["op1", "op2"]
    assert id(MythicCommands._operation_cache) == cache_id


def test_set_operation_cache_visible_to_other_instances(fake_instance):
    MythicCommands.set_operation_cache(["op1"])

    other = MythicCommands(fake_instance)

    assert other._operation_cache == ["op1"]
