"""NMEA GPS message generation and handling classes."""

from __future__ import annotations

import datetime
import random
from math import ceil

from pyproj import Geod

from .constants import (
    CHECKSUM_HEX_LENGTH,
    COORDINATE_DEGREES_LAT_WIDTH,
    COORDINATE_DEGREES_LON_WIDTH,
    COORDINATE_MINUTES_PRECISION,
    COORDINATE_MINUTES_WIDTH,
    DEFAULT_ANTENNA_ALTITUDE_MSL,
    DEFAULT_HDOP,
    DEFAULT_PDOP,
    DEFAULT_SATELLITES,
    DEFAULT_VDOP,
    DEGREES_HALF_CIRCLE,
    GPGSA_MAX_SATELLITE_FIELDS,
    GPS_FIX_MODE_3D,
    GPS_FIX_QUALITY_VALID,
    HEADING_INCREMENT_DEG,
    KNOTS_TO_KMHR_CONVERSION,
    KNOTS_TO_MS_CONVERSION,
    MAX_AZIMUTH_DEGREES,
    MAX_ELEVATION_DEGREES,
    MAX_HEADING_DEG,
    MAX_SATELLITE_ID,
    MAX_SATELLITES_FOR_FIX,
    MAX_SATELLITES_PER_SENTENCE,
    MAX_SNR_VALUE,
    MIN_SATELLITES_FOR_FIX,
    MINUTES_PER_DEGREE,
    SPEED_INCREMENT_KNOTS,
)


