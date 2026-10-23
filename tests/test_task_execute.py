import pytest

from backend.callback.queries import CallbackQueries
from backend.task.queries import TaskQueries
from backend.task.task import Task, TaskError


async def test_execute_rejects_command_not_loaded(make_task, monkeypatch):
    async def _loaded_commands(*_args, **_kwargs):
        return ["ls", "ps", "sleep"]

    async def _issue(*_args, **_kwargs):
        raise AssertionError("TaskQueries.execute must not be called for a command that isn't loaded")

    monkeypatch.setattr(CallbackQueries, "get_loaded_commands", _loaded_commands)
    monkeypatch.setattr(TaskQueries, "execute", _issue)

    task = make_task(command="caffeinate")

    with pytest.raises(TaskError, match="caffeinate.*not loaded"):
        await task.execute()


async def test_execute_proceeds_when_command_loaded(make_task, monkeypatch):
    async def _loaded_commands(*_args, **_kwargs):
        return ["ls", "ps", "sleep"]

    async def _issue(*_args, **_kwargs):
        return 42

    async def _query(self):
        self.completed = True

    monkeypatch.setattr(CallbackQueries, "get_loaded_commands", _loaded_commands)
    monkeypatch.setattr(TaskQueries, "execute", _issue)
    monkeypatch.setattr(Task, "query", _query)

    task = make_task(command="ps")
    await task.execute()

    assert task.id == 42
