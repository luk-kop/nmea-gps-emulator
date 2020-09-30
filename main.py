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
from pyproj import Geod


def utc_data() -> str:
    """
    Function returns current time and date for position.
    """
    # UTC time for - 'fix taken at ...'
    time_utc: str = datetime.datetime.utcnow().strftime('%H%M%S')
    date_utc: str = datetime.datetime.utcnow().strftime('%d%m%y')
    return time_utc, date_utc


def nmea_check_sum(data: str) -> str:
    """
    Function changes ASCII char to decimal representation, performs xor operation
    and returns NMEA check-sum i hex notation.
    """
    # Extracts data from string between range $ --- *
    data = data[data.index('$') + 1: data.index('*')]
    check_sum = 0
    for char in data:
        num = bytearray(char, encoding='utf-8')[0]
        # XOR operation.
        check_sum = (check_sum ^ num)
    # Returns only hex digits string without leading 0x.
    hex_str: str = str(hex(check_sum))[2:]
    if len(hex_str) == 2:
        return hex_str.upper()
    return f'0{hex_str}'.upper()


def position_input() -> list:
    """
    Function asks for position and checks validity of entry data.
    Function returns position list in format ['8900', 'S', '17000', 'W'].
    """
    while True:
        print('\n### Enter unit position (format - 5430N 01920E): ###')
        position_data = input('>>> ')
# >>>>>>>>> only for tests!!!! <<<<<<<<<<<<
        if position_data == '':
            return ['5430.000', 'N', '01920.000', 'E']
# >>>>>>>>> only for tests!!!! <<<<<<<<<<<<
        position_regex = re.compile(r'''^(
            ([0-8]\d[0-5]\d|9000)                               # Latitude
            (N|S)
            \s?
            (([0-1][0-7]\d[0-5]\d)|(0[0-9]\d[0-5]\d)|18000)     # Longitude
            (E|W)
            )$''', re.VERBOSE)
        mo = position_regex.search(position_data.upper().strip())
        if mo:
            # Returns position data - ['5432.000', 'N', '01832.000', 'E'].
            return [f'{float(mo.group(2)):.3f}', mo.group(3),
                    f'{float(mo.group(4)):.3f}', mo.group(7)]
        print('\nError: Wrong entry! Try again.')


