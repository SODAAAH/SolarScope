import pytest
from backend.app.metrics.time_utils import format_time_12h, format_datetime_12h, hour_index_to_12h

def test_hour_index_to_12h():
    assert hour_index_to_12h(0) == "12 AM"
    assert hour_index_to_12h(1) == "1 AM"
    assert hour_index_to_12h(6) == "6 AM"
    assert hour_index_to_12h(11) == "11 AM"
    assert hour_index_to_12h(12) == "12 PM"
    assert hour_index_to_12h(13) == "1 PM"
    assert hour_index_to_12h(18) == "6 PM"
    assert hour_index_to_12h(23) == "11 PM"
    assert hour_index_to_12h(24) == "12 AM"

def test_format_time_12h():
    assert format_time_12h("2025-01-15 00:00:00") == "12:00 AM"
    assert format_time_12h("2025-01-15 04:10:00") == "4:10 AM"
    assert format_time_12h("2025-01-15 12:00:00") == "12:00 PM"
    assert format_time_12h("2025-01-15 13:45:00") == "1:45 PM"
    assert format_time_12h("2025-01-15 23:55:00") == "11:55 PM"
    assert format_time_12h("14:30") == "2:30 PM"
    assert format_time_12h("08:15:00") == "8:15 AM"

def test_format_datetime_12h():
    assert format_datetime_12h("2025-01-15 00:00:00") == "2025-01-15 12:00 AM"
    assert format_datetime_12h("2025-01-15 04:10:00") == "2025-01-15 4:10 AM"
    assert format_datetime_12h("2025-01-15 13:45:00") == "2025-01-15 1:45 PM"
    assert format_datetime_12h(None) == ""
