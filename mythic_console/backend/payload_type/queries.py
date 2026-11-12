from typing import Dict, List

from mythic import mythic
from mythic.mythic_classes import Mythic

from .fragments import PayloadTypeFragments
from mythic_console.backend.graphql_log import logged_query


class PayloadTypeQueries:
    def __init__(self, session: Mythic):
        self.mythic = session

    @staticmethod
    async def query_by_id(session: Mythic, payload_type_id: int) -> Dict | None:
        resp = await logged_query(
            session,
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

        resp = await logged_query(
            session,
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
        resp = await logged_query(
            session,
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

    @staticmethod
    async def query_build_parameters(session: Mythic, payload_type_name: str) -> List[dict]:
        """
        Query the build parameters a payload type accepts

        :param session:
        :param payload_type_name:
        :return: list of build parameter dicts
        """

        resp = await logged_query(
            session,
            query=f"""
                        query Query($name: String!) {{
                          payloadtype(where: {{name: {{_eq: $name}}}}) {{
                            buildparameters {{
                              ...build_parameters_fragment
                            }}
                          }}
                        }}
                        {PayloadTypeFragments.build_parameters_fragment()}
                        """,
            variables={"name": payload_type_name}
        )

        payload_types = resp.get("payloadtype")
        if not payload_types:
            raise Exception(f"failed to query build parameters: {resp}")

        return payload_types[0].get("buildparameters") or []

    @staticmethod
    async def query_supported_c2_profiles(session: Mythic, payload_type_name: str) -> Dict:
        """The payload type's installed+supported C2 profiles (the `payloadtypec2profiles` join,
        filtered to non-deleted profiles) and whether it accepts multiple C2 profiles per build.
        Each profile dict carries its `c2profileparameters`, the same shape
        `C2ProfileQueries.query_all_c2_profiles` returns."""

        resp = await logged_query(
            session,
            query=f"""
                        query Query($name: String!) {{
                          payloadtype(where: {{name: {{_eq: $name}}}}) {{
                            ...supported_c2_fragment
                          }}
                        }}
                        {PayloadTypeFragments.supported_c2_fragment()}
                        """,
            variables={"name": payload_type_name}
        )

        payload_types = resp.get("payloadtype")
        if not payload_types:
            raise Exception(f"failed to query supported c2 profiles: {resp}")

        payload_type = payload_types[0]
        profiles = [join["c2profile"] for join in payload_type.get("payloadtypec2profiles") or []
                   if join.get("c2profile")]
        return {
            "supports_multiple": bool(payload_type.get("supports_multiple_c2_in_build")),
            "profiles": profiles,
        }

