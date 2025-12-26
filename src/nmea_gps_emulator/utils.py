"""Utility functions for user input handling and script management."""

import logging
import os
import platform
import re
import time
from re import Match, Pattern
from typing import NoReturn

import psutil
import serial.tools.list_ports
import serial.tools.list_ports_common

from .constants import (
    DEFAULT_HEADING,
    DEFAULT_LOCAL_IP,
    DEFAULT_NMEA_PORT,
    DEFAULT_POSITION,
    DEFAULT_REMOTE_IP,
    DEFAULT_SERIAL_BAUDRATE,
    DEFAULT_SPEED,
    SCRIPT_EXIT_DELAY_SEC,
    SUPPORTED_BAUDRATES,
)


def handle_keyboard_interrupt() -> NoReturn:
    """Handle KeyboardInterrupt by printing a closing message and exiting.

    This function provides a consistent way to handle user interrupts
    (Ctrl+C) throughout the application.

    Raises:
        SystemExit: Always exits the application by raising SystemExit

    """
    print("\n\nClosing...")
    raise SystemExit(0)


def safe_input(prompt: str, default: str | None = None) -> str:
    """Safe input function that handles KeyboardInterrupt consistently.

    Args:
        prompt: The input prompt to display
        default: Default value to return if user presses Enter (optional)

    Returns:
        User input string or default value if user presses Enter

    Raises:
        SystemExit: If user presses Ctrl+C (handled by handle_keyboard_interrupt)

    """
    try:
        user_input: str = input(prompt)
        if user_input == "" and default is not None:
            return default
        return user_input
    except KeyboardInterrupt:
        handle_keyboard_interrupt()


def exit_script() -> None:
    """Terminate the script from inside a child thread.

    Uses psutil to terminate the main process, allowing child threads
    to gracefully shut down the application.

    Returns:
        None

    """
    current_script_pid: int = os.getpid()
    current_script: psutil.Process = psutil.Process(current_script_pid)
    logging.info("Closing the script...")
    time.sleep(SCRIPT_EXIT_DELAY_SEC)
    current_script.terminate()


def position_input() -> dict[str, str]:
    """Prompt user for GPS position and validate the input.

    Accepts GPS coordinates in the format "5430N 01920E" and validates
    them against proper latitude/longitude ranges. Returns default position
    if user presses Enter without input.

    Returns:
        Dictionary with keys: latitude_value, latitude_direction,
        longitude_value, longitude_direction. Returns DEFAULT_POSITION
        if user presses Enter without input.

    Raises:
        SystemExit: If user presses Ctrl+C (handled by safe_input)

    """
    while True:
        print("\nEnter unit position (format: 5430N 01920E)")
        print("Default: 5430N 01920E")
        position_data: str = safe_input("> ", "")

        if position_data == "":
            return DEFAULT_POSITION.copy()

        position_regex_pattern: Pattern[str] = re.compile(
            r"""^(
            ([0-8]\d[0-5]\d|9000)                               # Latitude
            (N|S|n|s)
            \s?
            (([0-1][0-7]\d[0-5]\d)|(0[0-9]\d[0-5]\d)|18000)     # Longitude
            (E|W|e|w)
            )$""",
            re.VERBOSE,
        )
        mo: Match[str] | None = position_regex_pattern.fullmatch(position_data)
        if mo:
            position_dict: dict[str, str] = {
                "latitude_value": f"{float(mo.group(2)):08.3f}",
                "latitude_direction": mo.group(3),
                "longitude_value": f"{float(mo.group(4)):09.3f}",
                "longitude_direction": mo.group(7),
            }
            return position_dict
        print("[ERROR] Invalid position format. Use: 5430N 01920E")


