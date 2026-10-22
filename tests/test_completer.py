def test_empty_string_lists_top_level_commands(poseidon_agent):
    """OP#92: an empty/whitespace-only line now falls into the <=1-token branch and returns the
    top-level command list, instead of crashing with IndexError on `tokens[0]`."""
    items = poseidon_agent.get_completer_items("")

    assert items
    assert "help" in items
    assert "process" in items


def test_whitespace_only_lists_top_level_commands(poseidon_agent):
    items = poseidon_agent.get_completer_items("   ")

    assert items
    assert "help" in items
    assert "process" in items


def test_unbalanced_trailing_quote_returns_empty(poseidon_agent):
    assert poseidon_agent.get_completer_items('shell "a') == []


def test_single_partial_token_lists_help_and_commands(poseidon_agent):
    items = poseidon_agent.get_completer_items("pw")

    assert "help" in items
    assert "process" in items
    assert "pwd" in items  # alias for `directory working`


def test_two_token_line_returns_subcommands_and_options(poseidon_agent):
    items = poseidon_agent.get_completer_items("process list")

    assert set(items) == {"list", "kill", "start", "-h", "--help"}


def test_multi_token_line_excludes_tokens_already_on_the_line(poseidon_agent):
    items = poseidon_agent.get_completer_items("process list --regex foo extra")

    assert set(items) == {"-h", "--help", "-bg", "--background"}
    assert "--regex" not in items
