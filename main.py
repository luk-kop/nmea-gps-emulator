#!/usr/bin/env python3

import datetime
import time
import socket
import sys
import threading
import re
import platform

import serial
import serial.tools.list_ports
from apscheduler.schedulers.background import BackgroundScheduler

from nmea_gps import NmeaMsg


def position_input() -> dict:
    """
    Function query for position and checks validity of entry data.
    Function returns position.
    """
    while True:
        print('\n### Enter unit position (format - 5430N 01920E): ###')
        position_data = input('>>> ')
        if position_data == '':
            # Default position
            position_dict = {
                'latitude_value': '5430.000',
                'latitude_direction': 'N',
                'longitude_value': '01920.000',
                'longitude_direction': 'E',
            }
            return position_dict
        position_regex = re.compile(r'''^(
            ([0-8]\d[0-5]\d|9000)                               # Latitude
            (N|S)
            \s?
            (([0-1][0-7]\d[0-5]\d)|(0[0-9]\d[0-5]\d)|18000)     # Longitude
            (E|W)
            )$''', re.VERBOSE)
        mo = position_regex.search(position_data.upper().strip())
        if mo:
            # Returns position data
            position_dict = {
                'latitude_value': f'{float(mo.group(2)):08.3f}',
                'latitude_direction': mo.group(3),
                'longitude_value': f'{float(mo.group(4)):09.3f}',
                'longitude_direction': mo.group(7),
            }
            return position_dict
        print('\nError: Wrong entry! Try again.')


def ip_addr_port_num(option: str) -> tuple:
    """
    Function query for IP address and port number for connection.
    """
    while True:
        if option == 'telnet':
            print('\n### Enter Local IP address and port number [0.0.0.0:10110]: ###')
            ip_port_socket = input('>>> ')
            if ip_port_socket == '':
                # All available interfaces and default NMEA port.
                return ('0.0.0.0', 10110)
        elif option == 'stream':
            print('\n### Enter Remote IP address and port number [127.0.0.1:10110]: ###')
            ip_port_socket = input('>>> ')
            if ip_port_socket == '':
                return ('127.0.0.1', 10110)
        # Regex matchs only unicast IP addr from range 0.0.0.0 - 223.255.255.255
        # and port numbers from range 1 - 65535.
        ip_port_regex = re.compile(r'''^(
            ((22[0-3]\.|2[0-1][0-9]\.|1[0-9]{2}\.|[0-9]{1,2}\.)  # 1st octet
            (25[0-5]\.|2[0-4][0-9]\.|1[0-9]{2}\.|[0-9]{1,2}\.){2}  # 2nd and 3th octet
            (25[0-5]|2[0-4][0-9]|1[0-9]{2}|[0-9]{1,2}))            # 4th octet
            :
            ([1-9][0-9]{0,3}|[1-6][0-5]{2}[0-3][0-5])   # port number
            )$''', re.VERBOSE)
        mo = ip_port_regex.search(ip_port_socket)
        if mo:
            # return tuple with IP address (str) and port number (int).
            return (mo.group(2), int(mo.group(6)))
        print(f'\nError: Wrong format use - 192.168.10.10:2020.')


def fix_or_move() -> bool:
    """
    Function query for position type (fixed or in move).
    """
    while True:
        print('\n### Choose type of position: ')
        print('1 - Unit in a fixed position.')
        print('2 - Unit in move.')
        choose = input('>>> ')
        if choose == '1':
            return False
        elif choose == '2':
            return True


def client_thread(conn, addr, nav_dict) -> None:
    """
    Function creates separate thread for each connected client.
    """
    nmea_obj = NmeaMsg(position=nav_dict['position'],
                       altitude=nav_dict['gps_altitude_amsl'],
                       speed=nav_dict['gps_speed'],
                       heading=nav_dict['curr_heading'],
                       in_move=nav_dict['in_move'])
    while True:
        nmea_list = [f'{_}' for _ in next(nmea_obj)]
        try:
            for nmea in nmea_list:
                conn.sendall(nmea.encode())
                time.sleep(0.1)
            time.sleep(0.2)
        except:                                         # more specific except!!!
            break
    # Came out of the loop.
    conn.close()
    print(f'Connection closed with {addr[0]}:{addr[1]}')


##
# MAIN PART #
##
# TODO:     Enter gps_speed and gps_heading by hand when in move.
# TODO:     Add try-except when serial port is busy
# Driver Code
# if __name__ == '__main__':
print(r'''

.##..##..##...##..######...####...........######..##...##..##..##..##.......####...######...####...#####..
.###.##..###.###..##......##..##..........##......###.###..##..##..##......##..##....##....##..##..##..##.
.##.###..##.#.##..####....######..........####....##.#.##..##..##..##......######....##....##..##..#####..
.##..##..##...##..##......##..##..........##......##...##..##..##..##......##..##....##....##..##..##..##.
.##..##..##...##..######..##..##..........######..##...##...####...######..##..##....##.....####...##..##.
..........................................................................................................
''')


# Altitude, Meters, above mean sea level
gps_altitude_amsl = '15.2'
# Speed in Knots
gps_speed = '100.035'
# heading/track made good in degrees
# Initial heading.
gps_heading = '45.0'

scheduler = BackgroundScheduler()

