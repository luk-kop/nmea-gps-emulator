import random
from math import ceil
import datetime
import time

from pyproj import Geod


# static method in NmeaMsg
def check_sum(data):
    """
    Function changes ASCII char to decimal representation, perform XOR operation of
    all the bytes between the $ and the * (not including the delimiters themselves),
    and returns NMEA check-sum in hexadecimal notation.
    """
    check_sum: int = 0
    for char in data:
        num = bytearray(char, encoding='utf-8')[0]
        # XOR operation.
        check_sum = (check_sum ^ num)
    # Returns only hex digits string without leading 0x.
    hex_str: str = str(hex(check_sum))[2:]
    if len(hex_str) == 2:
        return hex_str.upper()
    return f'0{hex_str}'.upper()


class NmeaMsg:
    """
    The class represent a group of NMEA sentences.
    """
    def __init__(self, position, altitude, speed, heading):
        # Instance attributes
        self.utc_date_time = datetime.datetime.utcnow()
        self.position = position
        self.speed = speed
        self.heading = heading
        # NMEA sentences initialization
        self.gpgsv_group = GpgsvGroup(sats_total=15)
        self.gpgsa = Gpgsa(gpgsv_group=self.gpgsv_group)
        self.gga = Gpgga(gpgsa_object=self.gpgsa,
                         utc_date_time=self.utc_date_time,
                         position=position,
                         altitude=altitude,
                         antenna_altitude_above_msl=32.5)
        self.gpgll = Gpgll(utc_date_time=self.utc_date_time,
                           position=position)
        self.gprmc = Gprmc(utc_date_time=self.utc_date_time,
                           position=position,
                           sog=speed,
                           cmg=heading)
        self.gphdt = Gphdt(heading=heading)
        self.gpzda = Gpzda(utc_date_time=self.utc_date_time)
        self.nmea_sentences = [self.gga,
                               self.gpgsa,
                               *[gpgsv for gpgsv in self.gpgsv_group.gpgsv_instances],
                               self.gpgll,
                               self.gprmc,
                               self.gphdt,
                               self.gpzda,]

    def __next__(self):
        # self.utc_date_time_prev = self.utc_date_time
        utc_date_time_prev = self.utc_date_time
        self.utc_date_time = datetime.datetime.utcnow()
        if float(self.speed) > 0:
            self.position_update(utc_date_time_prev)
        self.gga.utc_time = self.utc_date_time
        self.gpgll.utc_time = self.utc_date_time
        self.gprmc.utc_time = self.utc_date_time
        self.gprmc.utc_time = self.utc_date_time
        self.gprmc.sog = self.speed
        self.gprmc.cmg = self.heading
        self.gphdt.heading = self.heading
        self.gpzda.utc_time = self.utc_date_time
        # raise StopIteration
        return self.nmea_sentences

    def __iter__(self):
        return self

    def __str__(self):
        nmea_msgs_str = ''
        for nmea in self.nmea_sentences:
            nmea_msgs_str += f'{nmea}'
        return nmea_msgs_str

    def position_update(self, utc_date_time_prev: datetime):
        """
        Update position when unit in move.
        """
        # The time that has elapsed since the last fix
        time_delta = (self.utc_date_time - utc_date_time_prev).total_seconds()
        # Knots to m/s conversion.
        speed_ms = float(self.speed) * 0.514444
        # Distance in meters.
        distance = speed_ms * time_delta
        # Assignment of coords.
        lat_a = self.position['latitude_value']
        lat_direction = self.position['latitude_direction']
        lon_a = self.position['longitude_value']
        lon_direction = self.position['longitude_direction']
        # Convert current position (start position) format to compatible with 'Geod.fwd' func.
        if lat_direction.lower() == 'n':
            lat_start = float(lat_a[:2]) + (float(lat_a[2:]) / 60)
        else:
            lat_start = - float(lat_a[:2]) - (float(lat_a[2:]) / 60)
        if lon_direction.lower() == 'e':
            lon_start = float(lon_a[:3]) + (float(lon_a[3:]) / 60)
        else:
            lon_start = - float(lon_a[:3]) - (float(lon_a[3:]) / 60)
        # Use WGS84 ellipsoid.
        g = Geod(ellps='WGS84')
        # forward transformation - returns longitude, latitude, back azimuth of terminus points
        lon_end, lat_end, back_azimuth = g.fwd(lon_start, lat_start, float(self.heading), distance)
        # Change direction when cross the equator or prime meridian (Greenwich)
        if lat_end >= 0:
            lat_direction = 'N'
        else:
            lat_direction = 'S'
        if lon_end >= 0:
            lon_direction = 'E'
        else:
            lon_direction = 'W'
        lon_end, lat_end = abs(lon_end), abs(lat_end)
        # New GPS position after calculation.
        lat_degrees = int(lat_end)
        try:
            lat_minutes = round(lat_end % int(lat_end) * 60, 3)
        except ZeroDivisionError:
            lat_minutes = round(lat_end * 60, 3)
        if lat_minutes == 60:
            lat_degrees += 1
            lat_minutes = 0
        lon_degrees = int(lon_end)
        try:
            lon_minutes = round(lon_end % int(lon_end) * 60, 3)
        except ZeroDivisionError:
            lon_minutes = round(lon_end * 60, 3)
        if lon_minutes == 60:
            lon_degrees += 1
            lon_minutes = 0
        self.position['latitude_value'] = f'{lat_degrees:02}{lat_minutes:06.3f}'
        self.position['latitude_direction'] = f'{lat_direction.upper()}'
        self.position['longitude_value'] = f'{lon_degrees:03}{lon_minutes:06.3f}'
        self.position['longitude_direction'] = f'{lon_direction.upper()}'


