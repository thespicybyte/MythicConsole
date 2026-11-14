import logging
import re

from mythic_console.utils.logger import BufferedRecord
from mythic_console.widgets.log_viewer import LogViewer, level_style


def _record(levelno, levelname, message="hello", location="x.py:1", asctime="12:00:00"):
    return BufferedRecord(levelno=levelno, levelname=levelname, asctime=asctime,
                           location=location, message=message)


def test_level_style_debug_is_dim():
    assert level_style(logging.DEBUG) == "dim"


def test_level_style_info_is_neutral():
    assert level_style(logging.INFO) == ""


def test_level_style_warning_uses_severity_color():
    assert level_style(logging.WARNING) == "yellow"


def test_level_style_error_and_critical_use_severity_color():
    assert level_style(logging.ERROR) == "red"
    assert level_style(logging.CRITICAL) == "red"


def test_passes_level_only_filter():
    viewer = LogViewer()
    viewer._enabled_levels = {"WARNING", "ERROR", "CRITICAL"}
    assert viewer._passes(_record(logging.WARNING, "WARNING")) is True
    assert viewer._passes(_record(logging.INFO, "INFO")) is False


def test_passes_regex_only_filter_is_case_insensitive():
    viewer = LogViewer()
    viewer._pattern = re.compile("hello", re.IGNORECASE)
    assert viewer._passes(_record(logging.INFO, "INFO", message="HELLO world")) is True
    assert viewer._passes(_record(logging.INFO, "INFO", message="goodbye")) is False


def test_passes_combines_level_and_regex_with_and():
    viewer = LogViewer()
    viewer._enabled_levels = {"ERROR"}
    viewer._pattern = re.compile("boom")
    assert viewer._passes(_record(logging.ERROR, "ERROR", message="boom")) is True
    assert viewer._passes(_record(logging.INFO, "INFO", message="boom")) is False
    assert viewer._passes(_record(logging.ERROR, "ERROR", message="quiet")) is False


def test_empty_regex_matches_every_enabled_level_record():
    viewer = LogViewer()
    viewer._enabled_levels = {"INFO"}
    assert viewer._pattern is None
    assert viewer._passes(_record(logging.INFO, "INFO", message="anything")) is True
