from abc import ABC, abstractmethod

from backend.datatypes import StructuredType
from ..task.task import Task


class Processor(ABC):
    """Responsible for serializing raw output into a structured datatype"""

    @abstractmethod
    async def process_task(self, task: Task) -> StructuredType:
        """
        Wrapper around all custom processors for the agent

        :param task: Task object to have output strucuted
        :rtype: Any structured type
        """
        pass