def ip_addr_port_num(option: str) -> tuple:
    """
    Function asks for IP address and port number for connection.
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


def nmea_data(nav_dict: dict):
    """
    Func returns all NMEA data sentences in one overall NMEA data list.
    """
    gps_position, gps_speed = nav_dict['position'], nav_dict['gps_speed']
    gps_heading = nav_dict['curr_heading']
    gps_altitude = nav_dict['gps_altitude_amsl']
    utc_time, utc_date = utc_data()

    gga_string = f'$GPGGA,{utc_time}.00,{gps_position[0]},'\
        f'{gps_position[1]},{gps_position[2]},{gps_position[3]},'\
        f'1,08,0.9,{gps_altitude},M,32.5,M,,*'
    gll_string = f'$GPGLL,{gps_position[0]},{gps_position[1]},'\
        f'{gps_position[2]},{gps_position[3]},{utc_time}.00,A,*'
    rmc_string = f'$GPRMC,{utc_time},A,{gps_position[0]},{gps_position[1]},'\
        f'{gps_position[2]},{gps_position[3]},{gps_speed},{gps_heading},'\
        f'{utc_date},,,A*'
    # Dumb NMEA sentences (GSA, GSV)
    gsa_string = '$GPGSA,A,3,22,27,10,28,11,24,32,01,14,,,,1.69,0.87,1.45*'
    gsv_string_list = [
        '$GPGSV,3,1,12,01,55,288,39,08,44,194,27,10,26,065,33,11,61,278,28*',
        '$GPGSV,3,2,12,14,43,134,33,17,04,325,,18,81,268,32,22,39,239,31*',
        '$GPGSV,3,3,12,24,08,023,26,27,16,169,38,28,21,305,23,32,49,092,37*',
    ]
    gphdt_string = f'$GPHDT,{gps_heading},T*'
    # List of all NMEA records with added check-sums:
    nmea_data_list = [f'{gga_string}{nmea_check_sum(gga_string)}\r\n',
                      f'{gsa_string}{nmea_check_sum(gsa_string)}\r\n',
                      f'{gsv_string_list[0]}{nmea_check_sum(gsv_string_list[0])}\r\n',
                      f'{gsv_string_list[1]}{nmea_check_sum(gsv_string_list[1])}\r\n',
                      f'{gsv_string_list[2]}{nmea_check_sum(gsv_string_list[2])}\r\n',
                      f'{gll_string}{nmea_check_sum(gll_string)}\r\n',
                      f'{rmc_string}{nmea_check_sum(rmc_string)}\r\n',
                      f'{gphdt_string}{nmea_check_sum(gphdt_string)}\r\n']
    # nmea_data_list = [
    #    '$GPGGA,140041.00,5436.70976,N,01839.98065,E,1,09,0.87,21.7,M,32.5,M,,*60\r\n',
    #    '$GPGSA,A,3,22,27,10,28,11,24,32,01,14,,,,1.69,0.87,1.45*0E\r\n',
    #    '$GPGSV,3,1,12,01,55,288,39,08,44,194,27,10,26,065,33,11,61,278,28*76\r\n',
    #    '$GPGSV,3,2,12,14,43,134,33,17,04,325,,18,81,268,32,22,39,239,31*74\r\n',
    #    '$GPGSV,3,3,12,24,08,023,26,27,16,169,38,28,21,305,23,32,49,092,37*7B\r\n',
    #    '$GPGLL,5436.70976,N,01839.98065,E,064341.00,A,A*67\r\n']
    return nmea_data_list


def new_gps_position_calc(position, heading, speed, timers_dict):
    '''
    Function returns position when unit is in move.
    '''
    # Calculate time from last position.
    # actual_time = time.time()
    actual_time = time.perf_counter()
    time_delta = actual_time - timers_dict['pos_time']
    # assignment of coords.
    lat_a, lat_direction, lon_a, lon_direction = position
    # Knots to m/s conversion.
    speed_ms = float(speed) * 0.514444
    # Distance in meters.
    distance = speed_ms * time_delta

    if lat_direction.lower() == 'n':
        lat_start = float(lat_a[: 2]) + (float(lat_a[2:])/60.)
    else:
        lat_start = - float(lat_a[: 2]) - (float(lat_a[2:])/60.)
    if lon_direction.lower() == 'e':
        lon_start = float(lon_a[: 3]) + (float(lon_a[3:])/60.)
    else:
        lon_start = -float(lon_a[: 3]) - (float(lon_a[3:])/60.)

    # Use WGS84 ellipsoid.
    g = Geod(ellps='WGS84')
    # forward transformation - returns longitude, latitude, back azimuth of terminus points
    lon_end, lat_end, back_azimuth = g.fwd(lon_start, lat_start, float(heading), distance)

    lon_end, lat_end = abs(lon_end), abs(lat_end)
    # New GPS position after calculation.
    position = [f'{int(lat_end):02}{round(lat_end % int(lat_end) * 60,3):02.3f}',
                f'{lat_direction.upper()}',
                f'{int(lon_end):03}{round(lon_end % int(lon_end) * 60,3):02.3f}',
                f'{lon_direction.upper()}']
    # New position fix time.
    # timers_dict['pos_time'] = time.time()
    timers_dict['pos_time'] = time.perf_counter()
    return position, timers_dict


def fix_or_move() -> str:
    """
    Function asks for position type (fixed or in move).
    """
    # Asks for position type.
    while True:
        print('\n### Choose type of position: ')
        print('1 - Unit in a fixed position.')
        print('2 - Unit in move.')
        choose = input('>>> ')
        if choose == '1':
            return 'fixed'
        elif choose == '2':
            return 'move'


def client_thread(conn, addr, nav_dict) -> None:
    """
    Function creates separate thread for each connected client.
    """
    first_run = True
    while True:
        if nav_dict['pos_type'] == 'move':
            if first_run:
                nmea_list, timers_dict = nmea_data_to_send(
                    nav_dict, first_run=first_run)
                first_run = False
            else:
                nmea_list, timers_dict = nmea_data_to_send(nav_dict, timers_dict)
        elif nav_dict['pos_type'] == 'fixed':
            nmea_list = nmea_data(nav_dict)
        try:
            for data in nmea_list:
                conn.sendall(data.encode())
                time.sleep(0.1)
            time.sleep(1)
        except:
            break
    # Came out of the loop.
    conn.close()
    print(f'Connection closed with {addr[0]}:{addr[1]}')


def nmea_data_to_send(nav_dict: dict, timers_dict=None, first_run=False):
    """
    Function prepares NMEA data to send.
    """
    # Local auxiliary variables.
    gps_position, gps_speed = nav_dict['position'], nav_dict['gps_speed']
    if first_run:
        # Set time stamps for new position and new heading.
        timers_dict = {'pos_time': time.perf_counter(),
                       'head_time': time.perf_counter()}
        # Prepares NMEA data for first position - in move.
        nmea_list = nmea_data(nav_dict)
    else:
        # Calculate new heading - in move.
        # The new heading is calculated on the basis of elapsed time
        actual_time = time.perf_counter()
        # The angle by which it is going to change course.
        turn_angle = 120
        # Change heading after 5 second on a steady course.
        if actual_time - timers_dict['head_time'] > 60:
            new_course = float(nav_dict['curr_heading']) + 5
            initial_course = float(nav_dict['init_heading'])
            if new_course >= 360:
                new_course -= 360
            elif new_course < 0:
                new_course = 360 - new_course
            nav_dict['curr_heading'] = str(new_course)

            # Reset the time when the course changes were made by 'turn_angle'
            if abs(new_course - initial_course) >= turn_angle:
                nav_dict['init_heading'] = str(new_course)
                timers_dict['head_time'] = time.perf_counter()

        # Calculate new position - in move.
        gps_position, timers_dict = new_gps_position_calc(
            gps_position, nav_dict['curr_heading'], gps_speed, timers_dict)
        # Prepares NMEA data for new position and new heading.
        # nav_dict['init_heading'] = nav_dict['curr_heading']
        nav_dict['position'] = gps_position
        nmea_list = nmea_data(nav_dict)
    return nmea_list, timers_dict


##
# MAIN PART #
##
# TODO:    1. Object in fix position
# TODO:    2. Object in move (enter speed, start position and heading)
# TODO:     Enter gps_speed and gps_heading by hand when in move.
#
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

# test nav_data_dictionary
nav_data_dict = {'gps_speed': '100.035',
                 'init_heading': '45.0',
                 'curr_heading': '45.0',
                 'gps_altitude_amsl': '15.2',
                 'position': [],
                 'pos_type': None}

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
    nav_data_dict['pos_type'] = fix_or_move()

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
        first_run = True
        while True:
            if nav_data_dict['pos_type'] == 'move':
                if first_run:
                    nmea_list, timers_dict = nmea_data_to_send(
                        nav_data_dict, first_run=first_run)
                    first_run = False
                else:
                    nmea_list, timers_dict = nmea_data_to_send(nav_data_dict, timers_dict)
            elif nav_data_dict['pos_type'] == 'fixed':
                nmea_list = nmea_data(nav_data_dict)
            for data in nmea_list:
                ser.write(str.encode(data))
                time.sleep(0.1)
            time.sleep(1)

elif emulator_option == '2':
    # Runs telnet server witch emulates NMEA device.

    # Ask for local IP addr and port number.
    srv_ip_address, srv_port = ip_addr_port_num('telnet')

    # Ask for GPS position.
    # position = position_input()
    nav_data_dict['position'] = position_input()
    # Choose type of position.
    # pos_type = fix_or_move()
    nav_data_dict['pos_type'] = fix_or_move()

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

    # Ask for position:
    nav_data_dict['position'] = position_input()

    # Choose type of position.
    nav_data_dict['pos_type'] = fix_or_move()

    # Ask for remote IP addr and port number.
    srv_ip_address, srv_port = ip_addr_port_num('stream')

    print('\n### Enter transport protocol - TCP or UDP: ###')
    stream_proto = input('>>> ')
    if stream_proto.lower().strip() == 'tcp':
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # send TCP
        try:
            s.connect((srv_ip_address, srv_port))
            print(f'\nSending NMEA data - TCP stream to {srv_ip_address}:{srv_port}...')

            first_run = True
            while True:
                if nav_data_dict['pos_type'] == 'move':
                    if first_run:
                        nmea_list, timers_dict = nmea_data_to_send(
                            nav_data_dict, first_run=first_run)
                        first_run = False
                    else:
                        nmea_list, timers_dict = nmea_data_to_send(nav_data_dict, timers_dict)
                elif nav_data_dict['pos_type'] == 'fixed':
                    nmea_list = nmea_data(nav_data_dict)

                for data in nmea_list:
                    s.send(data.encode())    # lub conn.sendall(data.encode('ascii'))
                    # Send one packet with NMEA sentence in every 1 sek.
                    time.sleep(1)
                # time.sleep(1)
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

        first_run = True
        while True:
            if nav_data_dict['pos_type'] == 'move':
                if first_run:
                    nmea_list, timers_dict = nmea_data_to_send(
                        nav_data_dict, first_run=first_run)
                    first_run = False
                else:
                    nmea_list, timers_dict = nmea_data_to_send(nav_data_dict, timers_dict)
            elif nav_data_dict['pos_type'] == 'fixed':
                nmea_list = nmea_data(nav_data_dict)

            for data in nmea_list:
                try:
                    s.sendto(data.encode(), (srv_ip_address, srv_port))
                    # Send one packet with NMEA sentence in every 1 sek.
                    time.sleep(0.2)
                except OSError as err:
                    print(f'*** Error: {err} ***')
                    sys.exit()
                except KeyboardInterrupt:
                    print('\n*** Exit script! ***')
                    sys.exit()
