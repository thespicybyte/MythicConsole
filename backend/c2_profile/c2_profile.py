from typing import List, Optional

from backend import MythicInstance
from utils.logger import logger

from .queries import C2ProfileQueries


class C2Profile:
    def __init__(self, instance: MythicInstance, c2_profile_id: int = None, name: str = None):
        if not c2_profile_id and not name:
            raise Exception("c2 profile id or name required")

        self.instance = instance
        self.mythic = instance.mythic
        self.id = c2_profile_id
        self.name = name
        self.is_p2p = False
        self.parameters: List[dict] = []

    def __str__(self):
        return self.name

    def _update(self, data: dict):
        if data.get("id"):
            self.id = data.get("id")
        if data.get("name"):
            self.name = data.get("name")
        if data.get("is_p2p") is not None:
            self.is_p2p = data.get("is_p2p")
        if data.get("c2profileparameters") is not None:
            self.parameters = data.get("c2profileparameters")

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
                resp = await C2ProfileQueries.query_by_id(self.mythic, self.id)
            elif self.name:
                resp = await C2ProfileQueries.query_by_name(self.mythic, self.name)

            self._update(resp)
        except Exception as e:
            logger.exception(e)
            raise
