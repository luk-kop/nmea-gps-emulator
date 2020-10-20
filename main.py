#!/usr/bin/env python3

import time
import socket
import sys
import threading
import platform
import uuid
import os

import serial.tools.list_ports
from apscheduler.schedulers.background import BackgroundScheduler
import psutil

from nmea_gps import NmeaMsg
from input_funcs import position_input, ip_port_input, trans_proto_input, course_input, speed_input, \
    emulator_option_input, course_speed_input


def run_telnet_job(conn, ip_add, job_id: str) -> None:
    """
    Function creates separate job for each connected client.
    """
    nmea_list = [f'{_}' for _ in next(nmea_obj)]
    try:
        for nmea in nmea_list:
            conn.sendall(nmea.encode())
            time.sleep(0.05)
    except (BrokenPipeError, OSError):
        conn.close()
        print(f'\n*** Connection closed with {ip_add[0]}:{ip_add[1]} ***')
        scheduler.remove_job(job_id=job_id)


def run_telnet_server_thread(srv_ip_address: str, srv_port: str) -> None:
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
            max_sched_jobs = 1
            # Scripts waiting for client calls
            # The server is blocked (suspended) and is waiting for a client connection.
            conn, ip_add = s.accept()
            print(f'\n*** Connected with {ip_add[0]}:{ip_add[1]} ***')
            if len(scheduler.get_jobs()) < max_sched_jobs:
                job_id = uuid.uuid4().hex
                scheduler.add_job(func=run_telnet_job,
                                  kwargs={'conn': conn, 'ip_add': ip_add, 'job_id': job_id},
                                  trigger='interval',
                                  seconds=1,
                                  id=job_id)
                if not scheduler.running:
                    scheduler.start()
            else:
                # Close connection if number of scheduler jobs > max_sched_jobs
                conn.close()
                print(f'\n*** Connection closed with {ip_add[0]}:{ip_add[1]} ***')


def run_stream_thread(srv_ip_address: str, srv_port: str, stream_proto: str) -> None:
    """
    Function runs thread with NMEA stream - TCP or UDP.
    """
    if stream_proto == 'tcp':
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((srv_ip_address, srv_port))
                print(f'\n*** Sending NMEA data - TCP stream to {srv_ip_address}:{srv_port}... ***\n')
                while True:
                    timer_start = time.perf_counter()
                    nmea_list = [f'{_}' for _ in next(nmea_obj)]
                    for nmea in nmea_list:
                        s.send(nmea.encode())
                        time.sleep(0.05)
                    # Start next loop after 1 sec
                    time.sleep(1 - (time.perf_counter() - timer_start))
        except (OSError, TimeoutError, ConnectionRefusedError, BrokenPipeError) as err:
            print(f'\n*** Error: {err.strerror} ***\n')
            exit_script()
            # sys.exit()
    elif stream_proto == 'udp':
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            print(f'\n*** Sending NMEA data - UDP stream to {srv_ip_address}:{srv_port}... ***\n')
            while True:
                timer_start = time.perf_counter()
                nmea_list = [f'{_}' for _ in next(nmea_obj)]
                for nmea in nmea_list:
                    try:
                        s.sendto(nmea.encode(), (srv_ip_address, srv_port))
                        time.sleep(0.05)
                    except OSError as err:
                        print(f'*** Error: {err.strerror} ***')
                        exit_script()
                        # sys.exit()
                # Start next loop after 1 sec
                time.sleep(1 - (time.perf_counter() - timer_start))