def ip_port_input(option: str) -> tuple[str, int]:
    """Ask for IP address and port number for connection.

    Prompts user for IP:port combination based on the connection type
    (telnet server or stream client) and validates the format.

    Validates IP addresses in range 0.0.0.0 to 255.255.255.255 and
    port numbers in range 1 to 65535.

    Args:
        option: Connection type - "telnet" for local IP or "stream" for remote IP

    Returns:
        Tuple containing (IP address, port number)

    Raises:
        SystemExit: If user presses Ctrl+C (handled by safe_input)

    """
    while True:
        ip_port_socket: str
        if option == "telnet":
            print("\nEnter local IP address and port number")
            print(f"Default: {DEFAULT_LOCAL_IP}:{DEFAULT_NMEA_PORT}")
            ip_port_socket = safe_input("> ", "")
            if ip_port_socket == "":
                return (DEFAULT_LOCAL_IP, DEFAULT_NMEA_PORT)
        elif option == "stream":
            print("\nEnter remote IP address and port number")
            print(f"Default: {DEFAULT_REMOTE_IP}:{DEFAULT_NMEA_PORT}")
            ip_port_socket = safe_input("> ", "")
            if ip_port_socket == "":
                return (DEFAULT_REMOTE_IP, DEFAULT_NMEA_PORT)

        # Improved regex that correctly validates all IP addresses (0.0.0.0 to 255.255.255.255)
        # and port numbers (1 to 65535)
        ip_port_regex_pattern: Pattern[str] = re.compile(
            r"""^
            # IP Address: Each octet can be 0-255
            (
                # First octet: 0-255
                (25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])
                \.
                # Second octet: 0-255
                (25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])
                \.
                # Third octet: 0-255
                (25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])
                \.
                # Fourth octet: 0-255
                (25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])
            )
            :
            # Port: 1-65535 (port 0 is reserved and not allowed)
            (
                6553[0-5]|          # 65530-65535
                655[0-2][0-9]|      # 65500-65529
                65[0-4][0-9]{2}|    # 65000-65499
                6[0-4][0-9]{3}|     # 60000-64999
                [1-5][0-9]{4}|      # 10000-59999
                [1-9][0-9]{0,3}     # 1-9999
            )
            $""",
            re.VERBOSE,
        )
        mo: Match[str] | None = ip_port_regex_pattern.fullmatch(ip_port_socket)
        if mo:
            return (mo.group(1), int(mo.group(6)))
        print("[ERROR] Invalid format. Use: 192.168.10.10:2020")
        print("        IP range: 0.0.0.0 - 255.255.255.255")
        print("        Port range: 1 - 65535")


def trans_proto_input() -> str:
    """Ask for transport protocol for NMEA stream.

    Prompts user to choose between TCP and UDP protocols for streaming
    NMEA data. Defaults to TCP if user presses Enter.

    Returns:
        Protocol string - either "tcp" or "udp"

    Raises:
        SystemExit: If user presses Ctrl+C (handled by safe_input)

    """
    while True:
        print("\nEnter transport protocol (TCP or UDP)")
        print("Default: TCP")
        stream_proto: str = safe_input("> ", "tcp").strip().lower()

        if stream_proto == "" or stream_proto == "tcp":
            return "tcp"
        elif stream_proto == "udp":
            return "udp"
        print("[ERROR] Invalid protocol. Enter 'tcp' or 'udp'")


def heading_input() -> float:
    """Ask for the unit's course.

    Prompts user for heading/course value in degrees (0-359) and validates
    the input. Returns default heading if user presses Enter.

    Returns:
        Course value in degrees (0.0-359.0)

    Raises:
        SystemExit: If user presses Ctrl+C (handled by safe_input)

    """
    while True:
        print("\nEnter unit course (0-359 degrees)")
        print(f"Default: {int(DEFAULT_HEADING):03d}")
        heading_data: str = safe_input("> ", "")

        if heading_data == "":
            return DEFAULT_HEADING

        heading_regex_pattern: str = r"(3[0-5]\d|[0-2]\d{2}|\d{1,2})"
        mo: Match[str] | None = re.fullmatch(heading_regex_pattern, heading_data)
        if mo:
            return float(mo.group())
        print("[ERROR] Invalid heading. Enter a value between 0 and 359 degrees")


def speed_input() -> float:
    """Ask for the unit's speed.

    Prompts user for speed value in knots (0-999) and validates the input.
    Returns default speed if user presses Enter. Handles leading zero
    normalization for proper float conversion.

    Returns:
        Speed value in knots (0.0-999.0)

    Raises:
        SystemExit: If user presses Ctrl+C (handled by safe_input)

    """
    while True:
        print("\nEnter unit speed (0-999 knots)")
        print(f"Default: {DEFAULT_SPEED}")
        speed_data: str = safe_input("> ", "")

        if speed_data == "":
            return DEFAULT_SPEED

        speed_regex_pattern: str = r"(\d{1,3}(\.\d+)?)"
        mo: Match[str] | None = re.fullmatch(speed_regex_pattern, speed_data)
        if mo:
            match: str = mo.group()
            if match.startswith("0") and match != "0" and not match.startswith("0."):
                match = match.lstrip("0")
            speed_value: float = float(match)
            # Validate range
            if 0 <= speed_value <= 999:
                return speed_value
        print("[ERROR] Invalid speed. Enter a value between 0 and 999 knots")


