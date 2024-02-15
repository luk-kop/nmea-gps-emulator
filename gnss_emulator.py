#!/usr/bin/env python3

import time
import sys
import threading
import uuid
import logging
import pdb

from nmea_gps import NmeaMsg
from utils import position_input, ip_port_input, trans_proto_input, heading_input, speed_input, \
    heading_speed_input, serial_config_input, spi_config_input
from custom_thread import NmeaStreamThread, NmeaSerialThread, run_telnet_server_thread, NmeaSpiThread


class GnssEmulator:
    """
    Display a menu and respond to choices when run.
    """
    def __init__(self, choice: str = "1", speed: str ="10.035", heading: str = "45.0"):
        self.nmea_thread = None
        self.nmea_obj = None
        self._is_alive = False
        self.speed = speed
        self.heading = heading
        self.choices = {
            'serial': self.nmea_serial,
            'spi': self.nmea_spi,
            'tcp': self.nmea_tcp_server,
            'stream': self.nmea_stream,
            'quit': self.quit,
        }
        action = self.choices.get(choice)
        self.run(action)

    def start(self):
        self._is_alive = True

    def close(self):
        self._is_alive = False

    def update_speed(self, speed):
        self.speed = speed

    def update_heading(self, heading):
        self.heading = heading

    def run(self, action):
        while True:
            if action == self.nmea_spi:
                #SPI uses RPi.GPIO which only runs on PI, add an option such that one can choose SPI on PC also.
                print('\n\n*** SPI is WIP. Not possible to use yet***\n')
                sys.exit()
            if action:
                # Dummy 'nav_data_dict'
                #Default speed, heading, altitude
                nav_data_dict = {
                    'gps_speed': 10.035,
                    'gps_heading': 45.0,
                    'gps_altitude_amsl': 15.2,
                    'position': {}
                }

                # Position, initial course and speed queries
                nav_data_dict['position'] = position_input()
                nav_data_dict['gps_heading'] = heading_input()
                nav_data_dict['gps_speed'] = speed_input()

                # Initialize NmeaMsg object
                self.nmea_obj = NmeaMsg(position=nav_data_dict['position'],
                                        altitude=nav_data_dict['gps_altitude_amsl'],
                                        speed=nav_data_dict['gps_speed'],
                                        heading=nav_data_dict['gps_heading'])
                action()
                break
        # Changing the unit's course and speed by the user in the main thread.
        while self._is_alive:
            if not self.nmea_thread.is_alive() or not self._is_alive:
                print('\n\n*** Closing the script... ***\n')
                break
            new_head, new_speed = heading_speed_input(self.heading, self.speed)
            print(new_head)
            print(new_speed)
            # Get all 'nmea_srv*' telnet server threads
            thread_list = [thread for thread in threading.enumerate() if thread.name.startswith('nmea_srv')]
            if thread_list:
                for thr in thread_list:
                    # Update speed and heading
                    # a = time.time()
                    thr.set_heading(new_head)
                    thr.set_speed(new_speed)
                    # print(time.time() - a)
                else:
                    # Set targeted head and speed without connected clients
                    self.nmea_obj.heading_targeted = new_head
                    self.nmea_obj.speed_targeted = new_speed
                print()
            time.sleep(0.05)

    def nmea_serial(self):
        """
        Runs serial which emulates NMEA server-device
        """
        # serial_port = '/dev/ttyUSB0'
        # Serial configuration query
        serial_config = serial_config_input()
        self.nmea_thread = NmeaSerialThread(name=f'nmea_srv{uuid.uuid4().hex}',
                                       daemon=True,
                                       serial_config=serial_config,
                                       nmea_object=self.nmea_obj)
        self.nmea_thread.start()

    def nmea_spi(self):
        """
        Runs SPI which emulate NMEA server-device
        """

        spi_config = spi_config_input()
        self.nmea_thread = NmeaSpiThread(name=f'nmea_srv{uuid.uuid4().hex}',
                                       daemon=True,
                                       spi_config=spi_config,
                                       nmea_object=self.nmea_obj)
        self.nmea_thread.start()



    def nmea_tcp_server(self):
        """
        Runs telnet server witch emulates NMEA device.
        """
        # Local TCP server IP address and port number.
        srv_ip_address, srv_port = ip_port_input('telnet')
        self.nmea_thread = threading.Thread(target=run_telnet_server_thread,
                                            args=[srv_ip_address, srv_port, self.nmea_obj],
                                            daemon=True,
                                            name='nmea_thread')
        self.nmea_thread.start()

    def nmea_stream(self):
        """
        Runs TCP or UDP NMEA stream to designated host.
        """
        # IP address and port number query
        ip_add, port = ip_port_input('stream')
        # Transport protocol query.
        stream_proto = trans_proto_input()
        self.nmea_thread = NmeaStreamThread(name=f'nmea_srv{uuid.uuid4().hex}',
                                            daemon=True,
                                            ip_add=ip_add,
                                            port=port,
                                            proto=stream_proto,
                                            nmea_object=self.nmea_obj)
        self.nmea_thread.start()

    def quit(self):
        """
        Exit script.
        """
        sys.exit(0)


if __name__ == '__main__':
    # Logging config
    log_format = '%(asctime)s: %(message)s'
    logging.basicConfig(format=log_format, level=logging.INFO, datefmt='%H:%M:%S')

    GnssEmulator()


