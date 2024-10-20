from pathlib import Path
from typing import Optional, List

from backend import MythicInstance
from utils.logger import logger

from .queries import PayloadQueries


class Payload:
    def __init__(self, instance: MythicInstance, payload_id: int = None, payload_uuid: str = None):
        if not payload_id and not payload_uuid:
            raise Exception("payload id or uuid required")

        self.instance = instance
        self.mythic = instance.mythic
        self.id = payload_id
        self.build_message: Optional[str] = None
        self.build_phase: Optional[str] = None
        self.build_stderr: Optional[str] = None
        self.build_stdout: Optional[str] = None
        self.deleted = False
        self.description: Optional[str] = None
        self.file_id: Optional[str] = None
        self.uuid = payload_uuid
        self.creation_time: Optional[str] = None
        self.os: Optional[str] = None
        self.timestamp: Optional[str] = None
        self.operator_id: Optional[int] = None
        self.username: Optional[str] = None
        self.operation_id: Optional[int] = None
        self.operation_name: Optional[str] = None
        self.payload_type_name: Optional[str] = None
        self.payload_c2profiles: List[str] = []

    def _update(self, data: dict):
        if data.get("id"):
            self.id = data.get("id")
        if data.get("build_message"):
            self.build_message = data.get("build_message")
        if data.get("build_phase"):
            self.build_phase = data.get("build_phase")
        if data.get("build_stderr"):
            self.build_stderr = data.get("build_stderr")
        if data.get("build_stdout"):
            self.build_stdout = data.get("build_stdout")
        if data.get("deleted"):
            self.deleted = data.get("deleted")
        if data.get("description"):
            self.description = data.get("description")
        if data.get("file_id"):
            self.file_id = data.get("file_id")
        if data.get("uuid"):
            self.uuid = data.get("uuid")
        if data.get("creation_time"):
            self.creation_time = data.get("creation_time")
        if data.get("os"):
            self.os = data.get("os")
        if data.get("timestamp"):
            self.timestamp = data.get("timestamp")
        if data.get("operator"):
            operator = data.get("operator")
            if operator.get("id"):
                self.operator_id = operator.get("id")
            if operator.get("username"):
                self.username = operator.get("username")
        if data.get("operation"):
            operation = data.get("operation")
            if operation.get("id"):
                self.operation_id = operation.get("id")
            if operation.get("name"):
                self.operation_name = operation.get("name")
        if data.get("payloadtype"):
            payload_type = data.get("payloadtype")
            if payload_type.get("name"):
                self.payload_type_name = payload_type.get("name")
        if data.get("payloadc2profiles"):
            self.payload_c2profiles = []
            c2_profiles = data.get("payloadc2profiles")
            for c2_profile in c2_profiles:
                if c2_profile.get("c2profile"):
                    profile = c2_profile.get("c2profile")
                    if profile.get("name"):
                        self.payload_c2profiles.append(profile.get("name"))

    async def get_id(self) -> int:
        if self.id:
            return self.id

        await self.query()
        return self.id

    async def get_uuid(self) -> str:
        if self.uuid:
            return self.uuid

        await self.query()
        return self.uuid

    async def query(self):
        try:
            resp = {}
            if self.id:
                resp = await PayloadQueries.query_by_id(self.mythic, self.id)
            if self.uuid:
                resp = await PayloadQueries.query_by_uuid(self.mythic, self.uuid)

            self._update(resp)

        except Exception as e:
            logger.exception(e)
            raise

    async def export(self, path: str = None):
        try:
            uuid = await self.get_uuid()
            config = await PayloadQueries.export(self.mythic, uuid)

            if path:
                with open(path, "w") as f:
                    f.write(config)
                return config

            return config

        except Exception as e:
            logger.exception(e)
            raise

    async def download(self, path: str | Path):
        try:
            uuid = await self.get_uuid()
            data = await PayloadQueries.download(self.mythic, uuid)

            with open(path, 'wb') as f:
                f.write(data)

        except Exception as e:
            logger.exception(e)
            raise
