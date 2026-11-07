from mythic.mythic_classes import Mythic
from mythic import mythic

from .fragments import TaskFragments


class TaskQueries:
    @staticmethod
    async def query_by_id(session: Mythic, task_id: int):
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                    query Query($id: Int!) {{
                      task(where: {{id: {{_eq: $id}}}}) {{
                        ...query_fragment
                      }}
                    }}
                    {TaskFragments.query()}
                    """,
            variables={"id": task_id}
        )

        tasks = resp.get("task")

        if not tasks:
            raise Exception(f"failed to query task: {resp}")

        if len(tasks) != 1:
            raise Exception(f"failed to query task: {resp}")

        return tasks[0]

    @staticmethod
    async def query_by_uuid(session: Mythic, uuid: str):
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                    query Query($uuid: String!) {{
                      task(where: {{agent_task_id: {{_eq: $uuid}}}}) {{
                        ...query_fragment
                      }}
                    }}
                    {TaskFragments.query()}
                    """,
            variables={"uuid": uuid}
        )

        tasks = resp.get("task")

        if not tasks:
            raise Exception(f"failed to query task: {resp}")

        if len(tasks) != 1:
            raise Exception(f"failed to query task: {resp}")

        return tasks[0]

    @staticmethod
    async def wait_for_complete(session: Mythic, display_id: int, timeout=None):
        return await mythic.waitfor_task_complete(session, display_id, timeout=timeout)

    @staticmethod
    async def execute(session: Mythic, command: str, args: str | dict, callback_display_id: int) -> int | None:
        resp = await mythic.issue_task(session,
                                       command_name=command,
                                       parameters=args,
                                       callback_display_id=callback_display_id,
                                       custom_return_attributes="id")

        error = resp.get("error")
        if error:
            raise Exception(error)

        task_id = resp.get("id")
        if not task_id:
            raise Exception(f"Could not get task id: {resp}")
        
        return task_id
