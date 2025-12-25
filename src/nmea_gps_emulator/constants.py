"""Constants used throughout the NMEA GPS Emulator."""

# Network
MAX_TCP_CONNECTIONS: int = 10
DEFAULT_NMEA_PORT: int = 10110
DEFAULT_LOCAL_IP: str = "0.0.0.0"  # noqa: S104
DEFAULT_REMOTE_IP: str = "127.0.0.1"

# Timing
NMEA_SEND_INTERVAL_SEC: int = 1
NMEA_SENTENCE_DELAY_SEC: float = 0.05
THREAD_STARTUP_DELAY_SEC: int = 2
SCRIPT_EXIT_DELAY_SEC: int = 1
SOCKET_BIND_RETRY_MINUTES: int = 2

# Timing precision and safety
MIN_SLEEP_TIME_SEC: float = 0.0
TIMING_PRECISION_TOLERANCE: float = 0.001  # 1ms tolerance for timing calculations
MAX_LOOP_EXECUTION_TIME_SEC: float = 0.9  # Maximum allowed loop execution time before warning

# Navigation
HEADING_INCREMENT_DEG: int = 3
SPEED_INCREMENT_KNOTS: int = 3
MAX_HEADING_DEG: int = 360
KNOTS_TO_MS_CONVERSION: float = 0.514444
KNOTS_TO_KMHR_CONVERSION: float = 1.852
MINUTES_PER_DEGREE: int = 60
DEGREES_HALF_CIRCLE: int = 180
MAX_ELEVATION_DEGREES: int = 90
MAX_AZIMUTH_DEGREES: int = 359
MAX_SNR_VALUE: int = 99

# GPS defaults
DEFAULT_HDOP: float = 0.92
DEFAULT_PDOP: float = 1.56
DEFAULT_VDOP: float = 1.25
DEFAULT_ANTENNA_ALTITUDE_MSL: float = 32.5
DEFAULT_SATELLITES: int = 15
DEFAULT_ALTITUDE_AMSL: float = 15.2

# NMEA sentence configuration
MAX_SATELLITES_PER_SENTENCE: int = 4
MIN_SATELLITES_FOR_FIX: int = 4
MAX_SATELLITES_FOR_FIX: int = 12
MAX_SATELLITE_ID: int = 32
GPGSA_MAX_SATELLITE_FIELDS: int = 12
GPS_FIX_QUALITY_VALID: int = 1
GPS_FIX_MODE_3D: int = 3
CHECKSUM_HEX_LENGTH: int = 2

# Coordinate formatting
LATITUDE_FORMAT_WIDTH: int = 8
LATITUDE_FORMAT_PRECISION: int = 3
LONGITUDE_FORMAT_WIDTH: int = 9
LONGITUDE_FORMAT_PRECISION: int = 3
COORDINATE_DEGREES_LAT_WIDTH: int = 2
COORDINATE_DEGREES_LON_WIDTH: int = 3
COORDINATE_MINUTES_WIDTH: int = 6
COORDINATE_MINUTES_PRECISION: int = 3

# Serial
DEFAULT_SERIAL_BAUDRATE: int = 9600
SERIAL_BYTESIZE_DEFAULT: int = 8
SERIAL_STOPBITS_DEFAULT: int = 1
SERIAL_TIMEOUT_DEFAULT: int = 1
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

# Menu choices
MENU_CHOICE_SERIAL: str = "1"
MENU_CHOICE_TCP_SERVER: str = "2"
MENU_CHOICE_STREAM: str = "3"
MENU_CHOICE_QUIT: str = "4"

# Default navigation values for menu
DEFAULT_MENU_SPEED: float = 10.035
DEFAULT_MENU_HEADING: float = 45.0
