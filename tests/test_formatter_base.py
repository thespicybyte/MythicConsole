import json

import pytest
from rich.table import Column
from rich.text import Text

from backend.formatter.formatter import DefaultFormatter, Formatter
from backend.task.task import TaskNotCompleted


def test_build_table_no_headers_hides_header():
    table = Formatter.build_table(["a", "b"], headers=None)
    assert table.show_header is False


def test_build_table_string_headers_wrapped_in_column():
    table = Formatter.build_table(["a"], headers=["name"])
    assert table.show_header is True
    assert isinstance(table.columns[0], Column)
    assert table.columns[0].header == "name"
    assert table.columns[0].overflow == "fold"


def test_build_table_adds_rows():
    table = Formatter.build_table(["a", "1"], ["b", "2"], headers=["name", "value"])
    assert table.row_count == 2


def test_build_table_sets_title():
    table = Formatter.build_table(["a"], headers=["name"], title="my table")
    assert table.title == "my table"


async def test_format_plaintext_decodes_and_concatenates(make_task, fake_responses):
    fake_responses(["hello ", "world"])
    task = make_task(completed=True)

    result = await Formatter.format_plaintext(task)

    assert isinstance(result, Text)
    assert result.plain == "hello world"


async def test_format_plaintext_raises_when_not_completed(make_task):
    task = make_task(completed=False)

    with pytest.raises(Exception):
        await Formatter.format_plaintext(task)


async def test_get_raw_output_concatenates_chunks(make_task, fake_responses):
    fake_responses(["chunk-1-", "chunk-2"])
    task = make_task(completed=True)

    raw = await Formatter.get_raw_output(task)

    assert raw == "chunk-1-chunk-2"


async def test_format_pretty_with_json_output(make_task, fake_responses):
    payload = {"key": "value"}
    fake_responses([json.dumps(payload)])
    task = make_task(completed=True)

    result = await DefaultFormatter().format_pretty(task)

    assert result._object == payload


async def test_format_pretty_raises_task_not_completed(make_task):
    task = make_task(completed=False)

    with pytest.raises(TaskNotCompleted):
        await DefaultFormatter().format_pretty(task)