class NmeaMsg:
    """The class represent a group of NMEA sentences.

    Main orchestrator class that generates and manages all NMEA sentence types,
    handles position updates using WGS84 geodetic calculations, and manages
    speed/heading changes over time.
    """

    def __init__(self, position: dict[str, str], altitude: float, speed: float, heading: float) -> None:
        """Initialize NMEA message generator with position, altitude, speed, and heading.

        Args:
            position: Dictionary containing GPS coordinates with keys:
                     latitude_value, latitude_direction, longitude_value, longitude_direction
            altitude: Altitude above sea level in meters
            speed: Initial speed in knots
            heading: Initial heading/course in degrees (0-359)

        Returns:
            None

        """
        # Instance attributes
        self.utc_date_time: datetime.datetime = datetime.datetime.now(datetime.UTC)
        self.position: dict[str, str] = position
        self.speed: float = speed
        # The unit's speed provided by the user during the operation of the script
        self.speed_targeted: float = speed
        self.heading: float = heading
        # The unit's heading provided by the user during the operation of the script
        self.heading_targeted: float = heading
        # NMEA sentences initialization - by default with 15 sats
        self.gpgsv_group: GpgsvGroup = GpgsvGroup(sats_total=DEFAULT_SATELLITES)
        self.gpgsa: Gpgsa = Gpgsa(gpgsv_group=self.gpgsv_group)
        self.gga: Gpgga = Gpgga(
            sats_count=self.gpgsa.sats_count,
            utc_date_time=self.utc_date_time,
            position=position,
            altitude=altitude,
            antenna_altitude_above_msl=DEFAULT_ANTENNA_ALTITUDE_MSL,
        )
        self.gpgll: Gpgll = Gpgll(utc_date_time=self.utc_date_time, position=position)
        self.gprmc: Gprmc = Gprmc(utc_date_time=self.utc_date_time, position=position, sog=speed, cmg=heading)
        self.gphdt: Gphdt = Gphdt(heading=heading)
        self.gpvtg: Gpvtg = Gpvtg(heading_true=heading, sog_knots=speed)
        self.gpzda: Gpzda = Gpzda(utc_date_time=self.utc_date_time)
        self.nmea_sentences: list[Gpgga | Gpgsa | Gpgsv | Gpgll | Gprmc | Gphdt | Gpvtg | Gpzda] = [
            self.gga,
            self.gpgsa,
            *list(self.gpgsv_group.gpgsv_instances),
            self.gpgll,
            self.gprmc,
            self.gphdt,
            self.gpvtg,
            self.gpzda,
        ]

    def __next__(
        self,
    ) -> list[Gpgga | Gpgsa | Gpgsv | Gpgll | Gprmc | Gphdt | Gpvtg | Gpzda]:
        """Generate next set of NMEA sentences with updated position and parameters.

        Updates position based on elapsed time and current speed/heading,
        gradually adjusts heading and speed toward target values, and
        refreshes all NMEA sentences with current data.

        Returns:
            List of updated NMEA sentence objects

        """
        utc_date_time_prev = self.utc_date_time
        self.utc_date_time = datetime.datetime.now(datetime.UTC)
        if self.speed > 0:
            self.position_update(utc_date_time_prev)
        if self.heading != self.heading_targeted:
            self._heading_update()
        if self.speed != self.speed_targeted:
            self._speed_update()
        self.gga.utc_time = self.utc_date_time
        self.gpgll.utc_time = self.utc_date_time
        self.gprmc.utc_time = self.utc_date_time
        self.gprmc.sog = self.speed
        self.gprmc.cmg = self.heading
        self.gphdt.heading = self.heading
        self.gpvtg.heading_true = self.heading
        self.gpvtg.sog_knots = self.speed
        self.gpzda.utc_time = self.utc_date_time
        return self.nmea_sentences

    def __iter__(self) -> NmeaMsg:
        """Return iterator for NMEA message generation.

        Returns:
            Self as iterator object

        """
        return self

    def __str__(self) -> str:
        """Return formatted string of all NMEA sentences.

        Returns:
            Concatenated string containing all NMEA sentences

        """
        nmea_msgs_str: str = ""
        for nmea in self.nmea_sentences:
            nmea_msgs_str += f"{nmea}"
        return nmea_msgs_str

    def position_update(self, utc_date_time_prev: datetime.datetime) -> None:
        """Update position when unit in move.

        Calculates new GPS position based on elapsed time, current speed,
        and heading using WGS84 geodetic calculations. Handles coordinate
        conversion and direction changes when crossing equator or prime meridian.

        Args:
            utc_date_time_prev: Previous timestamp for calculating time delta

        Returns:
            None

        """
        # The time that has elapsed since the last fix
        time_delta = (self.utc_date_time - utc_date_time_prev).total_seconds()
        # Knots to m/s conversion.
        speed_ms = self.speed * KNOTS_TO_MS_CONVERSION
        # Distance in meters.
        distance = speed_ms * time_delta
        # Assignment of coords.
        lat_a = self.position["latitude_value"]
        lat_direction = self.position["latitude_direction"]
        lon_a = self.position["longitude_value"]
        lon_direction = self.position["longitude_direction"]
        # Convert current position (start position) format to compatible with 'Geod.fwd' func.
        if lat_direction.lower() == "n":
            lat_start = float(lat_a[:COORDINATE_DEGREES_LAT_WIDTH]) + (
                float(lat_a[COORDINATE_DEGREES_LAT_WIDTH:]) / MINUTES_PER_DEGREE
            )
        else:
            lat_start = -float(lat_a[:COORDINATE_DEGREES_LAT_WIDTH]) - (
                float(lat_a[COORDINATE_DEGREES_LAT_WIDTH:]) / MINUTES_PER_DEGREE
            )
        if lon_direction.lower() == "e":
            lon_start = float(lon_a[:COORDINATE_DEGREES_LON_WIDTH]) + (
                float(lon_a[COORDINATE_DEGREES_LON_WIDTH:]) / MINUTES_PER_DEGREE
            )
        else:
            lon_start = -float(lon_a[:COORDINATE_DEGREES_LON_WIDTH]) - (
                float(lon_a[COORDINATE_DEGREES_LON_WIDTH:]) / MINUTES_PER_DEGREE
            )
        # Use WGS84 ellipsoid.
        g = Geod(ellps="WGS84")
        # Forward transformation - returns longitude, latitude, back azimuth of terminus points
        lon_end, lat_end, back_azimuth = g.fwd(lon_start, lat_start, self.heading, distance)
        # Change direction when cross the equator or prime meridian (Greenwich)
        lat_direction = "N" if lat_end >= 0 else "S"
        lon_direction = "E" if lon_end >= 0 else "W"
        lon_end, lat_end = abs(lon_end), abs(lat_end)
        # New GPS position after calculation.
        lat_degrees = int(lat_end)
        try:
            lat_minutes = round(lat_end % int(lat_end) * MINUTES_PER_DEGREE, COORDINATE_MINUTES_PRECISION)
        except ZeroDivisionError:
            lat_minutes = round(lat_end * MINUTES_PER_DEGREE, COORDINATE_MINUTES_PRECISION)
        if lat_minutes == MINUTES_PER_DEGREE:
            lat_degrees += 1
            lat_minutes = 0
        lon_degrees = int(lon_end)
        try:
            lon_minutes = round(lon_end % int(lon_end) * MINUTES_PER_DEGREE, COORDINATE_MINUTES_PRECISION)
        except ZeroDivisionError:
            lon_minutes = round(lon_end * MINUTES_PER_DEGREE, COORDINATE_MINUTES_PRECISION)
        if lon_minutes == MINUTES_PER_DEGREE:
            lon_degrees += 1
            lon_minutes = 0
        self.position["latitude_value"] = (
            f"{lat_degrees:0{COORDINATE_DEGREES_LAT_WIDTH}}{lat_minutes:0{COORDINATE_MINUTES_WIDTH}.{COORDINATE_MINUTES_PRECISION}f}"
        )
        self.position["latitude_direction"] = f"{lat_direction.upper()}"
        self.position["longitude_value"] = (
            f"{lon_degrees:0{COORDINATE_DEGREES_LON_WIDTH}}{lon_minutes:0{COORDINATE_MINUTES_WIDTH}.{COORDINATE_MINUTES_PRECISION}f}"
        )
        self.position["longitude_direction"] = f"{lon_direction.upper()}"

    def _heading_update(self) -> None:
        """Update the unit's heading (course) when changed by user.

        Gradually adjusts current heading toward target heading using
        incremental changes. Handles wraparound at 0/360 degrees and
        chooses shortest rotation path.

        Returns:
            None

        """
        head_target: float = self.heading_targeted
        head_current: float = self.heading
        turn_angle = head_target - head_current
        # Immediate change of course when the increment <= turn_angle
        if abs(turn_angle) <= HEADING_INCREMENT_DEG:
            head_current = head_target
        else:
            # The unit's heading is increased gradually
            if head_target > head_current:
                if abs(turn_angle) > DEGREES_HALF_CIRCLE:
                    if turn_angle > 0:
                        head_current -= HEADING_INCREMENT_DEG
                    else:
                        head_current += HEADING_INCREMENT_DEG
                else:
                    if turn_angle > 0:
                        head_current += HEADING_INCREMENT_DEG
                    else:
                        head_current -= HEADING_INCREMENT_DEG
            else:
                if abs(turn_angle) > DEGREES_HALF_CIRCLE:
                    if turn_angle > 0:
                        head_current -= HEADING_INCREMENT_DEG
                    else:
                        head_current += HEADING_INCREMENT_DEG
                else:
                    if turn_angle > 0:
                        head_current += HEADING_INCREMENT_DEG
                    else:
                        head_current -= HEADING_INCREMENT_DEG
        # Heading range: 0-359
        if head_current == MAX_HEADING_DEG:
            head_current = 0
        elif head_current > MAX_HEADING_DEG:
            head_current -= MAX_HEADING_DEG
        elif head_current < 0:
            head_current += MAX_HEADING_DEG
        self.heading = round(head_current, 1)

    def _speed_update(self) -> None:
        """Update the unit's speed when changed by user.

        Gradually adjusts current speed toward target speed using
        incremental changes to simulate realistic acceleration/deceleration.

        Returns:
            None

        """
        speed_target: float = self.speed_targeted
        speed_current: float = self.speed
        speed_diff: float = speed_target - speed_current
        # Immediate change of speed when the increment <= speed_diff
        if abs(speed_diff) <= SPEED_INCREMENT_KNOTS:
            speed_current = speed_target
        elif speed_target > speed_current:
            speed_current += SPEED_INCREMENT_KNOTS
        else:
            speed_current -= SPEED_INCREMENT_KNOTS
        self.speed = round(speed_current, 3)

    @staticmethod
    def check_sum(data: str):
        """Calculate NMEA checksum for given data string.

        Performs XOR operation on all bytes between $ and * delimiters
        and returns checksum in hexadecimal notation.

        Args:
            data: NMEA sentence data (without $ prefix and * suffix)

        Returns:
            Two-character uppercase hexadecimal checksum string

        """
        check_sum: int = 0
        for char in data:
            num = bytearray(char, encoding="utf-8")[0]
            # XOR operation.
            check_sum = check_sum ^ num
        # Returns only hex digits string without leading 0x.
        hex_str: str = str(hex(check_sum))[CHECKSUM_HEX_LENGTH:]
        if len(hex_str) == CHECKSUM_HEX_LENGTH:
            return hex_str.upper()
        return f"0{hex_str}".upper()