class Gpgga:
    """
    Global Positioning System Fix Data
    Example: $GPGGA,140041.00,5436.70976,N,01839.98065,E,1,09,0.87,21.7,M,32.5,M,,*60\r\n
    """
    sentence_id: str = 'GPGGA'

    def __init__(self, gpgsa_object, utc_date_time, position, altitude, antenna_altitude_above_msl, fix_quality=1,
                 hdop=0.92, dgps_last_update='', dgps_ref_station_id=''):
        self.gpgsa_object = gpgsa_object
        self.utc_time = utc_date_time
        self.position = position
        self.fix_quality = fix_quality
        # self.num_of_satellites = num_of_sats
        self.hdop = hdop
        self.altitude = altitude
        self.antenna_altitude_above_msl = antenna_altitude_above_msl
        self.dgps_last_update = dgps_last_update
        self.dgps_ref_station_id = dgps_ref_station_id

    @property
    def num_of_sats(self) -> int:
        return len(self.gpgsa_object.sats_ids)

    @property
    def utc_time(self) -> str:
        return self._utc_time

    @utc_time.setter
    def utc_time(self, value) -> None:
        self._utc_time = value.strftime('%H%M%S')

    def __str__(self) -> str:
        nmea_output = f'{self.sentence_id},{self.utc_time}.00,{self.position["latitude_value"]},' \
                      f'{self.position["latitude_direction"]},{self.position["longitude_value"]},' \
                      f'{self.position["longitude_direction"]},{self.fix_quality},' \
                      f'{self.num_of_sats:02d},{self.hdop},{self.altitude},M,' \
                      f'{self.antenna_altitude_above_msl},M,{self.dgps_last_update},' \
                      f'{self.dgps_ref_station_id}'
        return f'${nmea_output}*{check_sum(nmea_output)}\r\n'


class Gpgll:
    """
    Position data: position fix, time of position fix, and status
    Example: $GPGLL,5432.216118,N,01832.663994,E,095942.000,A,A*58
    """
    sentence_id: str = 'GPGLL'

    def __init__(self, utc_date_time, position, data_status='A', faa_mode='A'):
        # UTC time in format: 211250
        self.utc_time = utc_date_time
        self.position = position
        self.data_status = data_status
        # FAA Mode option in NMEA 2.3 and later
        self.faa_mode = faa_mode

    @property
    def utc_time(self) -> str:
        return self._utc_time

    @utc_time.setter
    def utc_time(self, value) -> None:
        self._utc_time = value.strftime('%H%M%S')

    def __str__(self):
        nmea_output = f'{self.sentence_id},{self.position["latitude_value"]},' \
                      f'{self.position["latitude_direction"]},{self.position["longitude_value"]},' \
                      f'{self.position["longitude_direction"]},{self.utc_time}.000,' \
                      f'{self.data_status},{self.faa_mode}'
        return f'${nmea_output}*{check_sum(nmea_output)}\r\n'


