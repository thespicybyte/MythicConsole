import asyncio

import pytest
from mythic import mythic as mythic_module

from mythic_console.backend.mythic_agent.mythic_agent import MythicCommands
from mythic_console.backend.mythic_instance.mythic_instance import MythicInstance


@pytest.fixture
def instance():
    inst = MythicInstance(username="operator", password="hunter2", url="https://mythic.test")
    inst.mythic = object()
    return inst


async def test_monitor_operation_updates_yields_names(instance, monkeypatch):
    """No deleted filter is sent: the production query intentionally omits `where`, to match
    the no-filter fallback (get_all_operation_names / operation list)."""
    async def fake_subscribe(session, query):
        yield {"operation": [{"name": "op1"}, {"name": "op2"}]}
        yield {"operation": [{"name": "op1"}]}

    monkeypatch.setattr(mythic_module, "subscribe_custom_query", fake_subscribe)

    results = []
    async for names in instance.monitor_operation_updates():
        results.append(names)

    assert results == [["op1", "op2"], ["op1"]]


async def test_monitor_operation_updates_tolerates_empty_and_missing_name(instance, monkeypatch):
    async def fake_subscribe(session, query):
        yield {}
        yield {"operation": []}
        yield {"operation": [{"name": "op1"}, {"no_name": True}]}

    monkeypatch.setattr(mythic_module, "subscribe_custom_query", fake_subscribe)

    results = []
    async for names in instance.monitor_operation_updates():
        results.append(names)

    assert results == [[], [], ["op1"]]


async def test_monitor_operation_updates_stops_cleanly_on_cancellation(instance, monkeypatch):
    async def fake_subscribe(session, query):
        yield {"operation": [{"name": "op1"}]}
        await asyncio.sleep(3600)

    monkeypatch.setattr(mythic_module, "subscribe_custom_query", fake_subscribe)

    results = []

    async def consume():
        async for names in instance.monitor_operation_updates():
            results.append(names)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    task.cancel()
    await task

    assert results == [["op1"]]


def test_set_operation_cache_replaces_in_place():
    cache_id = id(MythicCommands._operation_cache)

    MythicCommands.set_operation_cache(["op1", "op2"])

    assert MythicCommands._operation_cache == ["op1", "op2"]
    assert id(MythicCommands._operation_cache) == cache_id


def test_set_operation_cache_visible_to_other_instances(fake_instance):
    MythicCommands.set_operation_cache(["op1"])

    other = MythicCommands(fake_instance)

    assert other._operation_cache == ["op1"]


async def test_worker_loop_updates_operation_cache_on_each_push(instance, monkeypatch):
    async def fake_subscribe(session, query):
        yield {"operation": [{"name": "op1"}]}
        yield {"operation": [{"name": "op1"}, {"name": "op2"}]}

    monkeypatch.setattr(mythic_module, "subscribe_custom_query", fake_subscribe)

    seen = []
    async for names in instance.monitor_operation_updates():
        MythicCommands.set_operation_cache(names)
        seen.append(list(MythicCommands._operation_cache))

    assert seen == [["op1"], ["op1", "op2"]]
