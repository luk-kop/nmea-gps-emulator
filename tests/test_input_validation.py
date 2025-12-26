"""Comprehensive tests for input validation functions."""

import unittest
from unittest.mock import patch

from nmea_gps_emulator.utils import (
    heading_input,
    ip_port_input,
    position_input,
    speed_input,
    trans_proto_input,
)


class TestIPPortValidation(unittest.TestCase):
    """Test IP address and port validation."""

    def test_valid_ip_port_combinations(self) -> None:
        """Test valid IP:port combinations."""
        valid_cases = [
            ("192.168.1.1:8080", ("192.168.1.1", 8080)),
            ("0.0.0.0:10110", ("0.0.0.0", 10110)),
            ("127.0.0.1:1", ("127.0.0.1", 1)),
            ("255.255.255.255:65535", ("255.255.255.255", 65535)),
            ("10.0.0.1:80", ("10.0.0.1", 80)),
            ("172.16.0.1:443", ("172.16.0.1", 443)),
            ("192.168.0.1:22", ("192.168.0.1", 22)),
            ("1.1.1.1:53", ("1.1.1.1", 53)),
        ]

        for input_str, expected in valid_cases:
            with patch("nmea_gps_emulator.utils.safe_input", return_value=input_str):
                result = ip_port_input("telnet")
                self.assertEqual(
                    result,
                    expected,
                    f"Failed for input: {input_str}, expected {expected}, got {result}",
                )

    def test_invalid_ip_addresses(self) -> None:
        """Test invalid IP addresses are rejected."""
        invalid_cases = [
            "256.1.1.1:8080",  # Octet > 255
            "192.168.1.256:8080",  # Last octet > 255
            "192.168.300.1:8080",  # Third octet > 255
            "999.999.999.999:8080",  # All octets invalid
            "192.168.1:8080",  # Missing octet
            "192.168.1.1.1:8080",  # Too many octets
            "192.168.-1.1:8080",  # Negative octet
            "a.b.c.d:8080",  # Non-numeric octets
        ]

        for invalid_input in invalid_cases:
            with patch(
                "nmea_gps_emulator.utils.safe_input",
                side_effect=[invalid_input, "127.0.0.1:8080"],
            ):
                result = ip_port_input("telnet")
                # Should reject invalid and accept valid
                self.assertEqual(result, ("127.0.0.1", 8080))

    def test_invalid_ports(self) -> None:
        """Test invalid port numbers are rejected."""
        invalid_cases = [
            "192.168.1.1:0",  # Port 0 (should be 1-65535)
            "192.168.1.1:65536",  # Port > 65535
            "192.168.1.1:99999",  # Port way too high
            "192.168.1.1:-1",  # Negative port
            "192.168.1.1:abc",  # Non-numeric port
            "192.168.1.1:",  # Missing port
            "192.168.1.1",  # No colon or port
        ]

        for invalid_input in invalid_cases:
            with patch(
                "nmea_gps_emulator.utils.safe_input",
                side_effect=[invalid_input, "127.0.0.1:8080"],
            ):
                result = ip_port_input("telnet")
                self.assertEqual(result, ("127.0.0.1", 8080))

    def test_edge_case_ports(self) -> None:
        """Test edge case port numbers."""
        edge_cases = [
            ("192.168.1.1:1", ("192.168.1.1", 1)),  # Minimum valid port
            ("192.168.1.1:65535", ("192.168.1.1", 65535)),  # Maximum valid port
            ("192.168.1.1:1024", ("192.168.1.1", 1024)),  # Common boundary
            ("192.168.1.1:8080", ("192.168.1.1", 8080)),  # Common port
        ]

        for input_str, expected in edge_cases:
            with patch("nmea_gps_emulator.utils.safe_input", return_value=input_str):
                result = ip_port_input("telnet")
                self.assertEqual(result, expected)

    def test_edge_case_ips(self) -> None:
        """Test edge case IP addresses."""
        edge_cases = [
            ("0.0.0.0:8080", ("0.0.0.0", 8080)),  # All zeros
            ("255.255.255.255:8080", ("255.255.255.255", 8080)),  # All max
            ("127.0.0.1:8080", ("127.0.0.1", 8080)),  # Localhost
            ("10.0.0.1:8080", ("10.0.0.1", 8080)),  # Private range
            ("172.16.0.1:8080", ("172.16.0.1", 8080)),  # Private range
            ("192.168.0.1:8080", ("192.168.0.1", 8080)),  # Private range
        ]

        for input_str, expected in edge_cases:
            with patch("nmea_gps_emulator.utils.safe_input", return_value=input_str):
                result = ip_port_input("telnet")
                self.assertEqual(result, expected)

    def test_default_values(self) -> None:
        """Test default values are returned on empty input."""
        with patch("nmea_gps_emulator.utils.safe_input", return_value=""):
            result_telnet = ip_port_input("telnet")
            self.assertEqual(result_telnet, ("0.0.0.0", 10110))

            result_stream = ip_port_input("stream")
            self.assertEqual(result_stream, ("127.0.0.1", 10110))


