import pytest

from backend.callback.queries import CallbackQueries
from backend.task.queries import TaskQueries
from backend.task.task import Task, TaskError


def _raise_if_queried(*_args, **_kwargs):
    raise AssertionError("CallbackQueries.get_loaded_commands must not be called per task")


async def test_execute_rejects_command_not_loaded(make_task, monkeypatch):
    async def _issue(*_args, **_kwargs):
        raise AssertionError("TaskQueries.execute must not be called for a command that isn't loaded")

    monkeypatch.setattr(CallbackQueries, "get_loaded_commands", _raise_if_queried)
    monkeypatch.setattr(TaskQueries, "execute", _issue)

    task = make_task(command="caffeinate", loaded_commands={"ls", "ps", "sleep"})

    with pytest.raises(TaskError, match="caffeinate.*not loaded"):
        await task.execute()


async def test_execute_proceeds_when_command_loaded(make_task, monkeypatch):
    async def _issue(*_args, **_kwargs):
        return 42

    async def _query(self):
        self.completed = True

    monkeypatch.setattr(CallbackQueries, "get_loaded_commands", _raise_if_queried)
    monkeypatch.setattr(TaskQueries, "execute", _issue)
    monkeypatch.setattr(Task, "query", _query)

    task = make_task(command="ps", loaded_commands={"ls", "ps", "sleep"})
    await task.execute()

    assert task.id == 42


async def test_execute_no_per_task_loaded_query(make_task, monkeypatch):
    async def _issue(*_args, **_kwargs):
        return 42

    async def _query(self):
        self.completed = True

    monkeypatch.setattr(CallbackQueries, "get_loaded_commands", _raise_if_queried)
    monkeypatch.setattr(TaskQueries, "execute", _issue)
    monkeypatch.setattr(Task, "query", _query)

    task = make_task(command="ps", loaded_commands={"ls", "ps", "sleep"})
    await task.execute()

    assert task.id == 42


async def test_execute_allows_when_loaded_set_unknown(make_task, monkeypatch):
    async def _issue(*_args, **_kwargs):
        return 42

    async def _query(self):
        self.completed = True

    monkeypatch.setattr(CallbackQueries, "get_loaded_commands", _raise_if_queried)
    monkeypatch.setattr(TaskQueries, "execute", _issue)
    monkeypatch.setattr(Task, "query", _query)

    task = make_task(command="anything", loaded_commands=None)
    await task.execute()

    assert task.id == 42


async def test_execute_allows_when_no_callback(fake_instance, monkeypatch):
    async def _issue(*_args, **_kwargs):
        return 42

    async def _query(self):
        self.completed = True

    monkeypatch.setattr(CallbackQueries, "get_loaded_commands", _raise_if_queried)
    monkeypatch.setattr(TaskQueries, "execute", _issue)
    monkeypatch.setattr(Task, "query", _query)

    task = Task(fake_instance, command="x", callback_display_id=1)
    await task.execute()

    assert task.id == 42
