import pytest


@pytest.mark.parametrize("raw,expected", [
    ("Error: processing arguments", "error"),
    ("error: build failed with a very long message", "error"),
    ("success", "success"),
    ("processing", "processing"),
    ("submitted", "submitted"),
    ("completed", "completed"),
    (None, ""),
    ("", ""),
])
def test_display_status(make_task, raw, expected):
    task = make_task(status=raw)
    assert task.display_status == expected


def test_raw_status_preserved(make_task):
    task = make_task(status="Error: processing arguments")
    assert task.status == "Error: processing arguments"
