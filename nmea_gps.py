import random
from math import ceil
import datetime


class NmeaMsg:
    """
    The parent class for all NMEA sentences.
    """
    def check_sum(self, data):
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


class Gpgga(NmeaMsg):
    """
    Global Positioning System Fix Data
    Example: $GPGGA,140041.00,5436.70976,N,01839.98065,E,1,09,0.87,21.7,M,32.5,M,,*60\r\n
    """
    sentence_id: str = 'GPGGA'

    def __init__(self, gpgsa_object, utc_time, position, altitude, antenna_altitude_above_msl, fix_quality=1,
                 hdop=0.92, dgps_last_update='', dgps_ref_station_id=''):
        self.gpgsa_object = gpgsa_object
        # UTC of position time in format: 211250
        self.utc_time = utc_time.strftime('%H%M%S')
        self.latitude_value = position['latitude_value']
        self.latitude_direction = position['latitude_direction']
        self.longitude_value = position['longitude_value']
        self.longitude_direction = position['longitude_direction']
        self.fix_quality = fix_quality
        # self.num_of_satellites = num_of_sats
        self.hdop = hdop
        self.altitude = altitude
        self.antenna_altitude_above_msl = antenna_altitude_above_msl
        self.dgps_last_update = dgps_last_update
        self.dgps_ref_station_id = dgps_ref_station_id
        self.nmea_output = f'{self.sentence_id},{self.utc_time}.00,{self.latitude_value},' \
                           f'{self.latitude_direction},{self.longitude_value},{self.longitude_direction},' \
                           f'{self.fix_quality},{self.num_of_sats:02d},{self.hdop},{self.altitude},M,' \
                           f'{self.antenna_altitude_above_msl},M,{self.dgps_last_update},' \
                           f'{self.dgps_ref_station_id}'

    @property
    def num_of_sats(self):
        return len(self.gpgsa_object.sats_ids)

    def __str__(self) -> str:
        return f'${self.nmea_output}*{self.check_sum(self.nmea_output)}\r\n'


class Gpgll(NmeaMsg):
    """
    Position data: position fix, time of position fix, and status
    Example: $GPGLL,5432.216118,N,01832.663994,E,095942.000,A,A*58
    """
    sentence_id: str = 'GPGLL'

    def __init__(self, utc_time, position, data_status='A', faa_mode='A'):
        # UTC time in format: 211250
        self.utc_time = utc_time.strftime('%H%M%S')
        self.latitude_value = position['latitude_value']
        self.latitude_direction = position['latitude_direction']
        self.longitude_value = position['longitude_value']
        self.longitude_direction = position['longitude_direction']
        self.data_status = data_status
        # FAA Mode option in NMEA 2.3 and later
        self.faa_mode = faa_mode
        self.nmea_output = f'{self.sentence_id},{self.latitude_value},{self.latitude_direction},' \
                           f'{self.longitude_value},{self.longitude_direction},{self.utc_time}.000,' \
                           f'{self.data_status},{self.faa_mode}'

    def __str__(self):
        return f'${self.nmea_output}*{self.check_sum(self.nmea_output)}\r\n'


class Gprmc(NmeaMsg):
    """
    Recommended minimum specific GPS/Transit data
    Example: $GPRMC,095940.000,A,5432.216088,N,01832.664132,E,0.019,0.00,130720,,,A*59
    """
    sentence_id = 'GPRMC'

    def __init__(self, utc_time, position, sog, cmg, data_status='A', faa_mode='A', magnetic_var_value='',
                 magnetic_var_direct=''):
        # UTC time in format: 211250
        self.utc_time = utc_time.strftime('%H%M%S')
        self.data_status = data_status
        self.latitude_value = position['latitude_value']
        self.latitude_direction = position['latitude_direction']
        self.longitude_value = position['longitude_value']
        self.longitude_direction = position['longitude_direction']
        # Speed Over Ground
        self.sog = sog
        # Course Made Good
        self.cmg = cmg
        # UTC date in format: 130720
        self.utc_date = utc_time.strftime('%d%m%y')
        self.magnetic_var_value = magnetic_var_value
        self.magnetic_var_direct = magnetic_var_direct
        # FAA Mode option in NMEA 2.3 and later
        self.faa_mode = faa_mode
        self.nmea_output = f'{self.sentence_id},{self.utc_time}.000,{self.data_status},' \
                           f'{self.latitude_value},{self.latitude_direction},{self.longitude_value},' \
                           f'{self.longitude_direction},{self.sog},{self.cmg},{self.utc_date},' \
                           f'{self.magnetic_var_value},{self.magnetic_var_direct},{self.faa_mode}'

    def __str__(self):
        return f'${self.nmea_output}*{self.check_sum(self.nmea_output)}\r\n'


