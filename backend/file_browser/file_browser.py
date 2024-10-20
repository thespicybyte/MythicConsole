from pathlib import Path
from typing import List

from backend.mythic_instance.mythic_instance import MythicInstance
from .queries import FileBrowserQueries


class FileBrowser:
    def __init__(self, instance: MythicInstance, callback_uuid: str):
        self.instance = instance
        self.mythic = instance.mythic
        self.callback_uuid = callback_uuid
        self.paths: List[Path] = []

    async def query(self):
        self.paths = await FileBrowserQueries.query(self.mythic, self.callback_uuid)
