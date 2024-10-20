from typing import Dict, Literal, List

from mythic import mythic
from mythic.mythic_classes import Mythic
from mythic.mythic import execute_custom_query

from .fragments import OperationFragments
from utils.logger import logger


class OperationQueries:
    def __init__(self, session: Mythic):
        self.mythic = session

    @staticmethod
    async def query_by_id(session: Mythic, operation_id: int) -> Dict:
        resp = await execute_custom_query(
            mythic=session,
            query=f"""
                query Query($id: Int!) {{
                  operation(where: {{id: {{_eq: $id}}}}) {{
                    ...query_fragment
                  }}
                }}
                {OperationFragments.query()}
                """,
            variables={"id": operation_id}
        )

        operations = resp.get("operation")
        if not operations:
            raise Exception(f"failed to query operation: {resp}")

        if len(operations) != 1:
            raise Exception(f"failed to query operation: {resp}")

        return operations[0]

    @staticmethod
    async def query_by_name(session: Mythic, name: str) -> Dict:
        resp = await execute_custom_query(
            mythic=session,
            query=f"""
                query Query($name: String!) {{
                  operation(where: {{name: {{_eq: $name}}}}) {{
                    ...query_fragment
                  }}
                }}
                {OperationFragments.query()}
                """,
            variables={"name": name}
        )

        operations = resp.get("operation")
        if not operations:
            raise Exception(f"failed to query operation: {resp}")

        if len(operations) != 1:
            raise Exception(f"failed to query operation: {resp}")

        return operations[0]

    @staticmethod
    async def query_operation_name(session: Mythic, operation_id: int) -> str:
        """Query operation name providing the id"""

        resp = await execute_custom_query(
            mythic=session,
            query="""
                query QueryOperationName($id: Int!) {
                  operation(where: {id: {_eq: $id}}) {
                    name
                  }
                }
                """,
            variables={"id": operation_id}
        )

        operation = resp.get("operation")
        if not operation:
            logger.error(f"failed to get operation name: {resp}")
            return "unknown"

        if len(operation) != 1:
            logger.error(f"failed to get operation name: {resp}")
            return "unknown"

        operation_name = operation[0].get("name")
        if not operation:
            logger.error(f"failed to get operation name: {resp}")
            return "unknown"

        return operation_name

    @staticmethod
    async def add_operator(session: Mythic, operation_name: str, username: str):
        await mythic.add_operator_to_operation(session, operation_name, username)

    @staticmethod
    async def remove_operator(session: Mythic, operation_name: str, username: str):
        await mythic.remove_operator_from_operation(session, operation_name, username)

    @staticmethod
    async def update_operator(session: Mythic,
                              operation_name: str,
                              username: str, role: Literal["operator", "spectator"]):
        valid_roles = ["lead", "operator", "spectator"]
        if role not in valid_roles:
            raise ValueError(f"invalid role: {role}")

        await mythic.update_operator_in_operation(session, role, operation_name, username)

    @staticmethod
    async def update_operation(session: Mythic,
                               operation_name: str,
                               lead_operator_username: str = None,
                               new_operation_name: str = None,
                               channel: str = None,
                               webhook: str = None,
                               complete: bool = None,
                               deleted: bool = None):

        await mythic.update_operation(session,
                                      operation_name,
                                      lead_operator_username,
                                      new_operation_name,
                                      channel,
                                      webhook,
                                      complete,
                                      deleted)

    @staticmethod
    async def get_active_callbacks(session: Mythic) -> List[dict]:
        resp = await mythic.get_all_active_callbacks(session)
        return resp

    @staticmethod
    async def get_all_operations(session: Mythic) -> List[int]:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query {{
                    operation{{
                        id
                    }}
                }}
                """,
        )

        operation_ids = []
        operations = resp.get("operation")
        if not operations:
            return operation_ids

        for operation in operations:
            operation_id = operation.get("id")
            if not operation_id:
                continue
            operation_ids.append(operation_id)

        return operation_ids