class Gpgga:
    """Global Positioning System Fix Data.

    Provides essential GPS fix information including position, time,
    fix quality, number of satellites, and altitude data.

    Example: $GPGGA,140041.00,5436.70976,N,01839.98065,E,1,09,0.87,21.7,M,32.5,M,,*60
    """

    sentence_id: str = "GPGGA"

    def __init__(
        self,
        sats_count: int,
        utc_date_time: datetime.datetime,
        position: dict[str, str],
        altitude: float,
        antenna_altitude_above_msl: float = DEFAULT_ANTENNA_ALTITUDE_MSL,
        fix_quality: int = GPS_FIX_QUALITY_VALID,
        hdop: float = DEFAULT_HDOP,
        dgps_last_update: str = "",
        dgps_ref_station_id: str = "",
    ) -> None:
        """Initialize GPGGA sentence with position and satellite data.

        Args:
            sats_count: Number of satellites used in position fix
            utc_date_time: Current UTC date and time
            position: GPS coordinates dictionary
            altitude: Altitude above sea level in meters
            antenna_altitude_above_msl: Antenna height above mean sea level in meters
            fix_quality: GPS fix quality indicator (0=invalid, 1=GPS fix, 2=DGPS fix)
            hdop: Horizontal dilution of precision
            dgps_last_update: Time since last DGPS update (empty if not used)
            dgps_ref_station_id: DGPS reference station ID (empty if not used)

        Returns:
            None

        """
        self.sats_count: int = sats_count
        self.utc_time = utc_date_time
        self.position: dict[str, str] = position
        self.fix_quality: int = fix_quality
        self.hdop: float = hdop
        self.altitude: float = altitude
        self.antenna_altitude_above_msl: float = antenna_altitude_above_msl
        self.dgps_last_update: str = dgps_last_update
        self.dgps_ref_station_id: str = dgps_ref_station_id

    @property
    def utc_time(self) -> str:
        """Get UTC time in HHMMSS format.

        Returns:
            UTC time as string in HHMMSS format

        """
        return self._utc_time

    @utc_time.setter
    def utc_time(self, value: datetime.datetime) -> None:
        """Set UTC time from datetime object.

        Args:
            value: Datetime object to extract time from

        Returns:
            None

        """
        self._utc_time = value.strftime("%H%M%S")

    def __str__(self) -> str:
        """Return formatted GPGGA sentence string.

        Returns:
            Complete GPGGA NMEA sentence with checksum and line terminators

        """
        nmea_output = (
            f"{self.sentence_id},{self.utc_time}.00,{self.position['latitude_value']},"
            f"{self.position['latitude_direction']},{self.position['longitude_value']},"
            f"{self.position['longitude_direction']},{self.fix_quality},"
            f"{self.sats_count:02d},{self.hdop},{self.altitude},M,"
            f"{self.antenna_altitude_above_msl},M,{self.dgps_last_update},"
            f"{self.dgps_ref_station_id}"
        )
        return f"${nmea_output}*{NmeaMsg.check_sum(nmea_output)}\r\n"


