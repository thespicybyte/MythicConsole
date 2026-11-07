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


async def test_monitor_operator_updates_yields_deleted_filtered_usernames(instance, monkeypatch):
    async def fake_subscribe(session, query):
        yield {"operator": [{"username": "alice"}, {"username": "bob"}]}
        yield {"operator": [{"username": "alice"}]}

    monkeypatch.setattr(mythic_module, "subscribe_custom_query", fake_subscribe)

    results = []
    async for usernames in instance.monitor_operator_updates():
        results.append(usernames)

    assert results == [["alice", "bob"], ["alice"]]


async def test_monitor_operator_updates_tolerates_empty_and_missing_username(instance, monkeypatch):
    async def fake_subscribe(session, query):
        yield {}
        yield {"operator": []}
        yield {"operator": [{"username": "alice"}, {"no_username": True}]}

    monkeypatch.setattr(mythic_module, "subscribe_custom_query", fake_subscribe)

    results = []
    async for usernames in instance.monitor_operator_updates():
        results.append(usernames)

    assert results == [[], [], ["alice"]]


async def test_monitor_operator_updates_stops_cleanly_on_cancellation(instance, monkeypatch):
    async def fake_subscribe(session, query):
        yield {"operator": [{"username": "alice"}]}
        await asyncio.sleep(3600)

    monkeypatch.setattr(mythic_module, "subscribe_custom_query", fake_subscribe)

    results = []

    async def consume():
        async for usernames in instance.monitor_operator_updates():
            results.append(usernames)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    task.cancel()
    await task

    assert results == [["alice"]]


def test_set_user_cache_replaces_in_place():
    cache_id = id(MythicCommands._user_cache)

    MythicCommands.set_user_cache(["alice", "bob"])

    assert MythicCommands._user_cache == ["alice", "bob"]
    assert id(MythicCommands._user_cache) == cache_id


def test_set_user_cache_visible_to_other_instances(fake_instance):
    MythicCommands.set_user_cache(["alice"])

    other = MythicCommands(fake_instance)

    assert other._user_cache == ["alice"]


async def test_worker_loop_updates_cache_on_each_push(instance, monkeypatch):
    async def fake_subscribe(session, query):
        yield {"operator": [{"username": "alice"}]}
        yield {"operator": [{"username": "alice"}, {"username": "bob"}]}

    monkeypatch.setattr(mythic_module, "subscribe_custom_query", fake_subscribe)

    seen = []
    async for usernames in instance.monitor_operator_updates():
        MythicCommands.set_user_cache(usernames)
        seen.append(list(MythicCommands._user_cache))

    assert seen == [["alice"], ["alice", "bob"]]
