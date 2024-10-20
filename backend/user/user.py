from typing import Optional, Dict

from backend import MythicInstance
from utils.logger import logger

from .queries import UserQueries


class User:
    def __init__(self, instance: MythicInstance, user_id=0, username=""):
        """Instantiate a user object. If created a new user, id can be any int but username will be required"""

        if not user_id and not username:
            raise Exception("user_id or username required")

        self.instance = instance
        self.mythic = instance.mythic
        self.id = user_id
        self.username = username
        self.admin = False
        self.creation_time: Optional[str] = None
        self.last_login: Optional[str] = None
        self.active = False
        self.view_utc_time = False
        self.deleted = False
        self.current_operation_id: Optional[int] = None
        self.current_operation_name: Optional[str] = None

    def _update(self, data: Dict):
        if data.get("id"):
            self.id = data.get("id")
        if data.get("username"):
            self.username = data.get("username")
        if data.get("admin"):
            self.admin = data.get("admin")
        if data.get("creation_time"):
            self.creation_time = data.get("creation_time")
        if data.get("last_login"):
            self.last_login = data.get("last_login")
        if data.get("active"):
            self.active = data.get("active")
        if data.get("view_utc_time"):
            self.view_utc_time = data.get("view_utc_time")
        if data.get("deleted"):
            self.deleted = data.get("deleted")
        if data.get("current_operation_id"):
            self.current_operation_id = data.get("current_operation_id")
        if data.get("operation"):
            operation = data.get("operation")
            self.current_operation_name = operation.get("name")

    async def get_username(self) -> str:
        if self.username:
            return self.username

        await self.query()
        return self.username

    async def get_id(self) -> int:
        if self.id:
            return self.id

        await self.query()
        return self.id

    async def query(self):
        try:
            if self.id:
                resp = await UserQueries.query_by_id(self.mythic, user_id=self.id)
            else:
                resp = await UserQueries.query_by_username(self.mythic, username=self.username)

            self._update(resp)

        except Exception as e:
            logger.exception(e)
            raise

    async def create(self, password: str):
        resp = await UserQueries.create_operator(self.mythic, self.username, password)
        self._update(resp)

    async def set_admin_status(self, is_admin: bool):
        raise NotImplemented
        username = await self.get_username()
        resp = await UserQueries.set_admin_status(self.mythic, username, is_admin)
        self._update(resp)

    async def set_active_status(self, is_active: bool):
        raise NotImplemented
        username = await self.get_username()
        resp = await UserQueries.set_active_status(self.mythic, username, is_active)
        print(resp)
        # self._update(resp)

    async def set_password(self, new_password: str, old_password: str):
        raise NotImplemented
        username = await self.get_username()
        resp = await UserQueries.set_password(self.mythic, username, new_password, old_password)
        return

    async def update_current_operation(self, new_operation_id: int):
        operator_id = await self.get_id()
        await UserQueries.update_current_operation(self.mythic, operator_id, new_operation_id)
