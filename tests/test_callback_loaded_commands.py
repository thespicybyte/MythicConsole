import types

from backend.callback.callback import Callback
from backend.callback.queries import CallbackQueries


async def test_refresh_loaded_commands_updates_set_across_calls(fake_instance, monkeypatch):
    responses = iter([["ls", "ps"], ["ls", "ps", "cat"]])

    async def _get_loaded_commands(*_args, **_kwargs):
        return next(responses)

    monkeypatch.setattr(CallbackQueries, "get_loaded_commands", _get_loaded_commands)

    callback = Callback(fake_instance, callback_id=1)
    callback.display_id = 1

    await callback.refresh_loaded_commands()
    assert callback.loaded_commands == {"ls", "ps"}

    await callback.refresh_loaded_commands()
    assert callback.loaded_commands == {"ls", "ps", "cat"}


async def test_surfacing_reads_loaded_commands_live_with_no_agent_rebuild(arachne_agent):
    callback = types.SimpleNamespace(display_id=1, loaded_commands={"ls", "pwd"})
    arachne_agent.tasker.callback = callback

    items = arachne_agent.get_completer_items("")
    assert "shell" not in items

    callback.loaded_commands.add("shell")

    items = arachne_agent.get_completer_items("")
    assert "shell" in items
