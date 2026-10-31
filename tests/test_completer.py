import pytest

from backend.mythic_agent.mythic_agent import MythicCommands

CMD2_BUILTINS = {
    "_eof", "_relative_run_script", "alias", "edit", "help", "history",
    "macro", "quit", "run_pyscript", "run_script", "set", "shell", "shortcuts",
}


@pytest.fixture
def mythic_commands(fake_instance):
    return MythicCommands(fake_instance)


def test_empty_line_lists_only_real_global_commands(mythic_commands):
    items = mythic_commands.get_completer_items("")

    assert set(items) == {"callback", "operation", "payload", "user", "op"}


def test_empty_line_excludes_cmd2_builtins(mythic_commands):
    items = mythic_commands.get_completer_items("")

    assert CMD2_BUILTINS.isdisjoint(items)


def test_commands_property_excludes_cmd2_builtins(mythic_commands):
    # the property returns do_-prefixed names; none may be a cmd2 built-in
    names = {name.removeprefix("do_") for name in mythic_commands.commands}

    assert names == {"callback", "operation", "payload", "user"}


async def test_empty_string_lists_top_level_commands(test_plugin_agent):
    items = test_plugin_agent.get_completer_items("")

    assert items
    assert "help" in items
    assert "net" in items
    assert "transfer" in items
    assert "echo" in items
    assert "connect" in items
    assert "ping" in items


async def test_whitespace_only_lists_top_level_commands(test_plugin_agent):
    items = test_plugin_agent.get_completer_items("   ")

    assert items
    assert "help" in items
    assert "net" in items


async def test_unbalanced_trailing_quote_returns_empty(test_plugin_agent):
    assert test_plugin_agent.get_completer_items('foo "a') == []


async def test_single_partial_token_lists_help_and_commands(test_plugin_agent):
    items = test_plugin_agent.get_completer_items("ne")

    assert "help" in items
    assert "net" in items
    assert "echo" in items  # alias for `net echo`


async def test_two_token_line_returns_subcommands_and_options(test_plugin_agent):
    items = test_plugin_agent.get_completer_items("net echo")

    assert set(items) == {"echo", "connect", "-h", "--help"}


async def test_multi_token_line_excludes_tokens_already_on_the_line(test_plugin_agent):
    items = test_plugin_agent.get_completer_items("net echo --text foo extra")

    assert set(items) == {"-h", "--help", "-bg", "--background"}
    assert "--text" not in items


async def test_generated_command_name_is_completer_visible(test_plugin_agent):
    items = test_plugin_agent.get_completer_items("")

    assert "transfer" in items


async def test_trailing_space_after_command_lists_subcommands(test_plugin_agent):
    # "net " + Tab: the empty trailing word selects the command's subcommands,
    # not the top-level command list.
    items = test_plugin_agent.get_completer_items("net ")

    assert set(items) == {"echo", "connect", "-h", "--help"}
    assert "ping" not in items


async def test_trailing_space_after_subcommand_lists_its_options(test_plugin_agent):
    items = test_plugin_agent.get_completer_items("net echo ")

    assert "--text" in items
    assert "-bg" in items
    assert "echo" not in items


async def test_trailing_space_on_generated_command_lists_options(generic_agent):
    items = generic_agent.get_completer_items("echo ")

    assert "--shout" in items
    assert "-bg" in items