class Gpgll:
    """Position data: position fix, time of position fix, and status.

    Provides geographic position (latitude/longitude), UTC time of position fix,
    and data validity status information.

    Example: $GPGLL,5432.216118,N,01832.663994,E,095942.000,A,A*58
    """

    sentence_id: str = "GPGLL"

    def __init__(
        self,
        utc_date_time: datetime.datetime,
        position: dict[str, str],
        data_status: str = "A",
        faa_mode: str = "A",
    ) -> None:
        """Initialize GPGLL sentence with position and time data.

        Args:
            utc_date_time: Current UTC date and time
            position: GPS coordinates dictionary
            data_status: Data validity status ('A'=valid, 'V'=invalid)
            faa_mode: FAA mode indicator (NMEA 2.3+) ('A'=autonomous, 'D'=differential, etc.)

        Returns:
            None

        """
        # UTC time in format: 211250
        self.utc_time = utc_date_time
        self.position: dict[str, str] = position
        self.data_status: str = data_status
        # FAA Mode option in NMEA 2.3 and later
        self.faa_mode: str = faa_mode

    @property
    def utc_time(self) -> str:
        """Get UTC time in HHMMSS format.

        Returns:
            UTC time as string in HHMMSS format

        """
        return self._utc_time

    @utc_time.setter
    def utc_time(self, value: datetime.datetime) -> None:
        """Set UTC time from datetime object.

        Args:
            value: Datetime object to extract time from

        Returns:
            None

        """
        self._utc_time = value.strftime("%H%M%S")

    def __str__(self) -> str:
        """Return formatted GPGLL sentence string.

        Returns:
            Complete GPGLL NMEA sentence with checksum and line terminators

        """
        nmea_output = (
            f"{self.sentence_id},{self.position['latitude_value']},"
            f"{self.position['latitude_direction']},{self.position['longitude_value']},"
            f"{self.position['longitude_direction']},{self.utc_time}.000,"
            f"{self.data_status},{self.faa_mode}"
        )
        return f"${nmea_output}*{NmeaMsg.check_sum(nmea_output)}\r\n"


