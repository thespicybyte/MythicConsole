from typing import Dict, List, Optional, Tuple

from mythic import mythic as mythic_lib

from mythic_console.backend.mythic_instance.mythic_instance import MythicInstance
from mythic_console.backend.payload_type.queries import PayloadTypeQueries
from .queries import DisabledCommandsProfileQueries


class DisabledCommandsProfile:
    """A named command block list scoped to one operation."""

    def __init__(self, instance: MythicInstance, operation_id: int):
        self.instance = instance
        self.mythic = instance.mythic
        self.operation_id = operation_id

    async def list(self) -> List[Dict]:
        return await DisabledCommandsProfileQueries.list_for_operation(self.mythic, self.operation_id)

    async def show(self, name: str) -> List[Dict]:
        rows = await DisabledCommandsProfileQueries.get_by_name(self.mythic, self.operation_id, name)
        if not rows:
            raise Exception(f"block list '{name}' not found")

        return rows

    async def create(self, name: str, command_ids: List[int]):
        existing = await DisabledCommandsProfileQueries.get_by_name(self.mythic, self.operation_id, name)
        if existing:
            raise Exception(f"block list '{name}' already exists")

        for command_id in command_ids:
            await DisabledCommandsProfileQueries.insert_command(self.mythic, name, command_id)

    async def add(self, name: str, command_id: int):
        await DisabledCommandsProfileQueries.insert_command(self.mythic, name, command_id)

    async def remove(self, name: str, command_id: int):
        row_id = await self._resolve_row_id(name, command_id)
        await DisabledCommandsProfileQueries.delete_entry(self.mythic, name, [row_id])

    async def delete(self, name: str):
        await DisabledCommandsProfileQueries.delete_profile(self.mythic, name)

    async def assign(self, name: str, user_id: int):
        row_id = await self._profile_anchor_id(name)
        await DisabledCommandsProfileQueries.assign(self.mythic, self.operation_id, row_id, user_id)

    async def unassign(self, user_id: int):
        await DisabledCommandsProfileQueries.unassign(self.mythic, self.operation_id, user_id)

    async def resolve_command_id(self, cmd_name: str, payload_type: Optional[str] = None) -> int:
        if payload_type:
            commands = await mythic_lib.get_all_commands_for_payloadtype(
                self.mythic, payload_type, custom_return_attributes="id cmd attributes")
            for command in commands:
                if command.get("cmd") == cmd_name:
                    return command["id"]
            raise Exception(f"command '{cmd_name}' not found for payload type '{payload_type}'")

        payload_types = await PayloadTypeQueries.query_all_payload_types(self.mythic)
        matches = []
        for entry in payload_types or []:
            if entry.get("deleted") or not entry.get("name"):
                continue

            commands = await mythic_lib.get_all_commands_for_payloadtype(
                self.mythic, entry["name"], custom_return_attributes="id cmd attributes")
            for command in commands:
                if command.get("cmd") == cmd_name:
                    matches.append((entry["name"], command["id"]))

        if not matches:
            raise Exception(f"command '{cmd_name}' not found")

        if len(matches) > 1:
            candidates = ", ".join(sorted({name for name, _ in matches}))
            raise Exception(
                f"command '{cmd_name}' is ambiguous across payload types ({candidates}); use --payload-type")

        return matches[0][1]

    async def complement_command_ids(self, allowed: List[str],
                                      payload_type: Optional[str] = None) -> Tuple[List[int], List[str]]:
        """Command ids of every command in scope whose name is not in `allowed`.
        Scope is the one payload_type if given, else every non-deleted payload type (union).
        Returns (blocked_command_ids, unknown_allowed_names)."""
        if payload_type:
            scope_names = [payload_type]
        else:
            payload_types = await PayloadTypeQueries.query_all_payload_types(self.mythic)
            scope_names = [entry["name"] for entry in payload_types or []
                           if entry.get("name") and not entry.get("deleted")]

        universe: List[Tuple[str, int]] = []
        for name in scope_names:
            commands = await mythic_lib.get_all_commands_for_payloadtype(
                self.mythic, name, custom_return_attributes="id cmd attributes")
            for command in commands:
                if command.get("cmd") and command.get("id") is not None:
                    universe.append((command["cmd"], command["id"]))

        allowed_set = set(allowed)
        blocked_ids = [command_id for cmd, command_id in universe if cmd not in allowed_set]
        known_names = {cmd for cmd, _ in universe}
        unknown = [name for name in allowed if name not in known_names]

        return blocked_ids, unknown

    async def _resolve_row_id(self, name: str, command_id: int) -> int:
        rows = await DisabledCommandsProfileQueries.get_by_name(self.mythic, self.operation_id, name)
        for row in rows:
            if row.get("command_id") == command_id:
                return row["id"]

        raise Exception(f"command is not in block list '{name}'")

    async def _profile_anchor_id(self, name: str) -> int:
        rows = await DisabledCommandsProfileQueries.get_by_name(self.mythic, self.operation_id, name)
        if not rows:
            raise Exception(f"block list '{name}' not found")

        return min(row["id"] for row in rows if row.get("id"))
