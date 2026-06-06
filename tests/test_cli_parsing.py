"""Unit tests and property tests for CLI argument parsing and validation."""

import argparse
import contextlib
import io
import unittest

from hypothesis import given
from hypothesis import strategies as st

from nmea_gps_emulator.__main__ import build_cli_config, build_parser, validate_args
from nmea_gps_emulator.validators import (
    parse_heading,
    parse_ipv4,
    parse_position,
    parse_speed,
)


def make_args(**overrides: object) -> argparse.Namespace:
    """Build a valid argparse.Namespace, overriding individual fields."""
    base = {
        "mode": "interactive",
        "position": "5430N 01920E",
        "speed": 0.0,
        "heading": 0.0,
        "altitude": 15.2,
        "ip": "127.0.0.1",
        "port": 2020,
        "protocol": "tcp",
        "serial_port": None,
        "baudrate": 4800,
        "headless": False,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def is_rejected(args: argparse.Namespace) -> bool:
    """Return True if validate_args rejects the namespace with SystemExit."""
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            validate_args(args)
        except SystemExit:
            return True
    return False


# Valid compact-position string strategies (matching POSITION_REGEX).
_latitudes = st.builds(
    lambda d, m, h: f"{d:02d}{m:02d}{h}",
    st.integers(min_value=0, max_value=89),
    st.integers(min_value=0, max_value=59),
    st.sampled_from("NSns"),
)
_longitudes = st.builds(
    lambda d, m, h: f"{d:03d}{m:02d}{h}",
    st.integers(min_value=0, max_value=179),
    st.integers(min_value=0, max_value=59),
    st.sampled_from("EWew"),
)
_positions = st.builds(lambda la, lo: f"{la} {lo}", _latitudes, _longitudes)


class TestParsePosition(unittest.TestCase):
    """Tests for parse_position."""

    def test_valid_position(self) -> None:
        """A well-formed position parses into the expected dict."""
        result = parse_position("5430N 01920E")
        self.assertEqual(
            result,
            {
                "latitude_value": "5430.000",
                "latitude_direction": "N",
                "longitude_value": "01920.000",
                "longitude_direction": "E",
            },
        )

    def test_lowercase_hemisphere_normalized(self) -> None:
        """Lowercase hemisphere letters are upper-cased."""
        result = parse_position("5430n 01920e")
        self.assertEqual(result["latitude_direction"], "N")
        self.assertEqual(result["longitude_direction"], "E")

    def test_invalid_positions_rejected(self) -> None:
        """Malformed positions raise ValueError."""
        for bad in ["", "5430N", "9430N 01920E", "5460N 01920E", "5430N 18120E", "abc"]:
            with self.assertRaises(ValueError, msg=bad):
                parse_position(bad)

    def test_special_max_values(self) -> None:
        """Boundary values 9000 (lat) and 18000 (lon) are accepted."""
        result = parse_position("9000N 18000E")
        self.assertEqual(result["latitude_value"], "9000.000")
        self.assertEqual(result["longitude_value"], "18000.000")

    @given(_positions)
    def test_valid_positions_roundtrip(self, position: str) -> None:
        """Any well-formed position parses and preserves the hemisphere."""
        result = parse_position(position)
        self.assertEqual(
            set(result),
            {"latitude_value", "latitude_direction", "longitude_value", "longitude_direction"},
        )
        self.assertEqual(result["latitude_direction"], position[4].upper())
        self.assertEqual(result["longitude_direction"], position[-1].upper())


class TestParseHeading(unittest.TestCase):
    """Tests for parse_heading."""

    def test_valid_headings(self) -> None:
        """In-range headings parse to floats."""
        for value, expected in [("0", 0.0), ("90", 90.0), ("359", 359.0), ("007", 7.0)]:
            self.assertEqual(parse_heading(value), expected)

    def test_invalid_headings_rejected(self) -> None:
        """Out-of-range or malformed headings raise ValueError."""
        for bad in ["360", "400", "-5", "12.5", "abc", "", "9999"]:
            with self.assertRaises(ValueError, msg=bad):
                parse_heading(bad)

    @given(st.integers(min_value=0, max_value=359))
    def test_in_range_integers_accepted(self, value: int) -> None:
        """Every integer 0-359 is accepted and round-trips."""
        self.assertEqual(parse_heading(str(value)), float(value))

    @given(st.integers(min_value=360, max_value=10_000))
    def test_above_range_integers_rejected(self, value: int) -> None:
        """Integers >= 360 are rejected."""
        with self.assertRaises(ValueError):
            parse_heading(str(value))


class TestParseSpeed(unittest.TestCase):
    """Tests for parse_speed."""

    def test_valid_speeds(self) -> None:
        """In-range speeds parse to floats, with leading zeros normalized."""
        for value, expected in [("0", 0.0), ("10.5", 10.5), ("999", 999.0), ("007", 7.0)]:
            self.assertEqual(parse_speed(value), expected)

    def test_invalid_speeds_rejected(self) -> None:
        """Out-of-range or malformed speeds raise ValueError."""
        for bad in ["1000", "-5", "abc", "", "nan"]:
            with self.assertRaises(ValueError, msg=bad):
                parse_speed(bad)

    @given(st.integers(min_value=0, max_value=999))
    def test_in_range_integers_accepted(self, value: int) -> None:
        """Every integer 0-999 is accepted and round-trips."""
        self.assertEqual(parse_speed(str(value)), float(value))

    @given(st.integers(min_value=0, max_value=998), st.integers(min_value=0, max_value=999))
    def test_in_range_decimals_accepted(self, whole: int, frac: int) -> None:
        """Decimal speeds within range are accepted."""
        text = f"{whole}.{frac}"
        self.assertEqual(parse_speed(text), float(text))


class TestParseIpv4(unittest.TestCase):
    """Tests for parse_ipv4."""

    def test_valid_addresses(self) -> None:
        """Well-formed IPv4 addresses are returned unchanged."""
        for value in ["127.0.0.1", "0.0.0.0", "255.255.255.255", "192.168.1.100"]:
            self.assertEqual(parse_ipv4(value), value)

    def test_invalid_addresses_rejected(self) -> None:
        """Malformed IPv4 addresses raise ValueError."""
        for bad in ["999.999.999.999", "256.1.1.1", "1.2.3", "1.2.3.4.5", "abc", ""]:
            with self.assertRaises(ValueError, msg=bad):
                parse_ipv4(bad)

    @given(
        st.integers(0, 255),
        st.integers(0, 255),
        st.integers(0, 255),
        st.integers(0, 255),
    )
    def test_all_octet_combinations_accepted(self, a: int, b: int, c: int, d: int) -> None:
        """Every dotted-quad with octets 0-255 is accepted."""
        addr = f"{a}.{b}.{c}.{d}"
        self.assertEqual(parse_ipv4(addr), addr)


class TestValidateArgs(unittest.TestCase):
    """Tests for the mode-aware validate_args function."""

    def test_defaults_pass(self) -> None:
        """The default namespace validates cleanly in interactive mode."""
        self.assertFalse(is_rejected(make_args()))

    def test_negative_heading_rejected(self) -> None:
        """Regression for finding #1: small negative headings are rejected."""
        for heading in [-0.5, -0.9, -1.0, -5.0]:
            self.assertTrue(is_rejected(make_args(heading=heading)), msg=str(heading))

    def test_boundary_headings(self) -> None:
        """0 is accepted, 360 is rejected, 359.x is accepted."""
        self.assertFalse(is_rejected(make_args(heading=0.0)))
        self.assertFalse(is_rejected(make_args(heading=359.9)))
        self.assertTrue(is_rejected(make_args(heading=360.0)))

    def test_speed_out_of_range_rejected(self) -> None:
        """Speeds above 999 are rejected."""
        self.assertTrue(is_rejected(make_args(speed=1000.0)))
        self.assertFalse(is_rejected(make_args(speed=999.0)))

    def test_network_args_only_validated_in_network_modes(self) -> None:
        """Regression for finding #3: irrelevant ip/port are ignored."""
        # Bad ip/port are ignored in serial and interactive modes.
        self.assertFalse(is_rejected(make_args(mode="serial", serial_port="/dev/ttyUSB0", ip="999.999.999.999")))
        self.assertFalse(is_rejected(make_args(mode="serial", serial_port="/dev/ttyUSB0", port=70000)))
        self.assertFalse(is_rejected(make_args(mode="interactive", ip="999.999.999.999")))
        # But validated in the network modes that use them.
        self.assertTrue(is_rejected(make_args(mode="tcp-server", ip="999.999.999.999")))
        self.assertTrue(is_rejected(make_args(mode="stream", port=70000)))

    def test_serial_port_required_for_serial_mode(self) -> None:
        """Serial mode without a serial port is rejected."""
        self.assertTrue(is_rejected(make_args(mode="serial", serial_port=None)))
        self.assertFalse(is_rejected(make_args(mode="serial", serial_port="/dev/ttyUSB0")))

    def test_headless_rejected_for_interactive_mode(self) -> None:
        """Headless mode is only valid with direct-start operating modes."""
        self.assertTrue(is_rejected(make_args(mode="interactive", headless=True)))
        self.assertFalse(is_rejected(make_args(mode="tcp-server", headless=True)))
        self.assertFalse(is_rejected(make_args(mode="stream", headless=True)))
        self.assertFalse(is_rejected(make_args(mode="serial", serial_port="/dev/ttyUSB0", headless=True)))


class TestBuildParser(unittest.TestCase):
    """Tests for the argument parser and config builder."""

    def setUp(self) -> None:
        """Create a fresh parser for each test."""
        self.parser = build_parser()

    def test_defaults(self) -> None:
        """Parsing no arguments yields the documented defaults."""
        args = self.parser.parse_args([])
        self.assertEqual(args.mode, "interactive")
        self.assertEqual(args.position, "5430N 01920E")
        self.assertEqual(args.speed, 0.0)
        self.assertEqual(args.heading, 0.0)
        self.assertEqual(args.altitude, 15.2)
        self.assertEqual(args.ip, "127.0.0.1")
        self.assertEqual(args.port, 2020)
        self.assertEqual(args.protocol, "tcp")
        self.assertIsNone(args.serial_port)
        self.assertEqual(args.baudrate, 4800)
        self.assertFalse(args.headless)

    def test_headless_flag(self) -> None:
        """--headless enables headless execution."""
        args = self.parser.parse_args(["--mode", "tcp-server", "--headless"])
        self.assertTrue(args.headless)

    def test_quiet_verbose_mutually_exclusive(self) -> None:
        """--quiet and --verbose cannot be combined."""
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.parser.parse_args(["--quiet", "--verbose"])

    def test_invalid_choices_rejected(self) -> None:
        """Out-of-choice mode/protocol/baudrate values are rejected by argparse."""
        for argv in [["--mode", "bogus"], ["--protocol", "sctp"], ["--baudrate", "1234"]]:
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                self.parser.parse_args(argv)

    def test_build_cli_config_detects_provided(self) -> None:
        """Only explicitly-set navigation args appear in `provided`."""
        args = self.parser.parse_args(["--speed", "12.5", "--heading", "90"])
        position = validate_args(args)
        config = build_cli_config(args, self.parser, position)
        self.assertEqual(config.provided, frozenset({"speed", "heading"}))
        self.assertEqual(config.speed, 12.5)
        self.assertEqual(config.heading, 90.0)

    def test_build_cli_config_carries_headless(self) -> None:
        """Headless execution is carried into the menu config."""
        args = self.parser.parse_args(["--mode", "tcp-server", "--headless"])
        position = validate_args(args)
        config = build_cli_config(args, self.parser, position)
        self.assertTrue(config.headless)

    def test_build_cli_config_no_overrides(self) -> None:
        """With no overrides, `provided` is empty."""
        args = self.parser.parse_args([])
        position = validate_args(args)
        config = build_cli_config(args, self.parser, position)
        self.assertEqual(config.provided, frozenset())

    def test_validate_args_returns_parsed_position(self) -> None:
        """validate_args returns the parsed position dict for reuse."""
        args = self.parser.parse_args(["--position", "4807N 01131E"])
        position = validate_args(args)
        self.assertEqual(position, parse_position("4807N 01131E"))


if __name__ == "__main__":
    unittest.main()
