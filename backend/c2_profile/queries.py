from typing import List

from mythic.mythic_classes import Mythic
from mythic import mythic

from .fragments import C2ProfileFragments


class C2ProfileQueries:
    @staticmethod
    async def query_by_id(session: Mythic, c2_profile_id: int) -> dict:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                    query Query($id: Int!) {{
                      c2profile(where: {{id: {{_eq: $id}}}}) {{
                        ...query_fragment
                      }}
                    }}
                    {C2ProfileFragments.query()}
                    """,
            variables={"id": c2_profile_id}
        )

        c2_profiles = resp.get("c2profile")
        if not c2_profiles:
            raise Exception(f"failed to query c2 profile: {resp}")

        if len(c2_profiles) != 1:
            raise Exception(f"failed to query c2 profile: {resp}")

        return c2_profiles[0]

    @staticmethod
    async def query_by_name(session: Mythic, name: str) -> dict:
        """
        Query a c2 profile by name

        :param session:
        :param name:
        :return: dict object of the c2 profile
        """

        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                    query Query($name: String!) {{
                      c2profile(where: {{name: {{_eq: $name}}}}) {{
                        ...query_fragment
                      }}
                    }}
                    {C2ProfileFragments.query()}
                    """,
            variables={"name": name}
        )

        c2_profiles = resp.get("c2profile")
        if not c2_profiles:
            raise Exception(f"failed to query c2 profile: {resp}")

        if len(c2_profiles) != 1:
            raise Exception(f"failed to query c2 profile: {resp}")

        return c2_profiles[0]

    @staticmethod
    async def query_all_c2_profiles(session: Mythic) -> List[dict]:
        resp = await mythic.execute_custom_query(
            mythic=session,
            query=f"""
                        query Query {{
                          c2profile(where: {{deleted: {{_eq: false}}}}) {{
                            ...query_fragment
                          }}
                        }}
                        {C2ProfileFragments.query()}
                        """,
            variables=None
        )

        return resp.get("c2profile") or []
