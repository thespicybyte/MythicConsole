"""Opt-in live test for rich-param fidelity (OP#104). Needs a reachable Mythic server + .env, with
an active callback for a non-Poseidon agent (arachne on the lab test server) that has a `File`
parameter (e.g. `upload`).

Run with `pytest -m live`; deselected by default (pytest.ini's `addopts -m "not live"`).

Dynamic-query-function live resolution is intentionally not exercised here: the mythic library has
no helper to invoke it, and the lab's arachne install has no callback (dynamic queries are
callback-scoped), so there is nothing to confirm the mechanism against yet (see the plan's open
questions).
"""
import pytest

from backend.formatter.formatter import DefaultFormatter
from backend.mythic_agent.mythic_agent import MythicAgent
from backend.mythic_instance.mythic_instance import MythicInstance
from utils.environment import Environment

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def skip_without_live_server():
    if not Environment().server_url() or not Environment().username():
        pytest.skip("MYTHIC_SERVER_URL / MYTHIC_CONSOLE_USER not set; no live Mythic server configured")


async def _login() -> MythicInstance:
    instance = MythicInstance(Environment().username(), Environment().password(), Environment().server_url())
    assert await instance.login(), instance.get_login_error()
    return instance


async def _find_active_callback(instance: MythicInstance, payload_type_name: str) -> dict | None:
    from mythic import mythic

    callbacks = await mythic.get_all_active_callbacks(
        instance.mythic, custom_return_attributes="id display_id payload { payloadtype { name } }")
    for callback in callbacks:
        if callback.get("payload", {}).get("payloadtype", {}).get("name") == payload_type_name:
            return callback
    return None


async def test_file_param_registers_and_tasks_through_the_generated_path(tmp_path):
    instance = await _login()
    callback_row = await _find_active_callback(instance, "arachne")
    if not callback_row:
        pytest.skip("no active arachne callback on the test server")

    from backend.callback.callback import Callback

    callback = Callback(instance, callback_id=callback_row["id"])
    await callback.query()

    agent = MythicAgent("arachne", instance, DefaultFormatter())
    agent.tasker.set_callback(callback)
    await agent.load_commands()

    local_file = tmp_path / "live_upload.bin"
    local_file.write_bytes(b"mythicconsole-104 live test payload")

    command = agent.get_command("upload")
    ns = command.command_parser.parse_args(["--remote_path", "/tmp/mythicconsole-104.bin",
                                            "--file", str(local_file)])
    task = command._build_task(ns)

    assert task.file_params.get("file") == str(local_file)

    await task.execute()
    await task.wait_for_completion(timeout=60)

    assert await task.is_successful()
