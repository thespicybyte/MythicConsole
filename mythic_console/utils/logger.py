import logging
import os.path
from collections import deque

from mythic_console.utils.environment import Environment

LOG_FILE = os.path.join(Environment().log_directory(), Environment().log_file())
LOG_BUFFER_MAXLEN = 2000


class LogBufferHandler(logging.Handler):
    """Logging handler that keeps a bounded in-memory buffer of formatted lines."""

    def __init__(self, maxlen: int = LOG_BUFFER_MAXLEN):
        super().__init__()
        self.buffer: deque[str] = deque(maxlen=maxlen)
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.buffer.append(self.format(record))
        self.count += 1

    def snapshot(self) -> list[str]:
        """Return the buffered lines seen so far, oldest first."""
        with self.lock:
            return list(self.buffer)

    def drain_state(self) -> tuple[int, list[str]]:
        """Return (count, snapshot) read together, so a drain's tail slice can't be
        skewed by a concurrent emit() between reading one and the other."""
        with self.lock:
            return self.count, list(self.buffer)


logger = logging.getLogger('mythic_tui')
logger.setLevel(Environment().log_level())
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(Environment().log_level())
formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

log_buffer_handler = LogBufferHandler()
log_buffer_handler.setLevel(Environment().log_level())
log_buffer_handler.setFormatter(formatter)
logger.addHandler(log_buffer_handler)


def get_log_buffer_handler() -> LogBufferHandler:
    return log_buffer_handler
