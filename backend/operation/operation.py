from typing import Optional, List, Literal
from utils.logger import logger

from backend.mythic_instance.mythic_instance import MythicInstance
from .queries import OperationQueries


class Operation:
    def __init__(self, instance: MythicInstance, operation_id: int = None, name: str = None):
        self.instance = instance
        self.mythic = instance.mythic

        self.id = operation_id
        self.name = name
        self.admin_id: Optional[int] = None
        self.complete: bool = False
        self.webhook: Optional[str] = None
        self.channel: Optional[str] = None
        self.alert_count: Optional[int] = None
        self.deleted: bool = False
        self.callbacks: List[str] = []
        self.disabled_commands_profiles: List[int] = []
        self.operators: List[int] = []

    def __str__(self):
        return self.name

    def _update(self, data: dict):
        if data.get("name"):
            self.name = data.get("name")
        if data.get("admin_id"):
            self.admin_id = data.get("admin_id")
        if data.get("complete"):
            self.complete = data.get("complete")
        if data.get("webhook"):
            self.webhook = data.get("webhook")
        if data.get("channel"):
            self.channel = data.get("channel")
        if data.get("alert_count"):
            self.alert_count = data.get("alert_count")
        if data.get("deleted"):
            self.deleted = data.get("deleted")
        if data.get("callbacks"):
            self.callbacks = []
            callbacks = data.get("callbacks")
            for callback in callbacks:
                if callback.get("agent_callback_id"):
                    self.callbacks.append(callback.get("agent_callback_id"))
        if data.get("disabledcommandsprofiles"):
            self.disabled_commands_profiles = []
            disabled_commands_profiles = data.get("disabled_commands_profiles")
            for profile in disabled_commands_profiles:
                if profile.get("id"):
                    self.disabled_commands_profiles.append(profile.get("id"))
        if data.get("operators"):
            self.operators = []
            operators = data.get("operators")
            for operator in operators:
                if operator.get("id"):
                    self.operators.append(operator.get("id"))

    def get_name(self):
        if not self.name:
            raise Exception("could not get operation name")
        return self.name

    async def query(self):
        try:
            resp = {}
            if self.id:
                resp = await OperationQueries.query_by_id(self.mythic, self.id)
            elif self.name:
                resp = await OperationQueries.query_by_name(self.mythic, self.name)

            self._update(resp)
        except Exception as e:
            logger.exception(e)
            raise

    async def add_operator(self, username: str):
        try:
            await OperationQueries.add_operator(self.mythic, self.get_name(), username)
        except Exception as e:
            logger.error(e)

    async def remove_operator(self, username: str):
        try:
            await OperationQueries.remove_operator(self.mythic, self.get_name(), username)
        except Exception as e:
            logger.error(e)
            raise

    async def update_operator(self, username: str, role: Literal["operator", "spectator"]):
        try:
            await OperationQueries.update_operator(self.mythic, self.get_name(), username, role)
        except Exception as e:
            logger.error(e)
            raise

    async def update(self,
                     lead_operator_username: str = None,
                     new_operation_name: str = None,
                     channel: str = None,
                     webhook: str = None,
                     complete: bool = None,
                     deleted: bool = None):

        try:
            await OperationQueries.update_operation(self.mythic,
                                                    self.get_name(),
                                                    lead_operator_username,
                                                    new_operation_name,
                                                    channel,
                                                    webhook,
                                                    complete,
                                                    deleted)
        except Exception as e:
            logger.error(e)
            raise

    async def get_active_callbacks(self):
        resp = await OperationQueries.get_active_callbacks(self.mythic)
        self.callbacks = []
        for callback in resp:
            if callback.get("id"):
                self.callbacks.append(callback.get("id"))
