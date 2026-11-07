import json
from datetime import datetime, timedelta, timezone

import pytest

from utils.callback_status import (
    STREAMING_SENTINEL,
    alive_state,
    checkin_text,
    count_active,
    display_ip,
    format_relative,
    is_streaming,
    parse_mythic_timestamp,
    parse_sleep_window,
    status_glyph,
)

NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_mythic_timestamp_with_microseconds():
    parsed = parse_mythic_timestamp("2024-01-01T12:00:00.123456")
    assert parsed == datetime(2024, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)


def test_parse_mythic_timestamp_without_microseconds():
    parsed = parse_mythic_timestamp("2024-01-01T12:00:00")
    assert parsed == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_mythic_timestamp_trailing_z():
    parsed = parse_mythic_timestamp("2024-01-01T12:00:00.000000Z")
    assert parsed == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("value", [None, "", "not-a-timestamp"])
def test_parse_mythic_timestamp_returns_none_on_garbage(value):
    assert parse_mythic_timestamp(value) is None


def test_is_streaming_sentinel():
    assert is_streaming(STREAMING_SENTINEL) is True
    assert is_streaming("1970-01-01T00:00:00.000000") is True


@pytest.mark.parametrize("value", [None, "", "2024-01-01T00:00:00"])
def test_is_streaming_false_cases(value):
    assert is_streaming(value) is False


@pytest.mark.parametrize("seconds,expected", [(0, "0s"), (59, "59s"), (60, "1m"),
                                               (3599, "59m"), (3600, "1h"),
                                               (86399, "23h"), (86400, "1d")])
def test_format_relative_boundaries(seconds, expected):
    last_checkin = (NOW - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S")
    assert format_relative(last_checkin, NOW) == expected


def test_format_relative_unparseable_returns_placeholder():
    assert format_relative("garbage", NOW) == "?"


def test_checkin_text_streaming_overrides_relative():
    assert checkin_text(STREAMING_SENTINEL, NOW) == "streaming"


def test_checkin_text_falls_back_to_relative():
    last_checkin = NOW.strftime("%Y-%m-%dT%H:%M:%S")
    assert checkin_text(last_checkin, NOW) == "0s"


def test_display_ip_single_entry():
    assert display_ip(["10.0.0.1"]) == "10.0.0.1"


def test_display_ip_shows_only_first_entry_no_suffix():
    assert display_ip(["10.0.0.1", "192.168.1.1", "172.16.0.1"]) == "10.0.0.1"


def test_display_ip_falls_back_to_external_ip_when_no_ip_list():
    assert display_ip(None, "8.8.8.8") == "8.8.8.8"
    assert display_ip([], "8.8.8.8") == "8.8.8.8"


def test_display_ip_empty_with_no_external_ip():
    assert display_ip(None, None) == ""


def test_parse_sleep_window_empty_or_garbage_returns_none():
    assert parse_sleep_window("") is None
    assert parse_sleep_window(None) is None
    assert parse_sleep_window("not-json") is None
    assert parse_sleep_window("[]") is None
    assert parse_sleep_window("{}") is None


def test_parse_sleep_window_single_profile_with_jitter():
    sleep_info = json.dumps({"websocket": {"interval": 10, "jitter": 37, "killdate": "2099-01-01"}})
    assert parse_sleep_window(sleep_info) == pytest.approx(13.7)


def test_parse_sleep_window_defaults_jitter_to_zero():
    sleep_info = json.dumps({"http": {"interval": 20}})
    assert parse_sleep_window(sleep_info) == pytest.approx(20.0)


def test_parse_sleep_window_takes_max_across_profiles():
    sleep_info = json.dumps({
        "http": {"interval": 10, "jitter": 0},
        "websocket": {"interval": 50, "jitter": 10},
    })
    assert parse_sleep_window(sleep_info) == pytest.approx(55.0)


def test_alive_state_streaming_beats_dead():
    state = alive_state(dead=True, last_checkin=STREAMING_SENTINEL, sleep_info=None, now=NOW)
    assert state == "streaming"


def test_alive_state_dead_flag():
    last_checkin = (NOW.replace(year=2023)).strftime("%Y-%m-%dT%H:%M:%S")
    state = alive_state(dead=True, last_checkin=last_checkin, sleep_info=None, now=NOW)
    assert state == "dead"


def test_alive_state_late_past_expected_window():
    sleep_info = json.dumps({"http": {"interval": 10, "jitter": 0}})
    last_checkin = "2024-01-01T11:00:00"  # one hour before NOW, well past a 10s window
    state = alive_state(dead=False, last_checkin=last_checkin, sleep_info=sleep_info, now=NOW)
    assert state == "late"


def test_alive_state_alive_within_window():
    sleep_info = json.dumps({"http": {"interval": 3600, "jitter": 0}})
    last_checkin = "2024-01-01T11:59:00"
    state = alive_state(dead=False, last_checkin=last_checkin, sleep_info=sleep_info, now=NOW)
    assert state == "alive"


def test_alive_state_unparseable_sleep_info_never_late():
    last_checkin = "2020-01-01T00:00:00"
    state = alive_state(dead=False, last_checkin=last_checkin, sleep_info="garbage", now=NOW)
    assert state == "alive"


def test_status_glyph_known_and_unknown_states():
    assert status_glyph("alive") != ""
    assert status_glyph("not-a-real-state") == ""


def test_count_active_tracks_a_simulated_stream_flip():
    known_callbacks = {"a": True, "b": True, "c": False}
    assert count_active(known_callbacks) == (2, 3)

    # simulated callback_stream row flipping "b" to inactive
    known_callbacks["b"] = False
    assert count_active(known_callbacks) == (1, 3)
