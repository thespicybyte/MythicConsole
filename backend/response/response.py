from typing import Optional

from backend import MythicInstance
from utils.logger import logger

from .queries import ResponseQueries

class Response:
    def __init__(self, instance: MythicInstance, response_id: int):
        self.instance = instance
        self.mythic = instance.mythic
        self.id = response_id
        self.task_id: Optional[int] = None
        self.is_error = False
        self.operation_id: Optional[int] = None
        self.response_text: Optional[str] = None

    def _update(self, data: dict):
        if data.get("id"):
            self.id = data.get("id")
        if data.get("task_id"):
            self.task_id = data.get("task_id")
        if data.get("is_error"):
            self.is_error = data.get("is_error")
        if data.get("operation_id"):
            self.operation_id = data.get("operation_id")
        if data.get("response_text"):
            self.response_text = data.get("response_text")

    async def get_id(self) -> int:
        if self.id:
            return self.id

        await self.query()
        return self.id

    async def query(self):
        try:
            resp = {}
            if self.id:
                resp = await ResponseQueries.query_by_id(self.mythic, self.id)

            self._update(resp)

        except Exception as e:
            logger.exception(e)
            raise
