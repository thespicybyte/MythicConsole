import logging
import re

from mythic_console.utils.logger import LogBufferHandler, get_log_buffer_handler, logger


def test_emit_appends_formatted_line():
    handler = LogBufferHandler(maxlen=10)
    formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    test_logger = logging.getLogger("test_log_buffer_handler.emit")
    test_logger.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)

    test_logger.info("hello world")

    assert len(handler.snapshot()) == 1
    assert re.match(r".+ - test_log_buffer_handler.py:\d+ - INFO - hello world", handler.snapshot()[0])


def test_buffer_is_bounded_by_maxlen():
    handler = LogBufferHandler(maxlen=3)
    handler.setFormatter(logging.Formatter('%(message)s'))
    test_logger = logging.getLogger("test_log_buffer_handler.bounded")
    test_logger.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)

    for i in range(5):
        test_logger.info(f"line {i}")

    assert handler.snapshot() == ["line 2", "line 3", "line 4"]
    assert handler.count == 5


def test_records_below_level_are_excluded():
    handler = LogBufferHandler(maxlen=10)
    handler.setFormatter(logging.Formatter('%(message)s'))
    handler.setLevel(logging.WARNING)
    test_logger = logging.getLogger("test_log_buffer_handler.level")
    test_logger.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)

    test_logger.debug("quiet")
    test_logger.warning("loud")

    assert handler.snapshot() == ["loud"]


def test_mythic_tui_logger_feeds_the_module_level_buffer():
    handler = get_log_buffer_handler()
    before = len(handler.snapshot())

    logger.info("module level buffer check")

    snapshot = handler.snapshot()
    assert len(snapshot) == before + 1
    assert "module level buffer check" in snapshot[-1]
