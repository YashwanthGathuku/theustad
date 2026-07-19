import pytest
from app.parser import parse_duration


def test_simple_hours():
    assert parse_duration("2h") == 7200


def test_hours_and_minutes():
    assert parse_duration("1h30m") == 5400


def test_only_minutes():
    assert parse_duration("45m") == 2700


def test_90m_is_valid():
    # Ticket #4127: 90 minutes is a real duration users type constantly.
    assert parse_duration("90m") == 5400


def test_rejects_garbage():
    with pytest.raises(ValueError):
        parse_duration("abc")


def test_rejects_empty():
    with pytest.raises(ValueError):
        parse_duration("")
