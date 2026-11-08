from typing import Dict, List

from mythic import mythic
from mythic.mythic_classes import Mythic

from .fragments import DisabledCommandsProfileFragments


class DisabledCommandsProfileQueries:
    @staticmethod
    async def list_for_operation(session: Mythic, operation_id: int) -> List[Dict]:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query ListDisabledCommandsProfiles($operation_id: Int!) {{
                  disabledcommandsprofile(
                    where: {{operation_id: {{_eq: $operation_id}}}},
                    order_by: [{{name: asc}}, {{id: asc}}]
                  ) {{
                    ...query_fragment
                  }}
                }}
                {DisabledCommandsProfileFragments.query()}
                """,
            variables={"operation_id": operation_id},
        )

        return resp.get("disabledcommandsprofile") or []

    @staticmethod
    async def get_by_name(session: Mythic, operation_id: int, name: str) -> List[Dict]:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query GetDisabledCommandsProfile($operation_id: Int!, $name: String!) {{
                  disabledcommandsprofile(
                    where: {{operation_id: {{_eq: $operation_id}}, name: {{_eq: $name}}}},
                    order_by: [{{id: asc}}]
                  ) {{
                    ...query_fragment
                  }}
                }}
                {DisabledCommandsProfileFragments.query()}
                """,
            variables={"operation_id": operation_id, "name": name},
        )

        return resp.get("disabledcommandsprofile") or []

    @staticmethod
    async def insert_command(session: Mythic, name: str, command_id: int) -> Dict:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query="""
                mutation InsertDisabledCommandsProfileEntry($object: disabledcommandsprofile_insert_input!) {
                  insert_disabledcommandsprofile_one(object: $object) {
                    id
                    name
                    command_id
                  }
                }
                """,
            variables={"object": {"name": name, "command_id": command_id}},
        )

        result = resp.get("insert_disabledcommandsprofile_one")
        if not result:
            raise Exception(f"failed to add command to block list: {resp}")

        return result

    @staticmethod
    async def delete_entry(session: Mythic, name: str, row_ids: List[int]) -> Dict:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query="""
                mutation DeleteBlockListEntry($name: String!, $entries: [Int!]!) {
                  deleteBlockListEntry(name: $name, entries: $entries) {
                    status
                    error
                    name
                  }
                }
                """,
            variables={"name": name, "entries": row_ids},
        )

        result = resp.get("deleteBlockListEntry")
        if not result:
            raise Exception(f"failed to remove command from block list: {resp}")

        if result.get("status") != "success" or result.get("error"):
            raise Exception(result.get("error") or f"failed to remove command from block list: {result}")

        return result

    @staticmethod
    async def delete_profile(session: Mythic, name: str) -> Dict:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query="""
                mutation DeleteBlockList($name: String!) {
                  deleteBlockList(name: $name) {
                    status
                    error
                    name
                  }
                }
                """,
            variables={"name": name},
        )

        result = resp.get("deleteBlockList")
        if not result:
            raise Exception(f"failed to delete block list: {resp}")

        if result.get("status") != "success" or result.get("error"):
            raise Exception(result.get("error") or f"failed to delete block list: {result}")

        return result

    @staticmethod
    async def _update_disabled_command_map(session: Mythic, operation_id: int,
                                            profile_id: int, user_id: int) -> Dict:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query="""
                mutation UpdateOperatorOperation($operation_id: Int!, $disabled_command_map: [disabledCommand]) {
                  updateOperatorOperation(
                    operation_id: $operation_id,
                    disabled_command_map: $disabled_command_map
                  ) {
                    status
                    error
                  }
                }
                """,
            variables={
                "operation_id": operation_id,
                "disabled_command_map": [
                    {"disabled_command_profile_id": profile_id, "user_id": user_id}
                ],
            },
        )

        result = resp.get("updateOperatorOperation")
        if not result:
            raise Exception(f"failed to update operator block list assignment: {resp}")

        if result.get("status") != "success" or result.get("error"):
            raise Exception(result.get("error") or f"failed to update operator block list assignment: {result}")

        return result

    @staticmethod
    async def assign(session: Mythic, operation_id: int, profile_row_id: int, user_id: int) -> Dict:
        return await DisabledCommandsProfileQueries._update_disabled_command_map(
            session, operation_id, profile_row_id, user_id)

    @staticmethod
    async def unassign(session: Mythic, operation_id: int, user_id: int) -> Dict:
        return await DisabledCommandsProfileQueries._update_disabled_command_map(
            session, operation_id, 0, user_id)

    @staticmethod
    async def get_all_profile_names(session: Mythic, operation_id: int) -> List[str]:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query="""
                query AllBlockListNames($operation_id: Int!) {
                  disabledcommandsprofile(where: {operation_id: {_eq: $operation_id}}) {
                    name
                  }
                }
                """,
            variables={"operation_id": operation_id},
        )

        rows = resp.get("disabledcommandsprofile") or []
        names = {row["name"] for row in rows if row.get("name")}
        return sorted(names)
