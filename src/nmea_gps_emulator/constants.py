"""Constants used throughout the NMEA GPS Emulator."""

# Network
MAX_TCP_CONNECTIONS: int = 10
DEFAULT_NMEA_PORT: int = 10110
DEFAULT_LOCAL_IP: str = "0.0.0.0"  # noqa: S104
DEFAULT_REMOTE_IP: str = "127.0.0.1"

# Timing
NMEA_SEND_INTERVAL_SEC: int = 1
NMEA_SENTENCE_DELAY_SEC: float = 0.05

# Navigation
HEADING_INCREMENT_DEG: int = 3
SPEED_INCREMENT_KNOTS: int = 3
MAX_HEADING_DEG: int = 360

# GPS defaults
DEFAULT_HDOP: float = 0.92
DEFAULT_PDOP: float = 1.56
DEFAULT_VDOP: float = 1.25
DEFAULT_ANTENNA_ALTITUDE_MSL: float = 32.5
DEFAULT_SATELLITES: int = 15

# Serial
DEFAULT_SERIAL_BAUDRATE: int = 9600
SUPPORTED_BAUDRATES: list[str] = [
    "300",
    "600",
    "1200",
    "2400",
    "4800",
    "9600",
    "14400",
    "19200",
    "38400",
    "57600",
    "115200",
    "128000",
]

# Default position (Baltic Sea)
DEFAULT_POSITION: dict[str, str] = {
    "latitude_value": "5430.000",
    "latitude_direction": "N",
    "longitude_value": "01920.000",
    "longitude_direction": "E",
}
DEFAULT_HEADING: float = 90.0
DEFAULT_SPEED: float = 10.5