# test nav_data_dictionary
nav_data_dict = {'gps_speed': '100.035',
                 'init_heading': '45.0',
                 'curr_heading': '45.0',
                 'gps_altitude_amsl': '15.2',
                 'position': {},
                 'in_move': False}

while True:
    try:
        print('\n### Choose emulator option: ###')
        print('1 - NMEA Serial')
        print('2 - NMEA Telnet Server')
        print('3 - NMEA TCP or UDP Stream')
        print('### ctrl + c for exit ###')
        emulator_option = input('>>> ')
        if emulator_option in ['1', '2', '3']:
            break
    except KeyboardInterrupt:
        sys.exit()


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
        print(f'\nError: \'{serial_set["baudrate"]}\' is wrong port\'s baudrate.')

    # Ask for position:
    nav_data_dict['position'] = position_input()

    # Choose type of position.
    nav_data_dict['in_move'] = fix_or_move()

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
        nmea_obj = NmeaMsg(position=nav_data_dict['position'],
                           altitude=nav_data_dict['gps_altitude_amsl'],
                           speed=nav_data_dict['gps_speed'],
                           heading=nav_data_dict['curr_heading'],
                           in_move=nav_data_dict['in_move'])
        while True:
            nmea_list = [f'{_}' for _ in next(nmea_obj)]
            for nmea in nmea_list:
                ser.write(str.encode(nmea))
                time.sleep(0.1)
            time.sleep(0.5)

elif emulator_option == '2':
    # Runs telnet server witch emulates NMEA device.

    # Ask for local IP addr and port number.
    srv_ip_address, srv_port = ip_addr_port_num('telnet')

    # Ask for GPS position.
    # position = position_input()
    nav_data_dict['position'] = position_input()
    # Choose type of position.
    nav_data_dict['in_move'] = fix_or_move()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        print('Socket created')
        # Bind socket to local host and port.
        try:
            s.bind((srv_ip_address, srv_port))
        except socket.error as err:
            print(f'\nBind failed. Error: {err.strerror}. Error number: {err.errno}')
            sys.exit()
        print('Socket bind complete')
        # Start listening on socket
        s.listen(10)
        print(f'Socket now listening on {srv_ip_address}:{srv_port}...')

        # Function for handling connections. This will be used to create threads
        # now keep talking with the client.
        while True:
            # wait to accept a connection from clients
            # The server is blocked (suspended) and is waiting for a client conn.
            conn, addr = s.accept()
            print(f'Connected with {addr[0]}:{addr[1]}')
            # start new thread takes 1st argument as a function name to be run, second is the tuple of arguments to the function.
            thread_obj = threading.Thread(target=client_thread,
                                          args=(conn, addr, nav_data_dict))
            thread_obj.start()

elif emulator_option == '3':
    # Runs TCP or UDP NMEA stream to designated host.

    # Query for position:
    nav_data_dict['position'] = position_input()

    # Choose type of position.
    nav_data_dict['in_move'] = fix_or_move()

    # Ask for remote IP addr and port number.
    srv_ip_address, srv_port = ip_addr_port_num('stream')

    print('\n### Enter transport protocol - TCP or UDP: ###')
    stream_proto = input('>>> ')
    if stream_proto.lower().strip() == 'tcp':
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # send TCP
        try:
            s.connect((srv_ip_address, srv_port))
            print(f'\nSending NMEA data - TCP stream to {srv_ip_address}:{srv_port}...')
            nmea_obj = NmeaMsg(position=nav_data_dict['position'],
                               altitude=nav_data_dict['gps_altitude_amsl'],
                               speed=nav_data_dict['gps_speed'],
                               heading=nav_data_dict['curr_heading'],
                               in_move=nav_data_dict['in_move'])
            while True:
                nmea_list = [f'{_}' for _ in next(nmea_obj)]
                for nmea in nmea_list:
                    s.send(nmea.encode())    # or conn.sendall(data.encode('ascii'))
                    time.sleep(0.1)
                    # Send one packet with NMEA sentence in every 1 sek.
                time.sleep(0.2)
            s.close()
        except (OSError, TimeoutError, ConnectionRefusedError) as err:
            print(f'*** Error: {err} ***')
            # print(sys.exc_info()[0])
        except KeyboardInterrupt:
            print('\n*** Exit script! ***')
            sys.exit()
    elif stream_proto.lower().strip() == 'udp':
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f'\nSending NMEA data - UDP stream to {srv_ip_address}:{srv_port}...')

        nmea_obj = NmeaMsg(position=nav_data_dict['position'],
                           altitude=nav_data_dict['gps_altitude_amsl'],
                           speed=nav_data_dict['gps_speed'],
                           heading=nav_data_dict['curr_heading'],
                           in_move=nav_data_dict['in_move'])
        while True:
            nmea_list = [f'{_}' for _ in next(nmea_obj)]
            for nmea in nmea_list:
                try:
                    s.sendto(nmea.encode(), (srv_ip_address, srv_port))
                    # Send one packet with NMEA sentence in every 1 sek.
                    time.sleep(0.1)
                except OSError as err:
                    print(f'*** Error: {err} ***')
                    sys.exit()
                except KeyboardInterrupt:
                    print('\n*** Exit script! ***')
                    sys.exit()
