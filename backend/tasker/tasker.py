from typing import Optional
from mythic import mythic

from ..mythic_instance.mythic_instance import MythicInstance
from ..task.task import Task
from ..callback.callback import Callback

class Tasker:
    def __init__(self, instance: MythicInstance):
        """
        Object used for issuing tasks to any Mythic agent

        :param instance: Mythic Instance object
        """

        self.instance = instance
        self.mythic = instance.mythic
        self.callback: Optional[Callback] = None

    def set_callback(self, callback: Callback):
        """
        Update the callback tasks should be issued to

        :param callback: new Callback value
        """
        self.callback = callback

    async def execute(self, cmd: str, args: str | dict = "", wait=False, timeout=None) -> Task:
        """
        Issue a task to a callback

        :param cmd: Command to execute
        :param args: Arguments to pass to the command
        :param wait: Wait for the task to be completed
        :param timeout: How long to wait for the task to complete
        :return: Task object associated with the new task
        """

        if not self.callback:
            raise Exception("callback not set")

        display_id = await self.callback.get_display_id()
        resp = await mythic.issue_task(self.mythic, cmd, args, display_id)
        if not resp:
            raise Exception("unknown error issuing task")

        status = resp.get("status")
        if not status:
            raise Exception(f"error issuing task: {resp}")

        if status != "success":
            error = resp.get("error")
            if not error:
                raise Exception(f"error issuing task: {resp}")
            raise Exception(error)

        task_id = resp.get("id")
        if not task_id:
            raise Exception(f"error issuing task: {resp}")
        task = Task(self.instance, task_id=task_id)

        if wait:
            await task.wait_for_completion(timeout=timeout)
        return task