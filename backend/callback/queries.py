from mythic import mythic
from mythic.mythic_classes import Mythic

from .fragments import CallbackFragments


class CallbackQueries:
    @staticmethod
    async def query_by_id(session: Mythic, callback_id: int) -> dict:
        """
        Query callback based on id
        :param session: authenticated Mythic object
        :param callback_id: callback id
        :return: dict response from query
        """
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query($id: Int!) {{
                  callback(where: {{id: {{_eq: $id}}}}) {{
                    ...query_fragment
                  }}
                }}
                {CallbackFragments.query()}
                """,
            variables={"id": callback_id}
        )

        callbacks = resp.get("callback")

        if not callbacks:
            raise Exception(f"failed to query callback: {resp}")

        if len(callbacks) != 1:
            raise Exception(f"failed to query callback: {resp}")

        return callbacks[0]

    @staticmethod
    async def query_by_uuid(session: Mythic, uuid: str) -> dict:
        """
        Query callback based on uuid
        :param session: authenticated Mythic object
        :param uuid: callback uuid
        :return: dict response from query
        """
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query($uuid: String!) {{
                  callback(where: {{agent_callback_id: {{_eq: $uuid}}}}) {{
                    ...query_fragment
                  }}
                }}
                {CallbackFragments.query()}
                """,
            variables={"uuid": uuid}
        )

        callbacks = resp.get("callback")

        if not callbacks:
            raise Exception(f"failed to query callback: {resp}")

        if len(callbacks) != 1:
            raise Exception(f"failed to query callback: {resp}")

        return callbacks[0]

    @staticmethod
    async def update_active(session: Mythic, display_id: int, is_active: bool):
        await mythic.update_callback(session, display_id, active=is_active)

    @staticmethod
    async def update_locked(session: Mythic, display_id: int, is_locked: bool):
        await mythic.update_callback(session, display_id, locked=is_locked)

    @staticmethod
    async def update_description(session: Mythic, display_id: int, description: str):
        await mythic.update_callback(session, display_id, description=description)

    @staticmethod
    async def get_all_tasks(session: Mythic, display_id: int) -> dict:
        """
        Get all tasks for a callback based on the display id
        :param session: authenticated Mythic object
        :param display_id: display id for callback
        :return: dictionary returned from query
        """
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query($display_id: Int!) {{
                  callback(where: {{display_id: {{_eq: $display_id}}}}) {{
                    tasks {{
                      id
                    }}
                  }}
                }}
                """,
            variables={"display_id": display_id}
        )

        callbacks = resp.get("callback")

        if not callbacks:
            raise Exception(f"failed to query callback: {resp}")

        if len(callbacks) != 1:
            raise Exception(f"failed to query callback: {resp}")

        return callbacks[0].get("tasks")

    @staticmethod
    async def export(session: Mythic, callback_uuid: str) -> str:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query($uuid: String!) {{
                  exportCallbackConfig(agent_callback_id: $uuid) {{
                    config
                    error
                    status
                  }}
                }}
                """,
            variables={"uuid": callback_uuid}
        )

        callback = resp.get("exportCallbackConfig")
        if not callback:
            raise Exception(f"Could not export callback config: {resp}")

        error = callback.get("error")
        if error:
            raise Exception(f"error: {error}")

        status = callback.get("status")
        if not status:
            raise Exception(f"Could not export callback config: {resp}")
        if status != "success":
            raise Exception(f"Could not export callback config: {resp}")

        config = callback.get("config")
        if not config:
            raise Exception(f"Could not export callback config: {resp}")

        return config

    @staticmethod
    async def import_callback(session: Mythic, config: dict):
        """
        Import a callback from a config

        @param session: Authenticated Mythic instance
        @param config: Callback config in string format
        """

        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                mutation Query($config: jsonb!) {{
                  importCallbackConfig(config: $config) {{
                    error
                    status
                  }}
                }}
                """,
            variables={"config": config}
        )

        callback = resp.get("importCallbackConfig")
        if not callback:
            raise Exception(f"Could not import callback config: {resp}")

        status = callback.get("status")
        if not status:
            raise Exception(f"Could not import callback config: {resp}")
        if status == "success":
            return

        error = callback.get("error")
        if error:
            raise Exception(f"error: {error}")
