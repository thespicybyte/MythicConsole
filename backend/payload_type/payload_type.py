from typing import Optional

from backend import MythicInstance
from utils.logger import logger

from .queries import PayloadTypeQueries

class PayloadType:
    def __init__(self, instance: MythicInstance, payload_type_id: int = None, name: str = None):
        if not payload_type_id and not name:
            raise Exception("payload type id or name required")

        self.instance = instance
        self.mythic = instance.mythic
        self.id = payload_type_id
        self.agent_type: Optional[str] = None
        self.deleted = False
        self.name = name
        self.supported_os: Optional[str] = None

    def __str__(self):
        return self.name

    def _update(self, data: dict):
        if data.get("id"):
            self.id = data.get("id")
        if data.get("agent_type"):
            self.agent_type = data.get("agent_type")
        if data.get("deleted"):
            self.deleted = data.get("deleted")
        if data.get("name"):
            self.name = data.get("name")
        if data.get("supported_os"):
            self.supported_os = data.get("supported_os")

    async def get_name(self) -> str:
        if self.name:
            return self.name

        await self.query()
        return self.name

    async def get_id(self) -> int:
        if self.id:
            return self.id

        await self.query()
        return self.id

    async def query(self):
        try:
            resp = {}
            if self.id:
                resp = await PayloadTypeQueries.query_by_id(self.mythic, self.id)
            elif self.name:
                resp = await PayloadTypeQueries.query_by_name(self.mythic, self.name)

            self._update(resp)
        except Exception as e:
            logger.exception(e)
            raise

