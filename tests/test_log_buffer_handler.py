import logging
import re
import threading

from mythic_console.utils.logger import LogBufferHandler, get_log_buffer_handler, logger


def test_emit_appends_formatted_record():
    handler = LogBufferHandler(maxlen=10)
    formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    test_logger = logging.getLogger("test_log_buffer_handler.emit")
    test_logger.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)

    test_logger.info("hello world")

    records = handler.snapshot()
    assert len(records) == 1
    record = records[0]
    assert record.levelname == "INFO"
    assert record.levelno == logging.INFO
    assert record.message == "hello world"
    assert re.match(r"test_log_buffer_handler\.py:\d+", record.location)
    assert re.match(r".+ - test_log_buffer_handler\.py:\d+ - INFO - hello world", record.plain())


def test_buffer_is_bounded_by_maxlen():
    handler = LogBufferHandler(maxlen=3)
    handler.setFormatter(logging.Formatter('%(message)s'))
    test_logger = logging.getLogger("test_log_buffer_handler.bounded")
    test_logger.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)

    for i in range(5):
        test_logger.info(f"line {i}")

    assert [record.message for record in handler.snapshot()] == ["line 2", "line 3", "line 4"]
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

    assert [record.message for record in handler.snapshot()] == ["loud"]


def test_drain_state_returns_count_and_snapshot_together():
    handler = LogBufferHandler(maxlen=10)
    handler.setFormatter(logging.Formatter('%(message)s'))
    test_logger = logging.getLogger("test_log_buffer_handler.drain_state")
    test_logger.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)

    for i in range(4):
        test_logger.info(f"line {i}")

    count, snapshot = handler.drain_state()
    assert count == 4
    assert [record.message for record in snapshot] == ["line 0", "line 1", "line 2", "line 3"]


def test_snapshot_and_drain_state_acquire_the_handler_lock():
    handler = LogBufferHandler(maxlen=10)
    handler.setFormatter(logging.Formatter('%(message)s'))
    real_lock = handler.lock
    calls = []

    class SpyLock:
        def __enter__(self):
            calls.append("enter")
            return real_lock.__enter__()

        def __exit__(self, *args):
            calls.append("exit")
            return real_lock.__exit__(*args)

    handler.lock = SpyLock()

    handler.snapshot()
    handler.drain_state()

    assert calls == ["enter", "exit", "enter", "exit"]


def test_snapshot_survives_concurrent_emit_from_another_thread():
    """emit() runs under Handler.handle()'s lock from worker threads while the drain
    timer reads on the app thread; snapshot()/drain_state() must take the same lock
    or a concurrent append raises RuntimeError: deque mutated during iteration."""
    handler = LogBufferHandler(maxlen=50)
    handler.setFormatter(logging.Formatter('%(message)s'))
    test_logger = logging.getLogger("test_log_buffer_handler.concurrency")
    test_logger.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)

    stop = threading.Event()
    errors = []

    def emit_loop():
        i = 0
        while not stop.is_set():
            test_logger.info(f"line {i}")
            i += 1

    writer = threading.Thread(target=emit_loop)
    writer.start()
    try:
        for _ in range(2000):
            try:
                handler.snapshot()
                handler.drain_state()
            except RuntimeError as e:
                errors.append(e)
                break
    finally:
        stop.set()
        writer.join()

    assert errors == []


def test_mythic_tui_logger_feeds_the_module_level_buffer():
    handler = get_log_buffer_handler()
    before = len(handler.snapshot())

    logger.info("module level buffer check")

    snapshot = handler.snapshot()
    assert len(snapshot) == before + 1
    assert "module level buffer check" in snapshot[-1].message


def test_module_logger_buffers_debug_regardless_of_configured_level():
    handler = get_log_buffer_handler()
    before = len(handler.snapshot())

    logger.debug("debug buffered regardless of log level")

    snapshot = handler.snapshot()
    assert len(snapshot) == before + 1
    assert snapshot[-1].levelname == "DEBUG"