class Gprmc:
    """Recommended minimum specific GPS/Transit data.

    Contains the most essential GPS navigation information including position,
    speed over ground, course made good, date, and time.

    Example: $GPRMC,095940.000,A,5432.216088,N,01832.664132,E,0.019,0.00,130720,,,A*59
    """

    sentence_id: str = "GPRMC"

    def __init__(
        self,
        utc_date_time: datetime.datetime,
        position: dict[str, str],
        sog: float,
        cmg: float,
        data_status: str = "A",
        faa_mode: str = "A",
        magnetic_var_value: str = "",
        magnetic_var_direct: str = "",
    ) -> None:
        """Initialize GPRMC sentence with position, speed, and course data.

        Args:
            utc_date_time: Current UTC date and time
            position: GPS coordinates dictionary
            sog: Speed over ground in knots
            cmg: Course made good in degrees
            data_status: Data validity status ('A'=valid, 'V'=invalid)
            faa_mode: FAA mode indicator (NMEA 2.3+)
            magnetic_var_value: Magnetic variation value (empty if not available)
            magnetic_var_direct: Magnetic variation direction ('E' or 'W')

        Returns:
            None

        """
        # UTC time in format: 211250
        self.utc_time = utc_date_time
        # UTC date in format: 130720
        self.data_status: str = data_status
        self.position: dict[str, str] = position
        # Speed Over Ground
        self.sog: float = sog
        # Course Made Good
        self.cmg: float = cmg
        self.magnetic_var_value: str = magnetic_var_value
        self.magnetic_var_direct: str = magnetic_var_direct
        # FAA Mode option in NMEA 2.3 and later
        self.faa_mode: str = faa_mode

    @property
    def utc_time(self) -> str:
        """Get UTC time in HHMMSS format.

        Returns:
            UTC time as string in HHMMSS format

        """
        return self._utc_time

    @utc_time.setter
    def utc_time(self, value: datetime.datetime) -> None:
        """Set UTC time and date from datetime object.

        Args:
            value: Datetime object to extract time and date from

        Returns:
            None

        """
        self._utc_time = value.strftime("%H%M%S")
        self._utc_date = value.strftime("%d%m%y")

    @property
    def utc_date(self) -> str:
        """Get UTC date in DDMMYY format.

        Returns:
            UTC date as string in DDMMYY format

        """
        return self._utc_date

    @utc_date.setter
    def utc_date(self, value: datetime.datetime) -> None:
        """Set UTC date from datetime object.

        Args:
            value: Datetime object to extract date from

        Returns:
            None

        """
        self._utc_date = value.strftime("%d%m%y")

    def __str__(self) -> str:
        """Return formatted GPRMC sentence string.

        Returns:
            Complete GPRMC NMEA sentence with checksum and line terminators

        """
        nmea_output = (
            f"{self.sentence_id},{self.utc_time}.000,{self.data_status},"
            f"{self.position['latitude_value']},{self.position['latitude_direction']},"
            f"{self.position['longitude_value']},{self.position['longitude_direction']},"
            f"{self.sog:.3f},{self.cmg},{self.utc_date},"
            f"{self.magnetic_var_value},{self.magnetic_var_direct},{self.faa_mode}"
        )
        return f"${nmea_output}*{NmeaMsg.check_sum(nmea_output)}\r\n"


