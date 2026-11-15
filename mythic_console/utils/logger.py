import logging
import os.path
from collections import deque
from dataclasses import dataclass

from mythic_console.utils.environment import Environment

LOG_FILE = os.path.join(Environment().log_directory(), Environment().log_file())
LOG_BUFFER_MAXLEN = 2000


@dataclass(frozen=True)
class BufferedRecord:
    """One buffered log record, with its fields kept separate so a UI can filter
    and color by level without reparsing a formatted line."""
    levelno: int
    levelname: str
    asctime: str
    location: str
    message: str

    def plain(self) -> str:
        """The record as a single plain-text line, matching the file log's format."""
        return f"{self.asctime} - {self.location} - {self.levelname} - {self.message}"


class LogBufferHandler(logging.Handler):
    """Logging handler that keeps a bounded in-memory buffer of log records."""

    def __init__(self, maxlen: int = LOG_BUFFER_MAXLEN):
        super().__init__()
        self.buffer: deque[BufferedRecord] = deque(maxlen=maxlen)
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        asctime = self.formatter.formatTime(record) if self.formatter else ""
        self.buffer.append(BufferedRecord(
            levelno=record.levelno,
            levelname=record.levelname,
            asctime=asctime,
            location=f"{record.filename}:{record.lineno}",
            message=record.getMessage(),
        ))
        self.count += 1

    def snapshot(self) -> list[BufferedRecord]:
        """Return the buffered records seen so far, oldest first."""
        with self.lock:
            return list(self.buffer)

    def drain_state(self) -> tuple[int, list[BufferedRecord]]:
        """Return (count, snapshot) read together, so a drain's tail slice can't be
        skewed by a concurrent emit() between reading one and the other."""
        with self.lock:
            return self.count, list(self.buffer)


logger = logging.getLogger('mythic_tui')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(Environment().log_level())
formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

log_buffer_handler = LogBufferHandler()
log_buffer_handler.setLevel(logging.DEBUG)
log_buffer_handler.setFormatter(formatter)
logger.addHandler(log_buffer_handler)


def get_log_buffer_handler() -> LogBufferHandler:
    return log_buffer_handler
