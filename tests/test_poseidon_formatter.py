import json
from pathlib import Path

from rich.table import Table
from rich.text import Text

FIXTURES = Path(__file__).parent / "fixtures"


async def test_ls_renders_table_with_parent_and_child_rows(poseidon_agent, make_task, fake_responses):
    raw = (FIXTURES / "poseidon_ls.json").read_text()
    fake_responses([raw])
    task = make_task(command_name="ls", completed=True)

    result = await poseidon_agent.formatter.ls(task)

    assert isinstance(result, Table)
    assert result.row_count == 3  # the directory itself + 2 files
    assert result.title == "ls of /home/user/docs"


async def test_ls_returns_text_on_invalid_json(poseidon_agent, make_task, fake_responses):
    fake_responses(["not json"])
    task = make_task(command_name="ls", completed=True)

    result = await poseidon_agent.formatter.ls(task)

    assert isinstance(result, Text)


async def test_ps_renders_table_with_a_row_per_process(poseidon_agent, make_task, fake_responses):
    raw = (FIXTURES / "poseidon_ps.json").read_text()
    fake_responses([raw])
    task = make_task(command_name="ps", completed=True)

    result = await poseidon_agent.formatter.ps(task)

    assert isinstance(result, Table)
    assert result.row_count == 2
    assert result.title == "Process List"


async def test_format_output_dispatches_ls_to_table(poseidon_agent, make_task, fake_responses):
    raw = (FIXTURES / "poseidon_ls.json").read_text()
    fake_responses([raw])
    task = make_task(command_name="ls", completed=True)

    result = await poseidon_agent.formatter.format_output(task)

    assert isinstance(result, Table)


async def test_format_output_unknown_command_falls_back_to_plaintext(poseidon_agent, make_task, fake_responses):
    fake_responses(["raw output"])
    task = make_task(command_name="some_unlisted_command", completed=True)

    result = await poseidon_agent.formatter.format_output(task)

    assert isinstance(result, Text)
    assert result.plain == "raw output"
