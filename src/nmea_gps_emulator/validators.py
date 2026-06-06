"""
Pure validation and parsing functions for the NMEA GPS Emulator.

These functions contain no I/O — they validate input and return parsed
values or raise ``ValueError`` on failure.  Both the interactive menu
(``utils.py``) and the CLI layer (``__main__.py``) delegate to these.
"""

import re
from re import Match

from .constants import IPV4_REGEX, POSITION_REGEX


def parse_position(value: str) -> dict[str, str]:
    """
    Validate and parse a compact position string into a position dict.

    Args:
        value: Position string, e.g. ``"5430N 01920E"``.

    Returns:
        Dictionary with keys ``latitude_value``, ``latitude_direction``,
        ``longitude_value``, ``longitude_direction``.

    Raises:
        ValueError: If *value* does not match the expected format.

    """
    mo: Match[str] | None = POSITION_REGEX.fullmatch(value)
    if not mo:
        raise ValueError(f"Invalid position format: '{value}'")
    return {
        "latitude_value": f"{float(mo.group(2)):08.3f}",
        "latitude_direction": mo.group(3).upper(),
        "longitude_value": f"{float(mo.group(4)):09.3f}",
        "longitude_direction": mo.group(7).upper(),
    }


def parse_heading(value: str) -> float:
    """
    Validate and parse a heading string.

    Args:
        value: Heading string representing degrees (0-359).

    Returns:
        Heading as a float.

    Raises:
        ValueError: If *value* is not a valid heading.

    """
    mo: Match[str] | None = re.fullmatch(r"(3[0-5]\d|[0-2]\d{2}|\d{1,2})", value)
    if not mo:
        raise ValueError(f"Invalid heading: '{value}'")
    return float(mo.group())


def parse_speed(value: str) -> float:
    """
    Validate and parse a speed string.

    Args:
        value: Speed string representing knots (0-999).

    Returns:
        Speed as a float.

    Raises:
        ValueError: If *value* is not a valid speed.

    """
    mo: Match[str] | None = re.fullmatch(r"(\d{1,3}(\.\d+)?)", value)
    if not mo:
        raise ValueError(f"Invalid speed: '{value}'")
    match: str = mo.group()
    if match.startswith("0") and match != "0" and not match.startswith("0."):
        match = match.lstrip("0")
    speed_value: float = float(match)
    if not (0 <= speed_value <= 999):
        raise ValueError(f"Speed out of range: {speed_value}")
    return speed_value


def parse_ipv4(value: str) -> str:
    """
    Validate an IPv4 address string.

    Args:
        value: IPv4 address string.

    Returns:
        The validated IPv4 address.

    Raises:
        ValueError: If *value* is not a valid IPv4 address.

    """
    if not IPV4_REGEX.fullmatch(value):
        raise ValueError(f"Invalid IPv4 address: '{value}'")
    return value
