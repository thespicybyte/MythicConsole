from typing import List

from mythic.mythic_classes import Mythic
from mythic import mythic

from .fragments import PayloadFragments


class PayloadQueries:
    @staticmethod
    async def query_by_id(session: Mythic, payload_id: int) -> dict:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                    query Query($id: Int!) {{
                      payload(where: {{id: {{_eq: $id}}}}) {{
                        ...query_fragment
                      }}
                    }}
                    {PayloadFragments.query()}
                    """,
            variables={"id": payload_id}
        )

        payloads = resp.get("payload")

        if not payloads:
            raise Exception(f"failed to query payload: {resp}")

        if len(payloads) != 1:
            raise Exception(f"failed to query payload: {resp}")

        return payloads[0]

    @staticmethod
    async def query_by_uuid(session: Mythic, payload_uuid: str) -> dict:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                    query Query($uuid: String!) {{
                      payload(where: {{uuid: {{_eq: $uuid}}}}) {{
                        ...query_fragment
                      }}
                    }}
                    {PayloadFragments.query()}
                    """,
            variables={"uuid": payload_uuid}
        )

        payloads = resp.get("payload")

        if not payloads:
            raise Exception(f"failed to query payload: {resp}")

        if len(payloads) != 1:
            raise Exception(f"failed to query payload: {resp}")

        return payloads[0]

    @staticmethod
    async def export(session: Mythic, payload_uuid: str) -> str:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query($uuid: String!) {{
                  exportPayloadConfig(uuid: $uuid) {{
                    config
                    error
                    status
                  }}
                }}
                """,
            variables={"uuid": payload_uuid}
        )

        payload = resp.get("exportPayloadConfig")
        if not payload:
            raise Exception(f"Could not export payload config: {resp}")

        error = payload.get("error")
        if error:
            raise Exception(f"error: {error}")

        status = payload.get("status")
        if not status:
            raise Exception(f"Could not export payload config: {resp}")
        if status != "success":
            raise Exception(f"Could not export payload config: {resp}")

        config = payload.get("config")
        if not config:
            raise Exception(f"Could not export payload config: {resp}")

        return config

    @staticmethod
    async def download(session: Mythic, uuid: str) -> bytes:
        resp = await mythic.download_payload(session, uuid)
        return resp

    @staticmethod
    async def get_all_payloads(session: Mythic, payload_id: int) -> List[int]:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query($operation_id: Int!) {{
                    payload(where: {{operation_id: {{_eq: $operation_id}}}}) {{
                        id
                    }}
                }}
                """,
            variables={"operation_id": payload_id}
        )

        payload_ids = []
        payloads = resp.get("payload")
        if not payloads:
            return payload_ids

        for payload in payloads:
            payload_id = payload.get("id")
            if not payload_id:
                continue
            payload_ids.append(payload_id)

        return payload_ids