class TestPositionValidation(unittest.TestCase):
    """Test GPS position validation."""

    def test_valid_positions(self) -> None:
        """Test valid GPS positions."""
        valid_cases = [
            "5430N 01920E",  # Standard format
            "5430N01920E",  # No space
            "0000N 00000E",  # Minimum values
            "9000N 18000E",  # Maximum values
            "5430S 01920W",  # Southern/Western hemisphere
            "5430s 01920w",  # Lowercase directions
        ]

        for valid_input in valid_cases:
            with patch("nmea_gps_emulator.utils.safe_input", return_value=valid_input):
                result = position_input()
                self.assertIsInstance(result, dict)
                self.assertIn("latitude_value", result)
                self.assertIn("longitude_value", result)

    def test_invalid_positions(self) -> None:
        """Test invalid GPS positions are rejected."""
        invalid_cases = [
            "9001N 01920E",  # Latitude > 9000
            "5430N 18001E",  # Longitude > 18000
            "5430 01920E",  # Missing latitude direction
            "5430N 01920",  # Missing longitude direction
            "ABC N 01920E",  # Non-numeric latitude
            "5430N ABCDE",  # Non-numeric longitude
        ]

        for invalid_input in invalid_cases:
            with patch(
                "nmea_gps_emulator.utils.safe_input",
                side_effect=[invalid_input, "5430N 01920E"],
            ):
                result = position_input()
                # Should reject invalid and accept valid
                self.assertIsInstance(result, dict)


class TestHeadingValidation(unittest.TestCase):
    """Test heading/course validation."""

    def test_valid_headings(self) -> None:
        """Test valid heading values."""
        valid_cases = [
            ("0", 0.0),
            ("90", 90.0),
            ("180", 180.0),
            ("270", 270.0),
            ("359", 359.0),
            ("45", 45.0),
            ("123", 123.0),
        ]

        for input_str, expected in valid_cases:
            with patch("nmea_gps_emulator.utils.safe_input", return_value=input_str):
                result = heading_input()
                self.assertEqual(result, expected)

    def test_invalid_headings(self) -> None:
        """Test invalid heading values are rejected."""
        invalid_cases = [
            "360",  # >= 360
            "400",  # Way too high
            "-1",  # Negative
            "abc",  # Non-numeric
        ]

        for invalid_input in invalid_cases:
            with patch(
                "nmea_gps_emulator.utils.safe_input",
                side_effect=[invalid_input, "90"],
            ):
                result = heading_input()
                self.assertEqual(result, 90.0)


class TestSpeedValidation(unittest.TestCase):
    """Test speed validation."""

    def test_valid_speeds(self) -> None:
        """Test valid speed values."""
        valid_cases = [
            ("0", 0.0),
            ("10", 10.0),
            ("10.5", 10.5),
            ("999", 999.0),
            ("0.1", 0.1),
            ("123.456", 123.456),
        ]

        for input_str, expected in valid_cases:
            with patch("nmea_gps_emulator.utils.safe_input", return_value=input_str):
                result = speed_input()
                self.assertEqual(result, expected)

    def test_invalid_speeds(self) -> None:
        """Test invalid speed values are rejected."""
        invalid_cases = [
            "1000",  # > 999
            "-1",  # Negative
            "abc",  # Non-numeric
            "10.5.5",  # Multiple decimals
        ]

        for invalid_input in invalid_cases:
            with patch(
                "nmea_gps_emulator.utils.safe_input",
                side_effect=[invalid_input, "10"],
            ):
                result = speed_input()
                self.assertEqual(result, 10.0)


class TestTransportProtocolValidation(unittest.TestCase):
    """Test transport protocol validation."""

    def test_valid_protocols(self) -> None:
        """Test valid protocol inputs."""
        valid_cases = [
            ("tcp", "tcp"),
            ("TCP", "tcp"),
            ("udp", "udp"),
            ("UDP", "udp"),
            ("", "tcp"),  # Default
            ("  tcp  ", "tcp"),  # With whitespace
        ]

        for input_str, expected in valid_cases:
            with patch("nmea_gps_emulator.utils.safe_input", return_value=input_str):
                result = trans_proto_input()
                self.assertEqual(result, expected)

    def test_invalid_protocols(self) -> None:
        """Test invalid protocol inputs are rejected."""
        invalid_cases = ["http", "ftp", "xyz", "123"]

        for invalid_input in invalid_cases:
            with patch(
                "nmea_gps_emulator.utils.safe_input",
                side_effect=[invalid_input, "tcp"],
            ):
                result = trans_proto_input()
                self.assertEqual(result, "tcp")


if __name__ == "__main__":
    unittest.main()