def heading_speed_input() -> tuple[float, float]:
    """Ask for the unit's heading and speed (online).

    Interactive function for updating course and speed while the emulator
    is running. Prompts for both values sequentially and validates input.

    Returns:
        Tuple containing (new_heading, new_speed) in degrees and knots

    Raises:
        SystemExit: If user presses Ctrl+C (handled by safe_input)

    """
    heading_new: float
    while True:
        heading_data: str = safe_input("New course (0-359 degrees) > ")
        heading_regex_pattern: str = r"(3[0-5]\d|[0-2]\d{2}|\d{1,2})"
        mo: Match[str] | None = re.fullmatch(heading_regex_pattern, heading_data)
        if mo:
            heading_new = float(mo.group())
            break
        print("[ERROR] Invalid heading. Enter a value between 0 and 359 degrees")

    speed_new: float
    while True:
        speed_data: str = safe_input("New speed (0-999 knots) > ")
        speed_regex_pattern: str = r"(\d{1,3}(\.\d+)?)"
        mo = re.fullmatch(speed_regex_pattern, speed_data)
        if mo:
            match: str = mo.group()
            if match.startswith("0") and match != "0" and not match.startswith("0."):
                match = match.lstrip("0")
            speed_new = float(match)
            # Validate range
            if 0 <= speed_new <= 999:
                break
        print("[ERROR] Invalid speed. Enter a value between 0 and 999 knots")

    return heading_new, speed_new


def serial_config_input() -> dict[str, str | int]:
    """Ask for serial configuration.

    Prompts user to configure serial port settings including port selection
    and baudrate. Automatically detects available ports and validates
    user selections against connected devices and supported baudrates.

    Returns:
        Dictionary containing serial configuration with keys:
        - port: Serial port device path/name
        - baudrate: Communication speed in bps
        - bytesize: Data bits (fixed at 8)
        - parity: Parity setting (fixed at 'N')
        - stopbits: Stop bits (fixed at 1)
        - timeout: Read timeout in seconds (fixed at 1)

    Raises:
        SystemExit: If user presses Ctrl+C (handled by safe_input)

    """
    serial_set: dict[str, str | int] = {
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
        "timeout": 1,
    }

    ports_connected: list[serial.tools.list_ports_common.ListPortInfo] = serial.tools.list_ports.comports(
        include_links=False
    )
    ports_connected_names: list[str] = [port.device for port in ports_connected]
    print("\nConnected serial ports:")
    for port in sorted(ports_connected):
        print(f"  - {port}")
    platform_os: str = platform.system()

    serial_port: str
    while True:
        if platform_os.lower() == "linux":
            print("\nChoose serial port")
            print("Default: /dev/ttyUSB0")
            serial_port = safe_input("> ", "/dev/ttyUSB0")
        elif platform_os.lower() == "windows":
            print("\nChoose serial port")
            print("Default: COM1")
            serial_port = safe_input("> ", "COM1")
        else:
            # Fallback for other platforms
            print("\nChoose serial port")
            print("Default: /dev/ttyUSB0")
            serial_port = safe_input("> ", "/dev/ttyUSB0")

        if serial_port in ports_connected_names:
            serial_set["port"] = serial_port
            break
        print(f"[ERROR] Invalid port name: {serial_port}")

    while True:
        print("\nEnter serial baudrate")
        print(f"Default: {DEFAULT_SERIAL_BAUDRATE}")
        baudrate: str = safe_input("> ", str(DEFAULT_SERIAL_BAUDRATE))

        if baudrate in SUPPORTED_BAUDRATES:
            serial_set["baudrate"] = int(baudrate)
            break
        print(f"[ERROR] Invalid baudrate: {baudrate}")

    return serial_set
