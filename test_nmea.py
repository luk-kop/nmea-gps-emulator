import unittest
from unittest import mock
from datetime import datetime

from nmea_gps import NmeaMsg, Gprmc, Gpgga, Gpzda, Gphdt, Gpgll, GpgsvGroup


class TestNmeaGps(unittest.TestCase):
    """
    Tests for NMEA sentences.
    """
    def setUp(self):
        self.time = datetime(2021, 3, 9, 12, 9, 44, 855497)
        self.speed = 12.3
        self.course = 123.1
        self.altitude = 15.2
        self.position = {
            'latitude_value': '5425.123',
            'latitude_direction': 'N',
            'longitude_value': '01832.664',
            'longitude_direction': 'E',
        }

    def test_checksum(self):
        test_data = 'GPRMC,095940.000,A,5432.216088,N,01832.664132,E,0.019,0.00,130720,,,A'
        check_sum = NmeaMsg.check_sum(test_data)
        self.assertEqual(check_sum, '59')

    def test_gprmc_str(self):
        expected = '$GPRMC,120944.000,A,5425.123,N,01832.664,E,12.300,123.1,090321,,,A*56\r\n'
        test_obj = Gprmc(utc_date_time=self.time,
                         position=self.position,
                         sog=self.speed,
                         cmg=self.course)
        self.assertEqual(test_obj.__str__(), expected)

    def test_gpgga_str(self):
        expected = '$GPGGA,120944.00,5425.123,N,01832.664,E,1,12,0.92,15.2,M,32.5,M,,*66\r\n'
        test_obj = Gpgga(sats_count=12,
                         utc_date_time=self.time,
                         position=self.position,
                         altitude=self.altitude)
        self.assertEqual(test_obj.__str__(), expected)

    def test_gpzda_str(self):
        expected = '$GPZDA,120944.000,09,03,2021,0,0*57\r\n'
        test_obj = Gpzda(utc_date_time=self.time)
        self.assertEqual(test_obj.__str__(), expected)

    def test_gphdt_str(self):
        expected = '$GPHDT,123.1,T*34\r\n'
        test_obj = Gphdt(heading=self.course)
        self.assertEqual(test_obj.__str__(), expected)

    def test_gpgll_str(self):
        expected = '$GPGLL,5425.123,N,01832.664,E,120944.000,A,A*59\r\n'
        test_obj = Gpgll(utc_date_time=self.time,
                         position=self.position)
        self.assertEqual(test_obj.__str__(), expected)

    @mock.patch('random.randint')
    @mock.patch('random.sample')
    def test_gpgsv_group(self, mock_random_sample, mock_random_randint):
        expected = '$GPGSV,4,1,15,20,80,349,89,30,80,349,89,10,80,349,89,21,80,349,89*7B\r\n' \
                   '$GPGSV,4,2,15,03,80,349,89,02,80,349,89,19,80,349,89,08,80,349,89*7A\r\n' \
                   '$GPGSV,4,3,15,12,80,349,89,26,80,349,89,24,80,349,89,22,80,349,89*7B\r\n' \
                   '$GPGSV,4,4,15,09,80,349,89,01,80,349,89,25,80,349,89*45\r\n'
        mock_random_sample.return_value = ['20', '30', '10', '21', '03', '02', '19', '08', '12', '26', '24', '22', '09', '01', '25']
        mock_random_randint.side_effect = lambda x, y: y - 10
        test_obj = GpgsvGroup()
        self.assertEqual(test_obj.__str__(), expected)


if __name__ == '__main__':
    unittest.main()