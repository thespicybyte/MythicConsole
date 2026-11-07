import types


def test_surfaced_commands_fail_open_when_loaded_unknown(arachne_agent):
    assert arachne_agent.tasker.callback is None

    commands = {command.name for command in arachne_agent.surfaced_commands()}
    assert commands == set(arachne_agent._get_command_names())

    items = arachne_agent.get_completer_items("")
    assert "help" in items
    assert "shell" in items
    assert "ls" in items


def test_surfaced_commands_loaded_only_subset(arachne_agent):
    arachne_agent.tasker.callback = types.SimpleNamespace(display_id=1, loaded_commands={"ls", "pwd"})

    commands = {command.name for command in arachne_agent.surfaced_commands()}
    assert commands == {"ls", "pwd"}

    items = arachne_agent.get_completer_items("")
    assert set(items) == {"help", "ls", "pwd"}
    assert "shell" not in items


def test_surfaced_aliases_fail_open_when_loaded_unknown(test_plugin_agent):
    assert test_plugin_agent.tasker.callback is None

    aliases = {alias.name for alias in test_plugin_agent.surfaced_aliases()}
    assert aliases == {"echo", "connect"}

    items = test_plugin_agent.get_completer_items("")
    assert "echo" in items
    assert "connect" in items


def test_surfaced_aliases_hidden_when_target_command_unloaded(test_plugin_agent):
    test_plugin_agent.tasker.callback = types.SimpleNamespace(display_id=1, loaded_commands={"transfer"})

    aliases = {alias.name for alias in test_plugin_agent.surfaced_aliases()}
    assert aliases == set()

    items = test_plugin_agent.get_completer_items("")
    assert "echo" not in items
    assert "connect" not in items
    assert "transfer" in items


def test_surfaced_aliases_visible_when_target_command_loaded(test_plugin_agent):
    test_plugin_agent.tasker.callback = types.SimpleNamespace(display_id=1, loaded_commands={"net"})

    items = test_plugin_agent.get_completer_items("")
    assert "echo" in items
    assert "connect" in items


def test_scripts_stay_visible_regardless_of_loaded_set(test_plugin_agent):
    test_plugin_agent.tasker.callback = types.SimpleNamespace(display_id=1, loaded_commands=set())

    items = test_plugin_agent.get_completer_items("")
    assert "ping" in items