class Gpgsa:
    """GPS DOP and active satellites.

    Provides information about GPS fix mode, satellites used in position
    calculation, and dilution of precision (DOP) values.

    Example: $GPGSA,A,3,19,28,14,18,27,22,31,39,,,,,1.7,1.0,1.3*35
    """

    sentence_id: str = "GPGSA"

    def __init__(
        self,
        gpgsv_group: GpgsvGroup,
        select_mode: str = "A",
        mode: int = GPS_FIX_MODE_3D,
        pdop: float = DEFAULT_PDOP,
        hdop: float = DEFAULT_HDOP,
        vdop: float = DEFAULT_VDOP,
    ) -> None:
        """Initialize GPGSA sentence with satellite and DOP data.

        Args:
            gpgsv_group: GPGSV group containing satellite information
            select_mode: Selection mode ('A'=automatic, 'M'=manual)
            mode: Fix mode (1=no fix, 2=2D fix, 3=3D fix)
            pdop: Position dilution of precision
            hdop: Horizontal dilution of precision
            vdop: Vertical dilution of precision

        Returns:
            None

        """
        self.select_mode: str = select_mode
        self.mode: int = mode
        self.sats_ids = gpgsv_group.sats_ids
        self.pdop: float = pdop
        self.hdop: float = hdop
        self.vdop: float = vdop

    @property
    def sats_ids(self) -> list[str]:
        """Get list of satellite IDs.

        Returns:
            List of satellite ID strings used in position fix

        """
        return self._sats_ids

    @sats_ids.setter
    def sats_ids(self, value: list[str]) -> None:
        """Set satellite IDs by randomly sampling from available satellites.

        Args:
            value: List of available satellite IDs to sample from

        Returns:
            None

        """
        self._sats_ids = random.sample(value, k=random.randint(MIN_SATELLITES_FOR_FIX, MAX_SATELLITES_FOR_FIX))

    @property
    def sats_count(self) -> int:
        """Get count of active satellites.

        Returns:
            Number of satellites used in position fix

        """
        return len(self.sats_ids)

    def __str__(self) -> str:
        """Return formatted GPGSA sentence string.

        Returns:
            Complete GPGSA NMEA sentence with checksum and line terminators

        """
        # IDs of sat used in position fix (GPGSA_MAX_SATELLITE_FIELDS fields)
        # If less than GPGSA_MAX_SATELLITE_FIELDS sats, fill fields with ''
        sats_ids_output = self.sats_ids[:]
        while len(sats_ids_output) < GPGSA_MAX_SATELLITE_FIELDS:
            sats_ids_output.append("")
        nmea_output = (
            f"{self.sentence_id},{self.select_mode},{self.mode},"
            f"{','.join(sats_ids_output)},"
            f"{self.pdop},{self.hdop},{self.vdop}"
        )
        return f"${nmea_output}*{NmeaMsg.check_sum(nmea_output)}\r\n"