class Gpgsa(NmeaMsg):
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
        # IDs of satt used in position fix (12 fields), if less than 12 sats, fill fields with ''
        sats_ids_output = self.sats_ids[:]
        while len(sats_ids_output) < 12:
            sats_ids_output.append('')
        self.nmea_output = f'{self.sentence_id},{self.select_mode},{self.mode},' \
                           f'{",".join(sats_ids_output)},' \
                           f'{self.pdop},{self.hdop},{self.vdop}'

    @property
    def sats_ids(self):
        return self.__sats_ids

    @sats_ids.setter
    def sats_ids(self, sats_ids):
        self.__sats_ids = random.sample(sats_ids, k=random.randint(4, 12))

    def __str__(self):
        return f'${self.nmea_output}*{self.check_sum(self.nmea_output)}\r\n'


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
    def sats_total(self):
        return self.__sats_total

    @sats_total.setter
    def sats_total(self, sats_total):
        if int(sats_total) < 4:
            self.__sats_total = 4
        else:
            self.__sats_total = sats_total

    def __str__(self):
        gpgsv_group_str = ''
        for gpgsv in self.gpgsv_instances:
            gpgsv_group_str += f'{gpgsv}'
        return gpgsv_group_str

class Gpgsv(NmeaMsg):
    """
    GPS Satellites in view. During instance initialization will generate dummy (random) object's data.
    Example: $GPGSV,3,1,11,03,03,111,00,04,15,270,00,06,01,010,00,13,06,292,00*74
    """
    sentence_id: str = 'GPGSV'
    instances: list = []                # to delete

    def __init__(self, num_of_gsv_in_group, sentence_num, sats_total, sats_in_sentence, sats_ids):
        self.num_of_gsv_in_group = num_of_gsv_in_group
        self.sentence_num = sentence_num
        self.sats_total = sats_total
        self.sats_in_sentence = sats_in_sentence
        self.sats_ids = sats_ids
        self.nmea_output = f'{self.sentence_id},{self.num_of_gsv_in_group},{self.sentence_num},' \
                           f'{self.sats_total}'
        for satt in sats_ids:
            sattelite_id: str = satt
            elevation: str = f"{random.randint(0, 90):02d}"
            azimuth: str = f"{random.randint(0, 359):03d}"
            snr: str = f"{random.randint(0, 99):02d}"
            self.nmea_output += f',{sattelite_id},{elevation},{azimuth},{snr}'
        self.__class__.instances.append(self)

    @classmethod
    def get_instances(cls) -> list:
        return cls.instances

    def __str__(self) -> str:
        return f'${self.nmea_output}*{self.check_sum(self.nmea_output)}\r\n'


class Gphdt(NmeaMsg):
    """
    Heading, True.
    Actual vessel heading in degrees true produced by any device or system producing true heading.
    Example: $GPHDT,274.07,T*03
    """
    sentence_id = 'GPHDT'

    def __init__(self, heading):
        self.heading = heading
        self.nmea_output = f'{self.sentence_id},{self.heading},T'

    def __str__(self):
        return f'${self.nmea_output}*{self.check_sum(self.nmea_output)}\r\n'


class Gpzda(NmeaMsg):
    """
    Time and date - UTC and local Time Zone
    Example: $GPZDA,095942.000,13,07,2020,0,0*50
    """
    sentence_id = 'GPZDA'

    def __init__(self, utc_time):
        # UTC time in format: 211250
        self.utc_time = utc_time.strftime('%H%M%S')
        # UTC date in format: 13,07,2020 (for GPZDA)
        self.utc_date = utc_time.strftime('%d,%m,%Y')
        # Local Zone not used
        self.nmea_output = f'{self.sentence_id},{self.utc_time}.000,{self.utc_date},0,0'

    def __str__(self):
        return f'${self.nmea_output}*{self.check_sum(self.nmea_output)}\r\n'


if __name__ == "__main__":
    # only for tests
    utc_time = datetime.datetime.utcnow()
    # GPGLL
    position: dict = {
        'latitude_value': '5432.216118',
        'latitude_direction': 'N',
        'longitude_value': '01832.663994',
        'longitude_direction': 'E',
    }
    gpgll_sentence = Gpgll(utc_time, position)
    print(gpgll_sentence)

    # GPGSVs
    gpgsv_group = GpgsvGroup(16)
    for gpgsv in gpgsv_group.gpgsv_instances:
        print(gpgsv)

    print(gpgsv_group)

    # GPGSA
    gpgsa_sentence = Gpgsa(gpgsv_group)
    print(gpgsa_sentence)

    # GPGGA
    position: dict = {
        'latitude_value': '5436.70976',
        'latitude_direction': 'N',
        'longitude_value': '01839.98065',
        'longitude_direction': 'E',
    }
    gpgga_sentence = Gpgga(gpgsa_object=gpgsa_sentence,
                           utc_time=utc_time,
                           position=position,
                           altitude=21.7,
                           antenna_altitude_above_msl=32.5)
    print(gpgga_sentence)

    # GPRMC
    gprmc_sentence = Gprmc(utc_time=utc_time,
                           data_status='A',
                           position=position,
                           sog='0.019',
                           cmg='0.00',
                           faa_mode='A')
    print(gprmc_sentence)

    gphdt_sentence = Gphdt('274.07')
    print(gphdt_sentence)

    # GPZDA
    # in format '01,07,2020
    utc_date = datetime.datetime.utcnow().strftime('%d,%m,%Y')
    gpzda_sentence = Gpzda(utc_time=utc_time)
    print(gpzda_sentence)

    nmea_data_list = [
        f'{gpzda_sentence}',
    ]

    print(nmea_data_list)