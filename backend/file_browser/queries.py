from pathlib import Path
from typing import List

from mythic.mythic import execute_custom_query
from mythic.mythic_classes import Mythic


class FileBrowserQueries:
    def __init__(self, session: Mythic):
        self.mythic = session

    @staticmethod
    async def query(session: Mythic, callback_uuid: str) -> List[Path]:
        resp = await execute_custom_query(
            mythic=session,
            query=f"""
                query Query($uuid: String!) {{
                    mythictree(where: {{tree_type: {{_eq: "file"}}, callback: {{agent_callback_id: {{_eq: $uuid}}}}}}) {{
                        full_path_text
                        can_have_children
                    }}
                }}
                """,
            variables={"uuid": callback_uuid}
        )

        paths = []
        tree = resp.get("mythictree")
        if not tree:
            return paths

        for path in tree:
            full_path = path.get("full_path_text")
            if not full_path:
                continue

            paths.append(Path(full_path))

        return paths