class Gprmc:
    """
    Recommended minimum specific GPS/Transit data
    Example: $GPRMC,095940.000,A,5432.216088,N,01832.664132,E,0.019,0.00,130720,,,A*59
    """
    sentence_id = 'GPRMC'

    def __init__(self, utc_date_time, position, sog, cmg, data_status='A', faa_mode='A', magnetic_var_value='',
                 magnetic_var_direct=''):
        # UTC time in format: 211250
        self.utc_time = utc_date_time
        # UTC date in format: 130720
        # self.utc_date = utc_date_time
        self.data_status = data_status
        self.position = position
        # Speed Over Ground
        self.sog = sog
        # Course Made Good
        self.cmg = cmg
        self.magnetic_var_value = magnetic_var_value
        self.magnetic_var_direct = magnetic_var_direct
        # FAA Mode option in NMEA 2.3 and later
        self.faa_mode = faa_mode

    @property
    def utc_time(self) -> str:
        return self._utc_time

    @utc_time.setter
    def utc_time(self, value) -> None:
        self._utc_time = value.strftime('%H%M%S')
        self._utc_date = value.strftime('%d%m%y')

    @property
    def utc_date(self) -> str:
        return self._utc_date

    @utc_date.setter
    def utc_date(self, value) -> None:
        self._utc_date = value.strftime('%d%m%y')

    def __str__(self):
        nmea_output = f'{self.sentence_id},{self.utc_time}.000,{self.data_status},' \
                      f'{self.position["latitude_value"]},{self.position["latitude_direction"]},' \
                      f'{self.position["longitude_value"]},{self.position["longitude_direction"]},' \
                      f'{self.sog},{self.cmg},{self.utc_date},' \
                      f'{self.magnetic_var_value},{self.magnetic_var_direct},{self.faa_mode}'
        return f'${nmea_output}*{check_sum(nmea_output)}\r\n'


class Gpgsa:
    """
    GPS DOP and active satellites
    Example: $GPGSA,A,3,19,28,14,18,27,22,31,39,,,,,1.7,1.0,1.3*35
    """
    sentence_id: str = 'GPGSA'
    def __init__(self, gpgsv_group, select_mode='A', mode=3, pdop=1.56, hdop=0.92, vdop=1.25):
        self.select_mode = select_mode
        self.mode = mode
        self.sats_ids = gpgsv_group.sats_ids
        self.pdop = pdop
        self.hdop = hdop
        self.vdop = vdop

    @property
    def sats_ids(self) -> list:
        return self._sats_ids

    @sats_ids.setter
    def sats_ids(self, value) -> None:
        self._sats_ids = random.sample(value, k=random.randint(4, 12))

    def __str__(self) -> str:
        # IDs of satt used in position fix (12 fields), if less than 12 sats, fill fields with ''
        sats_ids_output = self.sats_ids[:]
        while len(sats_ids_output) < 12:
            sats_ids_output.append('')
        nmea_output = f'{self.sentence_id},{self.select_mode},{self.mode},' \
                      f'{",".join(sats_ids_output)},' \
                      f'{self.pdop},{self.hdop},{self.vdop}'
        return f'${nmea_output}*{check_sum(nmea_output)}\r\n'


class GpgsvGroup:
    """
    The class initializes the relevant number of GPGSV sentences depending on the specified number of satellites.
    """
    sats_in_sentence = 4

    def __init__(self, sats_total):
        self.gpgsv_instances = []
        self.sats_total = sats_total
        self.num_of_gsv_in_group = ceil(self.sats_total / self.sats_in_sentence)
        # List of sattelites ids for all GPGSV sentences
        self.sats_ids = random.sample([f'{_:02d}' for _ in range(1,33)], k=self.sats_total)
        # Iterator for sentence sats IDs
        sats_ids_iter = iter(self.sats_ids)
        # Initialize GPGSV sentences
        for sentence_num in range(1, self.num_of_gsv_in_group + 1):
            if sentence_num == self.num_of_gsv_in_group and self.sats_total % self.sats_in_sentence != 0:
                self.sats_in_sentence = self.sats_total % self.sats_in_sentence
            sats_ids_sentence = [next(sats_ids_iter) for _ in range(self.sats_in_sentence)]
            gpgsv_sentence = Gpgsv(sats_total=self.sats_total,
                                   sats_in_sentence=self.sats_in_sentence,
                                   num_of_gsv_in_group=self.num_of_gsv_in_group,
                                   sentence_num=sentence_num,
                                   sats_ids=sats_ids_sentence)
            self.gpgsv_instances.append(gpgsv_sentence)

    @property
    def sats_total(self) -> int:
        return self._sats_total

    @sats_total.setter
    def sats_total(self, value) -> None:
        if int(value) < 4:
            self._sats_total = 4
        else:
            self._sats_total = value

    def __str__(self) -> str:
        gpgsv_group_str = ''
        for gpgsv in self.gpgsv_instances:
            gpgsv_group_str += f'{gpgsv}'
        return gpgsv_group_str


