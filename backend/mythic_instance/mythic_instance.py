from asyncio import AbstractEventLoop
from datetime import datetime
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

        raw = self.url.strip()
        parsed = urlparse(raw)
        # urlparse only fills hostname/port when a scheme + // are present; a bare
        # "host" or "host:port" lands in scheme/path. Re-parse with a default scheme.
        if not parsed.scheme or not parsed.netloc:
            parsed = urlparse(f"https://{raw}")

        scheme = parsed.scheme or "https"
        self.protocol = scheme
        self.use_tls = scheme == "https"

        if parsed.hostname:
            self.server_address = parsed.hostname

        if parsed.port:
            self.server_port = parsed.port
        else:
            self.server_port = 443 if scheme == "https" else 80

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

    async def get_server_version(self) -> str:
        """Return the connected Mythic server version, or "" if it cannot be read."""
        query = """
        query GetServerVersion {
            getGlobalSettings {
                settings
            }
        }
        """
        try:
            resp = await mythic.execute_custom_query(self.mythic, query)
            return resp["getGlobalSettings"]["settings"]["server_config"]["version"]
        except Exception as e:
            logger.error(f"failed to query server version: {e}")
            return ""

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

    async def monitor_callback_updates(self) -> AsyncGenerator[dict, None]:
        """
        Monitor the unfiltered callback_stream for any update to any callback (active flips,
        dead flips, check-ins, streaming) regardless of which operator made the change
        :return: yields raw callback_stream rows
        """
        attrs = "agent_callback_id active dead last_checkin sleep_info ip external_ip current_time timestamp"
        sub = """
            subscription CallbackUpdates($now: timestamp!, $batch: Int!) {
              callback_stream(batch_size: $batch, cursor: {initial_value: {timestamp: $now}}) { %s }
            }""" % attrs
        variables = {"now": str(datetime.utcnow()), "batch": 100}
        try:
            async for result in mythic.subscribe_custom_query(self.mythic, sub, variables):
                for row in result.get("callback_stream", []):
                    yield row
        except asyncio.CancelledError:
            pass

    async def get_all_callbacks_detail(self) -> list[dict]:
        """
        Get all callbacks, including ones that are no longer active, for the manage-callbacks
        modal and the showing X/Y count
        :return: list of callback detail dicts
        """
        attrs = "agent_callback_id display_id host active payload { payloadtype { name } }"
        return await mythic.get_all_callbacks(self.mythic, custom_return_attributes=attrs)

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
