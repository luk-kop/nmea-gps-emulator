#!/usr/bin/env python3

import time
import socket
import sys
import threading
import uuid
import logging


from nmea_gps import NmeaMsg
from auxiliary_funcs import position_input, ip_port_input, trans_proto_input, heading_input, speed_input, \
    emulator_option_input, heading_speed_input, exit_script, serial_config_input
from custom_thread import NmeaSrvThread, NmeaStreamThread, NmeaSerialThread


def run_telnet_server_thread(srv_ip_address: str, srv_port: str, nmea_obj) -> None:
    """
    Function starts thread with TCP (telnet) server sending NMEA data to connected client (clients).
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Bind socket to local host and port.
        try:
            s.bind((srv_ip_address, srv_port))
        except socket.error as err:
            print(f'\n*** Bind failed. Error: {err.strerror}. ***')
            print('Change IP/port settings or try again in next 2 minutes.')
            exit_script()
            # sys.exit()
        # Start listening on socket
        s.listen(10)
        print(f'\n*** Server listening on {srv_ip_address}:{srv_port}... ***\n')
        while True:
            # Number of allowed connections to TCP server.
            max_threads = 5
            # Scripts waiting for client calls
            # The server is blocked (suspended) and is waiting for a client connection.
            conn, ip_add = s.accept()
            # print(f'\n*** Connected with {ip_add[0]}:{ip_add[1]} ***')
            logging.info(f'Connected with {ip_add[0]}:{ip_add[1]}')
            thread_list = [thread.name for thread in threading.enumerate()]
            if len([thread_name for thread_name in thread_list if thread_name.startswith('nmea_srv')]) < max_threads:
                nmea_srv_thread = NmeaSrvThread(name=f'nmea_srv{uuid.uuid4().hex}',
                                                daemon=True,
                                                conn=conn,
                                                ip_add=ip_add,
                                                nmea_object=nmea_obj)
                nmea_srv_thread.start()
            else:
                # Close connection if number of scheduler jobs > max_sched_jobs
                conn.close()
                # print(f'\n*** Connection closed with {ip_add[0]}:{ip_add[1]} ***')
                logging.info(f'Connection closed with {ip_add[0]}:{ip_add[1]}')


# TODO:     Add try-except when serial port is busy
if __name__ == '__main__':
    print(r'''

.##..##..##...##..######...####...........######..##...##..##..##..##.......####...######...####...#####..
.###.##..###.###..##......##..##..........##......###.###..##..##..##......##..##....##....##..##..##..##.
.##.###..##.#.##..####....######..........####....##.#.##..##..##..##......######....##....##..##..#####..
.##..##..##...##..##......##..##..........##......##...##..##..##..##......##..##....##....##..##..##..##.
.##..##..##...##..######..##..##..........######..##...##...####...######..##..##....##.....####...##..##.
..........................................................................................................
''')
    # Dummy 'nav_data_dict'
    nav_data_dict = {'gps_speed': 10.035,
                     'gps_heading': 45.0,
                     'gps_altitude_amsl': 15.2,
                     'position': {}
                     }

    # Emulator option query
    emulator_option = emulator_option_input()
    # Position, initial course and speed queries
    nav_data_dict['position'] = position_input()
    nav_data_dict['gps_heading'] = heading_input()
    nav_data_dict['gps_speed'] = speed_input()

    # Initialize NmeaMsg object
    nmea_obj = NmeaMsg(position=nav_data_dict['position'],
                       altitude=nav_data_dict['gps_altitude_amsl'],
                       speed=nav_data_dict['gps_speed'],
                       heading=nav_data_dict['gps_heading'])

    # Logging config
    log_format = '%(asctime)s: %(message)s'
    logging.basicConfig(format=log_format, level=logging.INFO, datefmt='%H:%M:%S')

    if emulator_option == '1':
        # Runs serial which emulates NMEA server-device
        # serial_port = '/dev/ttyUSB0'
        # Serial configuration query
        serial_config = serial_config_input()
        nmea_thread = NmeaSerialThread(name=f'nmea_srv{uuid.uuid4().hex}',
                                       daemon=True,
                                       serial_config=serial_config,
                                       nmea_object=nmea_obj)
        nmea_thread.start()

    elif emulator_option == '2':
        # Runs telnet server witch emulates NMEA device.
        # Local TCP server IP address and port number.
        srv_ip_address, srv_port = ip_port_input('telnet')
        nmea_thread = threading.Thread(target=run_telnet_server_thread,
                                       args=[srv_ip_address, srv_port, nmea_obj],
                                       daemon=True,
                                       name='nmea_thread')
        nmea_thread.start()
    elif emulator_option == '3':
        # Runs TCP or UDP NMEA stream to designated host.
        # IP address and port number query
        ip_add, port = ip_port_input('stream')
        # Transport protocol query.
        stream_proto = trans_proto_input()
        nmea_thread = NmeaStreamThread(name=f'nmea_srv{uuid.uuid4().hex}',
                                       daemon=True,
                                       ip_add=ip_add,
                                       port=port,
                                       proto=stream_proto,
                                       nmea_object=nmea_obj)
        nmea_thread.start()

    # Changing the unit's course and speed by the user in the main thread.
    first_run = True
    while True:
        if not nmea_thread.is_alive():
            print('\n*** Closing the script... ***\n')
            sys.exit()
        try:
            if first_run:
                time.sleep(2)
                first_run = False
            prompt = input('Press "Enter" to change course/speed or "Ctrl + c" to exit ...\n')
            if prompt == '':
                new_head, new_speed = heading_speed_input()
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
                    nmea_obj.heading_targeted = new_head
                    nmea_obj.speed_targeted = new_speed
                print()
        except KeyboardInterrupt:
            print('\n*** Closing the script... ***\n')
            sys.exit()

