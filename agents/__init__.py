from backend.mythic_instance.mythic_instance import MythicInstance
from backend.mythic_agent.mythic_agent import MythicAgent
from backend.formatter.formatter import DefaultFormatter
from agents.Poseidon.poseidon import Poseidon


class UnknownAgent(Exception):
    def __init__(self, payload_type_name: str):
        super().__init__(payload_type_name)


def get_agent(instance: MythicInstance, payload_type_name: str) -> MythicAgent:
    match payload_type_name:
        case "poseidon":
            return Poseidon(instance)
        case _ if not payload_type_name:
            raise UnknownAgent(payload_type_name)
        case _:
            return MythicAgent(payload_type_name, instance, DefaultFormatter())
