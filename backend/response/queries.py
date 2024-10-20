from mythic.mythic_classes import Mythic
from mythic import mythic

from .fragments import ResponseFragments


class ResponseQueries:
    @staticmethod
    async def query_by_id(session: Mythic, response_id: int) -> dict:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query($id: Int!) {{
                  response(where: {{id: {{_eq: $id}}}}) {{
                    ...query_fragment
                  }}
                }}
                {ResponseFragments.query()}
            """,
            variables={"id": response_id}
        )

        responses = resp.get("response")

        if not responses:
            raise Exception(f"failed to query response: {resp}")

        if len(responses) != 1:
            raise Exception(f"failed to query response: {resp}")

        return responses[0]

    @staticmethod
    async def query_responses_for_tasks(session: Mythic, task_id: int) -> dict | None:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query($task_id: Int!) {{
                  response(where: {{task_id: {{_eq: $task_id}}}}) {{
                    id
                  }}
                }}
            """,
            variables={"task_id": task_id}
        )

        responses = resp.get("response")

        if not responses:
            return None

        return responses