def exit_script():
    """
    The function enables to terminate the script (main thread) from the inside of child thread.
    """
    current_script_pid = os.getpid()
    current_script = psutil.Process(current_script_pid)
    print('*** Closing the script... ***\n')
    time.sleep(1)
    current_script.terminate()

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
    # Create APScheduler object
    scheduler = BackgroundScheduler()

    # Dummy 'nav_data_dict'
    nav_data_dict = {'gps_speed': 100.035,
                     'gps_heading': 45.0,
                     'gps_altitude_amsl': 15.2,
                     'position': {}}

    # Emulator option query
    emulator_option = emulator_option_input()

    if emulator_option == '1':
        # Runs serial which emulates NMEA server-device
        # serial_port = '/dev/ttyUSB0'

        # Dict with all serial port settings.
        serial_set = {'bytesize': 8,
                      'parity': 'N',
                      'stopbits': 1,
                      'timeout': 1}

        # Lista of available serial ports.
        ports_connected = serial.tools.list_ports.comports(include_links=False)
        # List of available serial port's names.
        ports_connected_names = [port.device for port in ports_connected]
        print('\n### Connected Serial Ports: ###')
        for port in sorted(ports_connected):
            print(f'   - {port}')
        # Check OS platform.
        platform_os = platform.system()
        # Asks for serial port name and checks the name validity.
        while True:
            if platform_os.lower() == 'linux':
                print('\n### Choose Serial Port [/dev/ttyUSB0]: ###')
                serial_set['port'] = input('>>> ')
                if serial_set['port'] == '':
                    serial_set['port'] = '/dev/ttyUSB0'
                if serial_set['port'] in ports_connected_names:
                    break
            elif platform_os.lower() == 'windows':
                print('\n### Choose Serial Port [COM1]: ###')
                serial_set['port'] = input('>>> ')
                if serial_set['port'] == '':
                    serial_set['port'] = 'COM1'
                if serial_set['port'] in ports_connected_names:
                    break
            print(f'\nError: \'{serial_set["port"]}\' is wrong port\'s name.')

        # Serial port settings:
        baudrate_list = ['300', '600', '1200', '2400', '4800', '9600', '14400',
                         '19200', '38400', '57600', '115200', '128000']
        while True:
            print('\n### Enter serial baudrate [9600]: ###')
            serial_set['baudrate'] = input('>>> ')
            if serial_set['baudrate'] == '':
                serial_set['baudrate'] = 9600
            if str(serial_set['baudrate']) in baudrate_list:
                break
            print(f'\n*** Error: \'{serial_set["baudrate"]}\' is wrong port\'s baudrate. ***')

        # Ask for position:
        nav_data_dict['position'] = position_input()

        # Open serial port.
        # TODO: add try-except when serial port is busy
        with serial.Serial(serial_set['port'], baudrate=serial_set['baudrate'],
                           bytesize=serial_set['bytesize'],
                           parity=serial_set['parity'],
                           stopbits=serial_set['stopbits'],
                           timeout=serial_set['timeout']) as ser:
            print(
                f'Serial port settings: {serial_set["port"]} {serial_set["baudrate"]} {serial_set["bytesize"]}{serial_set["parity"]}{serial_set["stopbits"]}')
            print('Sending NMEA data...')
            # Initialize NmeaMsg object
            nmea_obj = NmeaMsg(position=nav_data_dict['position'],
                               altitude=nav_data_dict['gps_altitude_amsl'],
                               speed=nav_data_dict['gps_speed'],
                               heading=nav_data_dict['gps_heading'])
            while True:
                nmea_list = [f'{_}' for _ in next(nmea_obj)]
                for nmea in nmea_list:
                    ser.write(str.encode(nmea))
                    time.sleep(0.1)
                time.sleep(0.5)
        # nmea_thread

    elif emulator_option == '2':
        # Runs telnet server witch emulates NMEA device.
        # Position, initial course and speed queries
        nav_data_dict['position'] = position_input()
        nav_data_dict['gps_heading'] = course_input()
        nav_data_dict['gps_speed'] = speed_input()
        # Initialize NmeaMsg object
        nmea_obj = NmeaMsg(position=nav_data_dict['position'],
                           altitude=nav_data_dict['gps_altitude_amsl'],
                           speed=nav_data_dict['gps_speed'],
                           heading=nav_data_dict['gps_heading'])
        # Local TCP server IP address and port number.
        srv_ip_address, srv_port = ip_port_input('telnet')
        nmea_thread = threading.Thread(target=run_telnet_server_thread,
                                       args=[srv_ip_address, srv_port],
                                       daemon=True,
                                       name='nmea_thread')
        nmea_thread.start()
    elif emulator_option == '3':
        # Runs TCP or UDP NMEA stream to designated host.
        # Position, initial course and speed queries
        nav_data_dict['position'] = position_input()
        nav_data_dict['gps_heading'] = course_input()
        nav_data_dict['gps_speed'] = speed_input()
        # Initialize NmeaMsg object
        nmea_obj = NmeaMsg(position=nav_data_dict['position'],
                           altitude=nav_data_dict['gps_altitude_amsl'],
                           speed=nav_data_dict['gps_speed'],
                           heading=nav_data_dict['gps_heading'])
        # IP address and port number query
        srv_ip_address, srv_port = ip_port_input('stream')
        # Transport  query
        stream_proto = trans_proto_input()
        # run_stream_thread(srv_ip_address, srv_port, nav_data_dict, stream_proto)
        nmea_thread = threading.Thread(target=run_stream_thread,
                                       args=[srv_ip_address, srv_port, stream_proto],
                                       daemon=True,
                                       name='nmea_thread')
        nmea_thread.start()

    first_run = True
    # Possibility of changing the unit's course and speed by the user in the main thread.
    while True:
        if not nmea_thread.is_alive():
            print('\n*** Closing the script... ***\n')
            sys.exit()
        try:
            if first_run:
                time.sleep(4)
                first_run = False
            prompt = input('Press "Enter" to change course/speed or "Ctrl + c" to exit ...\n')
            if prompt == '':
                nmea_obj.heading_targeted, nmea_obj.speed_targeted = course_speed_input()
                print()
        except KeyboardInterrupt:
            print('\n*** Closing the script... ***\n')
            sys.exit()