class GpgsvGroup:
    """Initializes the relevant number of GPGSV sentences based on satellite count.

    Manages multiple GPGSV sentences when more than MAX_SATELLITES_PER_SENTENCE satellites are visible,
    as each GPGSV sentence can contain information for up to MAX_SATELLITES_PER_SENTENCE satellites.
    """

    sats_in_sentence: int = MAX_SATELLITES_PER_SENTENCE

    def __init__(self, sats_total: int = 15) -> None:
        """Initialize GPGSV group with specified number of satellites.

        Args:
            sats_total: Total number of satellites to simulate (minimum MIN_SATELLITES_FOR_FIX)

        Returns:
            None

        """
        self.gpgsv_instances: list[Gpgsv] = []
        self.sats_total = sats_total
        self.num_of_gsv_in_group: int = ceil(self.sats_total / self.sats_in_sentence)
        # List of satellites ids for all GPGSV sentences
        self.sats_ids: list[str] = random.sample(
            [f"{_:02d}" for _ in range(1, MAX_SATELLITE_ID + 1)], k=self.sats_total
        )
        # Iterator for sentence sats IDs
        sats_ids_iter = iter(self.sats_ids)
        # Initialize GPGSV sentences
        for sentence_num in range(1, self.num_of_gsv_in_group + 1):
            if sentence_num == self.num_of_gsv_in_group and self.sats_total % self.sats_in_sentence != 0:
                self.sats_in_sentence = self.sats_total % self.sats_in_sentence
            sats_ids_sentence: list[str] = [next(sats_ids_iter) for _ in range(self.sats_in_sentence)]
            gpgsv_sentence = Gpgsv(
                sats_total=self.sats_total,
                sats_in_sentence=self.sats_in_sentence,
                num_of_gsv_in_group=self.num_of_gsv_in_group,
                sentence_num=sentence_num,
                sats_ids=sats_ids_sentence,
            )
            self.gpgsv_instances.append(gpgsv_sentence)

    @property
    def sats_total(self) -> int:
        """Get total number of satellites.

        Returns:
            Total number of satellites in the group

        """
        return self._sats_total

    @sats_total.setter
    def sats_total(self, value: int) -> None:
        """Set total number of satellites (minimum 4).

        Args:
            value: Number of satellites (will be set to 4 if less than 4)

        Returns:
            None

        """
        if int(value) < MIN_SATELLITES_FOR_FIX:
            self._sats_total = MIN_SATELLITES_FOR_FIX
        else:
            self._sats_total = value

    def __str__(self) -> str:
        """Return formatted string of all GPGSV sentences.

        Returns:
            Concatenated string of all GPGSV sentences in the group

        """
        gpgsv_group_str = ""
        for gpgsv in self.gpgsv_instances:
            gpgsv_group_str += f"{gpgsv}"
        return gpgsv_group_str


class Gpgsv:
    """GPS Satellites in view with randomly generated satellite data.

    Provides information about satellites in view including satellite ID,
    elevation, azimuth, and signal-to-noise ratio for up to 4 satellites per sentence.

    Example: $GPGSV,3,1,11,03,03,111,00,04,15,270,00,06,01,010,00,13,06,292,00*74
    """

    sentence_id: str = "GPGSV"

    def __init__(
        self,
        num_of_gsv_in_group: int,
        sentence_num: int,
        sats_total: int,
        sats_in_sentence: int,
        sats_ids: list[str],
    ) -> None:
        """Initialize GPGSV sentence with satellite visibility data.

        Args:
            num_of_gsv_in_group: Total number of GPGSV sentences in the group
            sentence_num: Current sentence number in the group
            sats_total: Total number of satellites across all sentences
            sats_in_sentence: Number of satellites in this specific sentence
            sats_ids: List of satellite IDs for this sentence

        Returns:
            None

        """
        self.num_of_gsv_in_group: int = num_of_gsv_in_group
        self.sentence_num: int = sentence_num
        self.sats_total: int = sats_total
        self.sats_in_sentence: int = sats_in_sentence
        self.sats_ids: list[str] = sats_ids
        self.sats_details: str = ""
        for sat in self.sats_ids:
            satellite_id: str = sat
            elevation: int = random.randint(0, MAX_ELEVATION_DEGREES)
            azimuth: int = random.randint(0, MAX_AZIMUTH_DEGREES)
            snr: int = random.randint(0, MAX_SNR_VALUE)
            self.sats_details += f",{satellite_id},{elevation:02d},{azimuth:03d},{snr:02d}"

    def __str__(self) -> str:
        """Return formatted GPGSV sentence string.

        Returns:
            Complete GPGSV NMEA sentence with checksum and line terminators

        """
        nmea_output = (
            f"{self.sentence_id},{self.num_of_gsv_in_group},{self.sentence_num},{self.sats_total}{self.sats_details}"
        )
        return f"${nmea_output}*{NmeaMsg.check_sum(nmea_output)}\r\n"


