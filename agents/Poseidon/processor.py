from backend import Task, StructuredType
from backend.processor.processor import Processor


class PoseidonProcessor(Processor):
    async def process_task(self, task: Task) -> StructuredType:
        pass
