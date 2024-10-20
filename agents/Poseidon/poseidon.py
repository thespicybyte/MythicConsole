from backend.mythic_instance.mythic_instance import MythicInstance
from backend.mythic_agent.mythic_agent import MythicAgent

from .formatter import PoseidonFormatter
from .processor import PoseidonProcessor


class Poseidon(MythicAgent):
    def __init__(self, instance: MythicInstance):
        name = "poseidon"
        formatter = PoseidonFormatter()
        processor = PoseidonProcessor()
        super().__init__(name, instance, formatter, processor)
