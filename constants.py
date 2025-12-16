"""Constants used throughout the NMEA GPS Emulator."""

# Network
MAX_TCP_CONNECTIONS = 10
DEFAULT_NMEA_PORT = 10110
DEFAULT_LOCAL_IP = "0.0.0.0"
DEFAULT_REMOTE_IP = "127.0.0.1"

# Timing
NMEA_SEND_INTERVAL_SEC = 1
NMEA_SENTENCE_DELAY_SEC = 0.05

# Navigation
HEADING_INCREMENT_DEG = 3
SPEED_INCREMENT_KNOTS = 3
MAX_HEADING_DEG = 360

# GPS defaults
DEFAULT_HDOP = 0.92
DEFAULT_PDOP = 1.56
DEFAULT_VDOP = 1.25
DEFAULT_ANTENNA_ALTITUDE_MSL = 32.5
DEFAULT_SATELLITES = 15

# Serial
DEFAULT_SERIAL_BAUDRATE = 9600
SUPPORTED_BAUDRATES = [
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
DEFAULT_POSITION = {
    "latitude_value": "5430.000",
    "latitude_direction": "N",
    "longitude_value": "01920.000",
    "longitude_direction": "E",
}
DEFAULT_HEADING = 90.0
DEFAULT_SPEED = 10.5
