import json
from typing import Optional, List

from utils.logger import logger

from backend import MythicInstance
from widgets.console import ConsolePanel
from .queries import CallbackQueries
from ..task.task import Task


class Callback:
    def __init__(self, instance: MythicInstance, callback_id: int = None, callback_uuid: str = None,
                 config: str = None):
        if not callback_uuid and not callback_id and not config:
            raise Exception("callback id or uuid is required")

        self.instance = instance
        self.mythic = instance.mythic
        self.id = callback_id
        self.uuid: str = callback_uuid
        self.display_id: Optional[int] = None
        self.init_callback: Optional[str] = None
        self.last_checkin: Optional[str] = None
        self.user: Optional[str] = None
        self.hostname: Optional[str] = None
        self.pid: Optional[int] = None
        self.ip: Optional[str] = None
        self.external_ip: Optional[str] = None
        self.process_name: Optional[str] = None
        self.description: Optional[str] = None
        self.operator_id: Optional[int] = None
        self.active: bool = False
        self.registered_payload_id: Optional[int] = None
        self.integrity_level: Optional[int] = None
        self.locked: bool = False
        self.locked_operator_id: Optional[int] = None
        self.operation_id: Optional[int] = None
        self.os: Optional[str] = None
        self.architecture: Optional[str] = None
        self.domain: Optional[str] = None
        self.extra_info: Optional[str] = None
        self.sleep_info: Optional[str] = None
        self.timestamp: Optional[str] = None
        self.payload_type_name: Optional[str] = None
        self.payload_type_uuid: Optional[str] = None
        self.operation_name: Optional[str] = None
        self.tasks: List[Task] = []
        self.config_path = config
        self.console_panel: ConsolePanel = ConsolePanel(instance=self.instance)

    def _update(self, data: dict):
        if data.get("id"):
            self.id = data.get("id")
        if data.get("agent_callback_id"):
            self.uuid = data.get("agent_callback_id")
        if data.get("display_id"):
            self.display_id = data.get("display_id")
        if data.get("init_callback"):
            self.init_callback = data.get("init_callback")
        if data.get("last_checkin"):
            self.last_checkin = data.get("last_checkin")
        if data.get("user"):
            self.user = data.get("user")
        if data.get("host"):
            self.hostname = data.get("host")
        if data.get("pid"):
            self.pid = data.get("pid")
        if data.get("ip"):
            ips = data.get("ip")
            if isinstance(ips, str):
                ips = json.loads(ips)
            self.ip = ips
        if data.get("external_ip"):
            self.external_ip = data.get("external_ip")
        if data.get("process_name"):
            self.process_name = data.get("process_name")
        if data.get("description"):
            self.description = data.get("description")
        if data.get("operator_id"):
            self.operator_id = data.get("operator_id")
        if data.get("active"):
            self.active = data.get("active")
        if data.get("registered_payload_id"):
            self.registered_payload_id = data.get("registered_payload_id")
        if data.get("integrity_level"):
            self.integrity_level = data.get("integrity_level")
        if data.get("locked"):
            self.locked = data.get("locked")
        if data.get("locked_operator_id"):
            self.locked_operator_id = data.get("locked_operator_id")
        if data.get("operation_id"):
            self.operation_id = data.get("operation_id")
        if data.get("os"):
            self.os = data.get("os")
        if data.get("architecture"):
            self.architecture = data.get("architecture")
        if data.get("domain"):
            self.domain = data.get("domain")
        if data.get("extra_info"):
            self.extra_info = data.get("extra_info")
        if data.get("sleep_info"):
            self.sleep_info = data.get("sleep_info")
        if data.get("timestamp"):
            self.timestamp = data.get("timestamp")
        if data.get("operation"):
            operation = data.get("operation")
            if operation.get("id"):
                self.operation_id = operation.get("id")
            if operation.get("name"):
                self.operation_name = operation.get("name")
        if data.get("payload"):
            payload = data.get("payload")
            if payload.get("id"):
                self.registered_payload_id = payload.get("id")
            if payload.get("uuid"):
                self.payload_type_uuid = payload.get("uuid")
            if payload.get("payloadtype"):
                payload_type = payload.get("payloadtype")
                if payload_type.get("name"):
                    self.payload_type_name = payload_type.get("name")

    async def get_display_id(self) -> int:
        if self.display_id:
            return self.display_id

        await self.query()
        return self.display_id

    async def get_uuid(self):
        if self.uuid:
            return self.uuid

        await self.query()
        return self.uuid

    async def query(self):
        try:
            resp = {}
            if self.id:
                resp = await CallbackQueries.query_by_id(self.mythic, self.id)
            elif self.uuid:
                resp = await CallbackQueries.query_by_uuid(self.mythic, self.uuid)

            self._update(resp)
            self.console_panel.set_agent(self.payload_type_name)
        except Exception as e:
            logger.exception(e)
            raise

    async def update_active(self, is_active: bool):
        display_id = await self.get_display_id()
        await CallbackQueries.update_locked(self.mythic, display_id, is_active)

    async def update_locked(self, is_locked: bool):
        display_id = await self.get_display_id()
        await CallbackQueries.update_locked(self.mythic, display_id, is_locked)

    async def update_description(self, description: str):
        display_id = await self.get_display_id()
        await CallbackQueries.update_description(self.mythic, display_id, description)

    async def get_all_tasks(self):
        display_id = await self.get_display_id()
        task_ids = await CallbackQueries.get_all_tasks(self.mythic, display_id)
        if not task_ids:
            return

        self.tasks = []
        for task_id in task_ids:
            task_id = task_id.get("id")
            if not task_id:
                continue

            task = Task(self.instance, task_id=task_id)
            await task.query()
            self.tasks.append(task)

    async def export(self, path: str = None):
        try:
            uuid = await self.get_uuid()
            config = await CallbackQueries.export(self.mythic, uuid)

            if path:
                with open(path, "w") as f:
                    f.write(config)
                return config

            return config

        except Exception as e:
            logger.exception(e)
            raise

    async def import_callback(self):
        if not self.config_path:
            raise Exception("config path required")

        try:
            with open(self.config_path, 'r') as f:
                config = f.read()

            config_json = json.loads(config)
            callback_id = config_json["callback"]["id"]
            self.id = callback_id

            await CallbackQueries.import_callback(self.mythic, config_json)
            logger.debug("callback config successfully imported")

            await self.query()
        except Exception as e:
            logger.exception(e)
            raise
