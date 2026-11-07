"""Opt-in live test for the operator subscription. Needs a reachable Mythic server + .env.

Run with `pytest -m live`; deselected by default (pytest.ini's `addopts -m "not live"`).

Creates a throwaway operator while a second connection is consuming
`monitor_operator_updates`, then deletes it, and asserts the subscription picks up both
changes: the username appears in a later push and then drops out of a push after that.
"""
import asyncio
import contextlib
import uuid

import pytest

from mythic_console.backend.mythic_instance.mythic_instance import MythicInstance
from mythic_console.backend.user.queries import UserQueries
from mythic_console.utils.environment import Environment

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def skip_without_live_server():
    if not Environment().server_url() or not Environment().username():
        pytest.skip("MYTHIC_SERVER_URL / MYTHIC_CONSOLE_USER not set; no live Mythic server configured")


async def _login() -> MythicInstance:
    instance = MythicInstance(Environment().username(), Environment().password(), Environment().server_url())
    assert await instance.login(), instance.get_login_error()
    return instance


async def test_operator_subscription_reflects_create_and_delete():
    subscriber = await _login()
    actor = await _login()

    username = f"live_sub_{uuid.uuid4().hex[:8]}"
    operator_id = None

    pushes: list[list[str]] = []

    async def consume():
        async for usernames in subscriber.monitor_operator_updates():
            pushes.append(usernames)

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(_wait_for(lambda: len(pushes) >= 1), timeout=30)

        operator = await UserQueries.create_operator(actor.mythic, username, "hunter2!live")
        operator_id = operator["id"]

        await asyncio.wait_for(_wait_for(lambda: any(username in push for push in pushes)), timeout=30)

        await UserQueries.delete_operator(actor.mythic, operator_id)
        operator_id = None

        await asyncio.wait_for(
            _wait_for(lambda: pushes and username not in pushes[-1]), timeout=30)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        if operator_id is not None:
            await UserQueries.delete_operator(actor.mythic, operator_id)


async def _wait_for(predicate, interval: float = 0.25) -> None:
    while not predicate():
        await asyncio.sleep(interval)
