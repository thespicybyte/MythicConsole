from enum import Enum
from datetime import datetime


class ViewMode(Enum):
    HOME = 1
    CALLBACK = 2


def get_timestamp(fmt: str = "%Y%m%dT%H%M%S") -> str:
    return datetime.now().strftime(fmt)
