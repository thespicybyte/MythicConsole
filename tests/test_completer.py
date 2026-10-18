import pytest


def test_empty_string_raises_index_error(poseidon_agent):
    """Known gap: widgets/console.py's _completer_items wrapper (OP#80) guards empty/whitespace
    input before it ever reaches the backend. MythicAgent.get_completer_items itself has no such
    guard and crashes on `tokens[0]` when shlex.split(line) yields no tokens. Documented here as
    current behavior; not in scope to fix for OP#79."""
    with pytest.raises(IndexError):
        poseidon_agent.get_completer_items("")


def test_whitespace_only_raises_index_error(poseidon_agent):
    with pytest.raises(IndexError):
        poseidon_agent.get_completer_items("   ")


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
