import pytest
from cmd2 import Cmd2ArgumentParser

from mythic_console.backend.mythic_agent.mythic_agent import MythicCommands

from conftest import completer_values

CMD2_BUILTINS = {
    "_eof", "_relative_run_script", "alias", "edit", "help", "history",
    "macro", "quit", "run_pyscript", "run_script", "set", "shell", "shortcuts",
}


@pytest.fixture
def mythic_commands(fake_instance):
    return MythicCommands(fake_instance)


def test_empty_line_lists_only_real_global_commands(mythic_commands):
    items = mythic_commands.get_completer_items("")

    assert completer_values(items) == {"callback", "operation", "payload", "user", "op", "profiles"}


def test_empty_line_excludes_cmd2_builtins(mythic_commands):
    items = mythic_commands.get_completer_items("")

    assert CMD2_BUILTINS.isdisjoint(completer_values(items))


def test_commands_property_excludes_cmd2_builtins(mythic_commands):
    # the property returns do_-prefixed names; none may be a cmd2 built-in
    names = {name.removeprefix("do_") for name in mythic_commands.commands}

    assert names == {"callback", "operation", "payload", "user", "profiles"}


def _self_contained_parser() -> Cmd2ArgumentParser:
    """A standalone root parser, independent of the app's real command tree, so these
    tests do not depend on what other in-flight work adds to it."""
    root = Cmd2ArgumentParser()
    root.add_argument("-v", "--verbose", action="store_true")
    subparsers = root.add_subparsers(title="subcommands")

    operator_parser = subparsers.add_parser("operator")
    operator_subparsers = operator_parser.add_subparsers(title="subcommands")
    operator_subparsers.add_parser("add")
    operator_subparsers.add_parser("remove")
    operator_subparsers.add_parser("role")

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--role", choices=["operator", "spectator"])
    create_parser.add_argument("active", choices=["true", "false"])

    return root


@pytest.fixture
def mythic_commands_with_test_parser(mythic_commands):
    mythic_commands._completer_parsers["testcmd"] = _self_contained_parser()
    return mythic_commands


def test_completer_nested_subverb_completes_all_sub_verbs(mythic_commands_with_test_parser):
    items = mythic_commands_with_test_parser.get_completer_items("testcmd operator ")

    assert completer_values(items) == {"add", "remove", "role"}


def test_completer_option_choice_completes_values(mythic_commands_with_test_parser):
    items = mythic_commands_with_test_parser.get_completer_items("testcmd create --role ")

    assert completer_values(items) == {"operator", "spectator"}


def test_completer_positional_choice_completes_values(mythic_commands_with_test_parser):
    items = mythic_commands_with_test_parser.get_completer_items("testcmd create ")

    assert completer_values(items) == {"true", "false"}


def test_completer_option_flags_complete_on_dash_for_command(mythic_commands_with_test_parser):
    items = mythic_commands_with_test_parser.get_completer_items("testcmd -")

    assert completer_values(items) == {"-v", "--verbose"}


def test_completer_option_flags_complete_on_dash_for_subcommand(mythic_commands_with_test_parser):
    items = mythic_commands_with_test_parser.get_completer_items("testcmd create -")

    assert completer_values(items) == {"--role"}


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
