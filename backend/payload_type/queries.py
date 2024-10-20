from typing import Dict

from mythic.mythic_classes import Mythic
from mythic import mythic

from .fragments import PayloadTypeFragments


class PayloadTypeQueries:
    def __init__(self, session: Mythic):
        self.mythic = session

    @staticmethod
    async def query_by_id(session: Mythic, payload_type_id: int) -> Dict | None:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                query Query($id: Int!) {{
                  payloadtype(where: {{id: {{_eq: $id}}}}) {{
                    ...query_fragment
                  }}
                }}
                {PayloadTypeFragments.query()}
                """,
            variables={"id": payload_type_id}
        )

        payload_type = resp.get("payloadtype")
        if not payload_type:
            raise Exception(f"failed to query payload type: {resp}")

        if len(payload_type) != 1:
            raise Exception(f"failed to query payload type: {resp}")

        return payload_type[0]

    @staticmethod
    async def query_by_name(session: Mythic, name: str) -> Dict:
        """
        Query payload type by name

        :param session:
        :param name:
        :return: dict object of the payload type
        """

        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                    query Query($name: String!) {{
                      payloadtype(where: {{name: {{_eq: $name}}}}) {{
                        ...query_fragment
                      }}
                    }}
                    {PayloadTypeFragments.query()}
                    """,
            variables={"name": name}
        )

        payload_type = resp.get("payloadtype")
        if not payload_type:
            raise Exception(f"failed to query payload type: {resp}")

        if len(payload_type) != 1:
            raise Exception(f"failed to query payload type: {resp}")

        return payload_type[0]

    @staticmethod
    async def query_all_payload_types(session: Mythic):
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                        query Query {{
                          payloadtype {{
                            ...query_fragment
                          }}
                        }}
                        {PayloadTypeFragments.query()}
                        """,
            variables=None
        )

        payload_types = resp.get("payloadtype")
        return payload_types

