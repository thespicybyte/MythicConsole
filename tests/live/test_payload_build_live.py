"""Opt-in live test for `payload build`. Needs a reachable Mythic server + .env with at least one
existing payload to export a config from (used to drive the build with real, server-validated
build/C2 parameters rather than hand-rolled ones).

Run with `pytest -m live`; deselected by default (pytest.ini's `addopts -m "not live"`).

Exports an existing payload's config via `exportPayloadConfig` (the raw shape, e.g.
`{"c2_profile": ..., "c2_profile_parameters": ...}` and `build_parameters` as a list), feeds it
straight into `MythicCommands._payload_build`, and confirms the build succeeds and the payload
downloads -- the round trip the config-translation layer exists to support.
"""
import json
import types

import pytest

from backend.mythic_agent.mythic_agent import MythicCommands
from backend.mythic_instance.mythic_instance import MythicInstance
from backend.payload.queries import PayloadQueries
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


async def _find_any_payload_uuid(instance: MythicInstance) -> str | None:
    from mythic import mythic

    resp = await mythic.execute_custom_query(
        mythic=instance.mythic,
        query="query Query { payload(where: {deleted: {_eq: false}}, limit: 1) { uuid } }",
    )
    payloads = resp.get("payload") or []
    return payloads[0]["uuid"] if payloads else None


async def test_export_then_build_round_trips_through_the_translation_layer(tmp_path):
    instance = await _login()
    if not instance.mythic.current_operation_id:
        pytest.skip("no current operation set for this account on the test server")

    source_uuid = await _find_any_payload_uuid(instance)
    if not source_uuid:
        pytest.skip("no existing payload on the test server to export a config from")

    exported = await PayloadQueries.export(instance.mythic, source_uuid)
    config = json.loads(exported)

    config_path = tmp_path / "exported_config.json"
    config_path.write_text(json.dumps(config))
    output_path = tmp_path / "built_payload.bin"

    commands = MythicCommands(instance)
    args = types.SimpleNamespace(
        payload_type=config["payload_type"],
        config=str(config_path),
        output=str(output_path),
        background=False,
    )

    resp = await commands._payload_build(args)

    assert "Payload built and saved" in resp, resp
    assert output_path.exists()
    assert output_path.stat().st_size > 0
