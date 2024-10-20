import re
from enum import Enum
from datetime import datetime


class ViewMode(Enum):
    HOME = 1
    CALLBACK = 2


def get_timestamp(fmt: str = "%Y%m%dT%H%M%S") -> str:
    return datetime.now().strftime(fmt)


def camel_to_snake(value: str) -> str:
    """Add an underscore between lowercase and uppercase letters"""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', value)
