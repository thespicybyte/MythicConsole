from backend.mythic_instance.mythic_instance import MythicInstance
from backend.mythic_agent.mythic_agent import MythicAgent
from backend.formatter.formatter import DefaultFormatter
from plugins import get_plugin_registry


class UnknownAgent(Exception):
    def __init__(self, payload_type_name: str):
        super().__init__(payload_type_name)


def get_agent(instance: MythicInstance, payload_type_name: str) -> MythicAgent:
    if not payload_type_name:
        raise UnknownAgent(payload_type_name)

    agent_class = get_plugin_registry().agent_class_for(payload_type_name)
    if agent_class is not None:
        return agent_class(instance)

    return MythicAgent(payload_type_name, instance, DefaultFormatter())
