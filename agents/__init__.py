from backend.mythic_instance.mythic_instance import MythicInstance
from agents.Poseidon.poseidon import Poseidon


class UnknownAgent(Exception):
    def __init__(self, payload_type_name: str):
        super().__init__(payload_type_name)


def get_agent(instance: MythicInstance, payload_type_name: str) -> Poseidon:
    match payload_type_name:
        case "poseidon":
            return Poseidon(instance)
        case _:
            raise UnknownAgent(payload_type_name)
