import argparse
import base64
import json
from typing import Optional, AsyncGenerator

import mythic.mythic

from backend import MythicInstance
from utils.logger import logger
from screens.prompts import TaskPrompt

from .queries import TaskQueries
from ..response.response import Response
from ..response.queries import ResponseQueries


class TaskError(Exception):
    pass


class TaskNotCompleted(Exception):
    pass


class Task:
    def __init__(self, instance: MythicInstance, task_id: int = None, task_uuid: str = None,
                 callback_display_id: int = None, command: str = None, args: str | dict = ""):
        if (not task_id and not task_uuid) and (not command and not callback_display_id):
            raise Exception("task id or uuid or command and callback display id required")

        self.instance = instance
        self.mythic = instance.mythic
        self.id = task_id
        self.uuid = task_uuid
        self.display_id: Optional[int] = None
        self.command_id: Optional[int] = None
        self.command_name: Optional[str] = command
        self.args: str | dict = args
        self.params: Optional[str] = None
        self.operation_id: Optional[int] = None
        self.response_count = 0
        self.completed = False
        self.comment: Optional[str] = None
        self.timestamp: Optional[str] = None
        self.stdout: Optional[str] = None
        self.stderr: Optional[str] = None
        self.status: Optional[str] = None
        self.operator_id: Optional[int] = None
        self.username: Optional[str] = None
        self.hostname: Optional[str] = None
        self.callback_id: Optional[int] = None
        self.callback_display_id = callback_display_id
        self.callback_uuid: Optional[str] = None
        self.payload_type_name: Optional[str] = None
        self.background = False
        self.verify_prompt: Optional[TaskPrompt] = None
        self.console_args: Optional[argparse.Namespace] = None

    def __eq__(self, other):
        if isinstance(other, Task):
            return self.id == other.id
        return False

    def __str__(self):
        if not self.command_name:
            return ""
        value = f"{self.command_name}"
        if self.params:
            value = f"{value} {self.params}"

        return value

    def _update(self, data: dict):
        if data.get("id"):
            self.id = data.get("id")
        if data.get("agent_task_id"):
            self.uuid = data.get("agent_task_id")
        if data.get("display_id"):
            self.display_id = data.get("display_id")
        if data.get("command_id"):
            self.command_id = data.get("command_id")
        if data.get("command_name"):
            self.command_name = data.get("command_name")
        if data.get("params"):
            self.params = data.get("params")
        if data.get("operation_id"):
            self.operation_id = data.get("operation_id")
        if data.get("response_count"):
            self.response_count = data.get("response_count")
        if data.get("completed"):
            self.completed = data.get("completed")
        if data.get("comment"):
            self.comment = data.get("comment")
        if data.get("timestamp"):
            self.timestamp = data.get("timestamp")
        if data.get("stdout"):
            self.stdout = data.get("stdout")
        if data.get("stderr"):
            self.stderr = data.get("stderr")
        if data.get("status"):
            self.status = data.get("status")
        if data.get("operator"):
            operator = data.get("operator")
            if operator.get("id"):
                self.operator_id = operator.get("id")
            if operator.get("username"):
                self.username = operator.get("username")
        if data.get("callback"):
            callback = data.get("callback")
            if callback.get("id"):
                self.callback_id = callback.get("id")
            if callback.get("display_id"):
                self.callback_display_id = callback.get("display_id")
            if callback.get("agent_callback_id"):
                self.callback_uuid = callback.get("agent_callback_id")
            if callback.get("host"):
                self.hostname = callback.get("host")
            if callback.get("payload"):
                payload = callback.get("payload")
                if payload.get("payloadtype"):
                    payload_type = payload.get("payloadtype")
                    if payload_type.get("name"):
                        self.payload_type_name = payload_type.get("name")

    async def get_id(self) -> int:
        if self.id:
            return self.id

        await self.query()
        return self.id

    async def get_display_id(self) -> int:
        if self.display_id:
            return self.display_id

        await self.query()
        return self.display_id

    async def get_uuid(self) -> str:
        if self.uuid:
            return self.uuid

        await self.query()
        return self.uuid

    async def is_complete(self) -> bool:
        """Returns True if the task is complete. If current state is false, query to verify"""

        if self.completed:
            return self.completed

        await self.query()
        return self.completed

    async def query(self):
        try:
            resp = {}
            if self.id:
                resp = await TaskQueries.query_by_id(self.mythic, self.id)
            if self.uuid:
                resp = await TaskQueries.query_by_uuid(self.mythic, self.uuid)
            self._update(resp)

        except Exception as e:
            logger.exception(e)
            raise

    async def wait_for_completion(self, timeout: int = None):
        try:
            display_id = await self.get_display_id()
            await TaskQueries.wait_for_complete(self.mythic, display_id, timeout=timeout)
            await self.query()
        except Exception as e:
            logger.exception(e)
            raise

    async def get_responses(self) -> AsyncGenerator[Response, None]:
        """
        Get the responses for a task once it has been completed
        This returns an async iterator, which can be used as:
            async for response in get_responses():
                print(response.__dict__)
        """
        if not self.completed:
            return

        try:
            task_id = await self.get_id()
            responses = await ResponseQueries.query_responses_for_tasks(self.mythic, task_id)
            if not responses:
                return

            for response in responses:
                response_id = response.get("id")
                if not response_id:
                    continue

                task_response = Response(self.instance, response_id)
                await task_response.query()
                yield task_response

        except Exception as e:
            logger.exception(e)
            raise

    async def is_successful(self):
        if self.status == "success":
            return True

        await self.query()
        if not self.completed:
            raise Exception("TaskNotCompleted")

        if self.status == "success":
            return True

        return False

    async def execute(self):
        if not self.command_name:
            raise ValueError("command not specified")

        if self.args is None:
            raise ValueError("arguments not set")

        if not self.callback_display_id:
            raise ValueError("callback display id not set")

        try:
            task_id = await TaskQueries.execute(self.mythic, self.command_name, self.args, self.callback_display_id)
            if not task_id:
                return

            self.id = task_id
            await self.query()

        except Exception as e:
            raise TaskError(e)

    async def download_file(self, local_path: str, file_id: str = None) -> bool:
        """
        When a task returns a `file_id`, get the associated file and download it from the server

        :param local_path: path to write the data
        :param file_id: file id to download. If not passed, attempt to get it from the task response
        :return: returh True if download was successful
        """

        if not file_id:
            if not self.completed:
                await self.wait_for_completion()

            async for resp in self.get_responses():
                decoded = base64.b64decode(resp.response_text).decode()
                try:
                    resp_dict = json.loads(decoded)
                except:
                    continue
                file_id = resp_dict.get("file_id")
                if file_id:
                    break

            if not file_id:
                raise Exception(f"could not get file_id from task {self.id} response")

            data = await mythic.mythic.download_file(self.instance.mythic, file_id)

            with open(local_path, 'wb') as f:
                f.write(data)

        return True
