from typing import List

from mythic import mythic
from mythic.mythic_classes import Mythic

from .fragments import UserFragments


class UserQueries:
    @staticmethod
    async def query_by_id(session: Mythic, user_id: int) -> dict | None:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query($id: Int!) {{
                  operator(where: {{id: {{_eq: $id}}}}) {{
                    ...query_fragment
                  }}
                }}
                {UserFragments.query()}
                """,
            variables={"id": user_id}
        )

        user = resp.get("operator")
        if not user:
            raise Exception(f"failed to query user: {resp}")

        if len(user) != 1:
            raise Exception(f"failed to query user: {resp}")

        return user[0]

    @staticmethod
    async def query_by_username(session: Mythic, username: str) -> dict | None:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query($username: String!) {{
                  operator(where: {{username: {{_eq: $username}}}}) {{
                    ...query_fragment
                  }}
                }}
                {UserFragments.query()}
                """,
            variables={"username": username}
        )

        user = resp.get("operator")
        if not user:
            raise Exception(f"failed to query user: {resp}")

        if len(user) != 1:
            raise Exception(f"failed to query user: {resp}")

        return user[0]

    @staticmethod
    async def create_operator(session: Mythic, username: str, password: str) -> dict:
        resp = await mythic.create_operator(session, username, password)
        result = resp.get("createOperator")
        error = result.get("error")
        if error:
            raise Exception(error)

        user_id = result.get("id")
        if not user_id:
            raise Exception("could not get new user id")

        return await UserQueries.query_by_id(session, user_id)

    @staticmethod
    async def set_admin_status(session: Mythic, username: str, is_admin: bool) -> dict:
        resp = await mythic.set_admin_status(session, username, is_admin)
        return resp

    @staticmethod
    async def set_active_status(session: Mythic, username: str, is_active: bool):
        resp = await mythic.set_active_status(session, username, is_active)
        return resp

    @staticmethod
    async def set_password(session: Mythic, username: str, new: str, old: str):
        resp = await mythic.set_password(session, username, new, old)
        print(resp)

    @staticmethod
    async def update_current_operation(session: Mythic, operator_id: int, operation_id: int):
        resp = await mythic.update_current_operation_for_user(session, operator_id, operation_id)
        error = resp.get("error")
        if error:
            raise Exception(error)

    @staticmethod
    async def get_all_users(session: Mythic) -> List[int]:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query {{
                    operator{{
                        id
                    }}
                }}
                """,
        )

        operator_ids = []
        operators = resp.get("operator")
        if not operators:
            return operator_ids

        for operator in operators:
            user_id = operator.get("id")
            if not user_id:
                continue
            operator_ids.append(user_id)

        return operator_ids