class Gphdt:
    """Heading, True.

    Actual vessel heading in degrees true produced by any device or system
    producing true heading. Provides compass heading relative to true north.

    Example: $GPHDT,274.07,T*03
    """

    sentence_id: str = "GPHDT"

    def __init__(self, heading: float) -> None:
        """Initialize GPHDT sentence with heading data.

        Args:
            heading: True heading in degrees (0-359)

        Returns:
            None

        """
        self.heading: float = heading

    def __str__(self) -> str:
        """Return formatted GPHDT sentence string.

        Returns:
            Complete GPHDT NMEA sentence with checksum and line terminators

        """
        nmea_output = f"{self.sentence_id},{self.heading},T"
        return f"${nmea_output}*{NmeaMsg.check_sum(nmea_output)}\r\n"


class Gpvtg:
    """Track Made Good and Ground Speed.

    Provides course and speed information including true and magnetic headings
    and speed over ground in both knots and kilometers per hour.

    Example: $GPVTG,360.0,T,348.7,M,000.0,N,000.0,K*43
    """

    sentence_id: str = "GPVTG"

    def __init__(
        self,
        heading_true: float,
        sog_knots: float,
        heading_magnetic: float | str = "",
    ) -> None:
        """Initialize GPVTG sentence with heading and speed data.

        Args:
            heading_true: True heading in degrees
            sog_knots: Speed over ground in knots
            heading_magnetic: Magnetic heading in degrees (empty if not available)

        Returns:
            None

        """
        self.heading_true: float = heading_true
        self.heading_magnetic: float | str = heading_magnetic
        self.sog_knots: float = sog_knots

    @property
    def sog_kmhr(self) -> float:
        """Return speed over ground in kilometers/hour.

        Returns:
            Speed over ground converted from knots to km/h

        """
        return round(self.sog_knots * KNOTS_TO_KMHR_CONVERSION, 1)

    def __str__(self) -> str:
        """Return formatted GPVTG sentence string.

        Returns:
            Complete GPVTG NMEA sentence with checksum and line terminators

        """
        nmea_output = (
            f"{self.sentence_id},{self.heading_true},T,{self.heading_magnetic},M,{self.sog_knots},N,{self.sog_kmhr},K"
        )
        return f"${nmea_output}*{NmeaMsg.check_sum(nmea_output)}\r\n"


class Gpzda:
    """Time and date - UTC and local Time Zone.

    Provides UTC time and date information along with local time zone offset.
    Essential for applications requiring precise timing information.

    Example: $GPZDA,095942.000,13,07,2020,0,0*50
    """

    sentence_id: str = "GPZDA"

    def __init__(self, utc_date_time: datetime.datetime) -> None:
        """Initialize GPZDA sentence with date and time data.

        Args:
            utc_date_time: Current UTC date and time

        Returns:
            None

        """
        # UTC time in format: 211250
        self.utc_time = utc_date_time

    @property
    def utc_time(self) -> str:
        """Get UTC time in HHMMSS format.

        Returns:
            UTC time as string in HHMMSS format

        """
        return self._utc_time

    @utc_time.setter
    def utc_time(self, value: datetime.datetime) -> None:
        """Set UTC time and date from datetime object.

        Args:
            value: Datetime object to extract time and date from

        Returns:
            None

        """
        self._utc_time = value.strftime("%H%M%S")
        self._utc_date = value.strftime("%d,%m,%Y")

    @property
    def utc_date(self) -> str:
        """Get UTC date in DD,MM,YYYY format.

        Returns:
            UTC date as string in DD,MM,YYYY format

        """
        return self._utc_date

    @utc_date.setter
    def utc_date(self, value: datetime.datetime) -> None:
        """Set UTC date from datetime object.

        Args:
            value: Datetime object to extract date from

        Returns:
            None

        """
        self._utc_date = value.strftime("%d,%m,%Y")

    def __str__(self) -> str:
        """Return formatted GPZDA sentence string.

        Returns:
            Complete GPZDA NMEA sentence with checksum and line terminators

        """
        # Local Zone not used
        nmea_output = f"{self.sentence_id},{self.utc_time}.000,{self.utc_date},0,0"
        return f"${nmea_output}*{NmeaMsg.check_sum(nmea_output)}\r\n"
