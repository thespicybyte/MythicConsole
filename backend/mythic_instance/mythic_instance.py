from asyncio import AbstractEventLoop
from typing import Optional, AsyncGenerator, List
from urllib.parse import urlparse

import asyncio

from mythic import mythic
from mythic.mythic_classes import Mythic

from utils.logger import logger


class MythicInstance:
    def __init__(self, username: str, password: str, url: str):
        self.mythic: Optional[Mythic] = None
        self.username = username
        self.password = password
        self.url = url
        self.server_address = "127.0.0.1"
        self.server_port = 7443
        self.use_tls = True
        self.protocol = "https"
        self._login_error = ""
        self._loop: Optional[AbstractEventLoop] = None

    @property
    def loop(self) -> AbstractEventLoop:
        return self._loop

    @loop.setter
    def loop(self, loop: AbstractEventLoop):
        self._loop = loop

    async def login(self) -> bool:
        """ Login to Mythic """

        url = urlparse(self.url)
        address = url.netloc
        if not address:
            address = url.path

        if url.scheme:
            if url.scheme == "https":
                self.server_port = 443
            if url.scheme == "http":
                self.protocol = "http"
                self.server_port = 80

        if ":" in address:
            self.server_address, self.server_port = address.split(":")

        self.use_tls = True if self.protocol == "https" else "http"

        self.url = f"{self.protocol}://{self.server_address}:{self.server_port}"
        try:
            logger.debug(f"logging in to {self.url}")
            self.mythic = await mythic.login(
                server_ip=self.server_address,
                server_port=self.server_port,
                username=self.username,
                password=self.password,
                ssl=self.use_tls,
                logging_level=50)  # logging.CRITICAL

            return True
        except Exception as e:
            self._login_error = str(e)
            logger.error(self._login_error)
            return False

    def get_login_error(self) -> str:
        """Return the error message from an unsuccessful login"""
        return self._login_error

    async def monitor_new_callbacks(self) -> AsyncGenerator[str, None]:
        """
        While running, monitor for new callbacks that connect to Mythic

        :return: callback uuid
        """
        try:
            logger.info("monitoring for new callbacks")
            return_attr = "agent_callback_id"
            async for callbacks in mythic.subscribe_new_callbacks(self.mythic,
                                                                  batch_size=1,
                                                                  custom_return_attributes=return_attr):
                for callback in callbacks:
                    callback_uuid = callback.get("agent_callback_id")
                    if callback_uuid:
                        yield callback_uuid
        except asyncio.CancelledError:
            pass

    async def get_active_callbacks(self) -> List[str]:
        """
        Get all current active callbacks
        :return: list of callback uuids
        """
        callback_uuids = []
        return_attr = "agent_callback_id"
        resp = await mythic.get_all_active_callbacks(self.mythic, custom_return_attributes=return_attr)
        for callback in resp:
            callback_uuid = callback.get("agent_callback_id")
            if callback_uuid:
                callback_uuids.append(callback_uuid)

        return callback_uuids

    async def monitor_tasks_updates(self) -> AsyncGenerator[int, None]:
        """
        Monitor for new tasks during sessions
        :return: yields task id
        """
        logger.debug("monitoring for task updates")
        try:
            return_attr = "id"
            async for task in mythic.subscribe_new_tasks_and_updates(self.mythic, custom_return_attributes=return_attr):
                logger.debug(f"task updated: {task}")
                for t in task:
                    task_id = t.get("id")
                    if task_id:
                        yield task_id
        except asyncio.CancelledError:
            pass

    async def get_and_monitor_new_tasks(self) -> AsyncGenerator[int, None]:
        """
        Monitor for new tasks during sessions
        :return: yields task id
        """
        try:
            return_attr = "id"
            async for task in mythic.subscribe_all_tasks(self.mythic, custom_return_attributes=return_attr):
                if isinstance(task, dict):
                    task_id = task.get("id")
                    if task_id:
                        yield task_id
                        continue

                if isinstance(task, list):
                    for t in task:
                        task_id = t.get("id")
                        if task_id:
                            yield task_id

        except asyncio.CancelledError:
            pass