class Gpgsv:
    """
    GPS Satellites in view. During instance initialization will generate dummy (random) object's data.
    Example: $GPGSV,3,1,11,03,03,111,00,04,15,270,00,06,01,010,00,13,06,292,00*74
    """
    sentence_id: str = 'GPGSV'

    def __init__(self, num_of_gsv_in_group, sentence_num, sats_total, sats_in_sentence, sats_ids):
        self.num_of_gsv_in_group = num_of_gsv_in_group
        self.sentence_num = sentence_num
        self.sats_total = sats_total
        self.sats_in_sentence = sats_in_sentence
        self.sats_ids = sats_ids

    def __str__(self) -> str:
        nmea_output = f'{self.sentence_id},{self.num_of_gsv_in_group},{self.sentence_num},' \
                      f'{self.sats_total}'
        for satt in self.sats_ids:
            sattelite_id: str = satt
            elevation: str = f"{random.randint(0, 90):02d}"
            azimuth: str = f"{random.randint(0, 359):03d}"
            snr: str = f"{random.randint(0, 99):02d}"
            nmea_output += f',{sattelite_id},{elevation},{azimuth},{snr}'
        return f'${nmea_output}*{check_sum(nmea_output)}\r\n'


class Gphdt:
    """
    Heading, True.
    Actual vessel heading in degrees true produced by any device or system producing true heading.
    Example: $GPHDT,274.07,T*03
    """
    sentence_id = 'GPHDT'

    def __init__(self, heading):
        self.heading = heading

    def __str__(self):
        nmea_output = f'{self.sentence_id},{self.heading},T'
        return f'${nmea_output}*{check_sum(nmea_output)}\r\n'


class Gpzda:
    """
    Time and date - UTC and local Time Zone
    Example: $GPZDA,095942.000,13,07,2020,0,0*50
    """
    sentence_id = 'GPZDA'

    def __init__(self, utc_date_time):
        # UTC time in format: 211250
        self.utc_time = utc_date_time
        # UTC date in format: 13,07,2020 (for GPZDA)
        # self.utc_date = utc_date_time

    @property
    def utc_time(self) -> str:
        return self._utc_time

    @utc_time.setter
    def utc_time(self, value) -> None:
        self._utc_time = value.strftime('%H%M%S')
        self._utc_date = value.strftime('%d,%m,%Y')

    @property
    def utc_date(self) -> str:
        return self._utc_date

    @utc_date.setter
    def utc_date(self, value) -> None:
        self._utc_date = value.strftime('%d,%m,%Y')

    def __str__(self):
        # Local Zone not used
        nmea_output = f'{self.sentence_id},{self.utc_time}.000,{self.utc_date},0,0'
        return f'${nmea_output}*{check_sum(nmea_output)}\r\n'


if __name__ == "__main__":
    # only for tests
    utc_time = datetime.datetime.utcnow()
    # GPGLL
    position: dict = {
        'latitude_value': '6059.999',
        'latitude_direction': 'N',
        'longitude_value': '00000.663',
        'longitude_direction': 'W',
    }

    nmea_obj = NmeaMsg(position=position,
                       altitude=21.7,
                       speed='100.00',
                       heading='90.00')
    # print(nmea_obj)
    # print('------------')
    while True:
        a = next(nmea_obj)
        nmea_obj.position_update(datetime.datetime.utcnow())
        for nmea in a:
            print(nmea)
            time.sleep(0.05)
        time.sleep(0.2)

    # gpgll_sentence = Gpgll(utc_time, position)
    # print(gpgll_sentence)
    #
    # # GPGSVs
    # gpgsv_group = GpgsvGroup(16)
    # for gpgsv in gpgsv_group.gpgsv_instances:
    #     print(gpgsv)
    #
    # print(gpgsv_group)
    #
    # # GPGSA
    # gpgsa_sentence = Gpgsa(gpgsv_group)
    # print(gpgsa_sentence)
    #
    # # GPGGA
    # position: dict = {
    #     'latitude_value': '5436.70976',
    #     'latitude_direction': 'N',
    #     'longitude_value': '01839.98065',
    #     'longitude_direction': 'E',
    # }
    # gpgga_sentence = Gpgga(gpgsa_object=gpgsa_sentence,
    #                        utc_date_time=utc_time,
    #                        position=position,
    #                        altitude=21.7,
    #                        antenna_altitude_above_msl=32.5)
    # print(gpgga_sentence)
    #
    # # GPRMC
    # gprmc_sentence = Gprmc(utc_date_time=utc_time,
    #                        data_status='A',
    #                        position=position,
    #                        sog='0.019',
    #                        cmg='0.00',
    #                        faa_mode='A')
    # print(gprmc_sentence)
    #
    # gphdt_sentence = Gphdt('274.07')
    # print(gphdt_sentence)
    #
    # # GPZDA
    # # in format '01,07,2020
    # utc_date = datetime.datetime.utcnow().strftime('%d,%m,%Y')
    # gpzda_sentence = Gpzda(utc_date_time=utc_time)
    # print(gpzda_sentence)
    #
    # nmea_data_list = [
    #     f'{gpzda_sentence}',
    # ]
    #
    # print(nmea_data_list)