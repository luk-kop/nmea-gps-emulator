#!/usr/bin/env python3

"""Main module for NMEA GPS Emulator application."""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from typing import NoReturn

from .constants import (
    DEFAULT_ALTITUDE_AMSL,
    DEFAULT_MENU_HEADING,
    DEFAULT_MENU_SPEED,
    MENU_CHOICE_QUIT,
    MENU_CHOICE_SERIAL,
    MENU_CHOICE_STREAM,
    MENU_CHOICE_TCP_SERVER,
    THREAD_STARTUP_DELAY_SEC,
)
from .custom_thread import (
    NmeaSerialThread,
    NmeaSrvThread,
    NmeaStreamThread,
    run_telnet_server_thread,
)
from .nmea_gps import NmeaMsg
from .utils import (
    handle_keyboard_interrupt,
    heading_input,
    heading_speed_input,
    ip_port_input,
    position_input,
    serial_config_input,
    speed_input,
    trans_proto_input,
)


class Menu:
    """Display a menu and respond to choices when run.

    Main application controller that provides an interactive menu system
    for selecting NMEA emulation modes (Serial, TCP Server, Stream) and
    manages the lifecycle of NMEA threads and user interactions.
    """

    def __init__(self) -> None:
        """Initialize Menu with empty thread and NMEA object references.

        Sets up the menu choice mapping and initializes thread and NMEA object
        references that will be populated during menu execution.

        Returns:
            None

        """
        self.nmea_thread: threading.Thread | None = None
        self.nmea_obj: NmeaMsg | None = None
        self.choices: dict[str, Callable[[], None]] = {
            MENU_CHOICE_SERIAL: self.nmea_serial,
            MENU_CHOICE_TCP_SERVER: self.nmea_tcp_server,
            MENU_CHOICE_STREAM: self.nmea_stream,
            MENU_CHOICE_QUIT: self.quit,
        }

    def display_menu(self) -> None:
        """Display the main menu options.

        Shows the ASCII art banner and available emulation options including
        Serial, TCP Server, Stream, and Quit choices with numbered selection.

        Returns:
            None

        """
        print(r"""

..####...#####....####...........######..##...##..##..##..##.......####...######...####...#####..
.##......##..##..##..............##......###.###..##..##..##......##..##....##....##..##..##..##.
.##.###..#####....####...........####....##.#.##..##..##..##......######....##....##..##..#####..
.##..##..##..........##..........##......##...##..##..##..##......##..##....##....##..##..##..##.
..####...##.......####...........######..##...##...####...######..##..##....##.....####...##..##.
.................................................................................................
        """)
        print("Choose emulator option:")
        print("  1. NMEA Serial")
        print("  2. NMEA TCP Server")
        print("  3. NMEA TCP or UDP Stream")
        print("  4. Quit")

    def run(self) -> None:
        """Display the menu and respond to choices.

        Main execution method that displays the menu, handles user input,
        sets up navigation data, starts the selected emulation mode, and
        enters the interactive loop for runtime course/speed changes.

        Returns:
            None

        Raises:
            SystemExit: If user presses Ctrl+C (handled by handle_keyboard_interrupt)

        """
        self.display_menu()
        while True:
            try:
                choice: str = input("> ")
            except KeyboardInterrupt:
                handle_keyboard_interrupt()

            action = self.choices.get(choice)
            if not action:
                continue

            # Handle quit option immediately
            if action == self.quit:
                action()

            # For other options, collect navigation data first
            self._setup_navigation_data()
            action()
            break

        # Start the interactive loop for course/speed changes
        self._interactive_loop()

    def _setup_navigation_data(self) -> None:
        """Collect navigation data from user input.

        Prompts user for GPS position, heading, and speed, then creates
        the NMEA message object with the collected navigation parameters
        and default altitude setting.

        Returns:
            None

        Raises:
            SystemExit: If user presses Ctrl+C during input (handled by input functions)

        """
        nav_data_dict = {
            "gps_speed": DEFAULT_MENU_SPEED,
            "gps_heading": DEFAULT_MENU_HEADING,
            "gps_altitude_amsl": DEFAULT_ALTITUDE_AMSL,
            "position": {},
        }

        nav_data_dict["position"] = position_input()
        nav_data_dict["gps_heading"] = heading_input()
        nav_data_dict["gps_speed"] = speed_input()

        self.nmea_obj = NmeaMsg(
            position=nav_data_dict["position"],  # type: ignore[arg-type]
            altitude=nav_data_dict["gps_altitude_amsl"],  # type: ignore[arg-type]
            speed=nav_data_dict["gps_speed"],  # type: ignore[arg-type]
            heading=nav_data_dict["gps_heading"],  # type: ignore[arg-type]
        )

    def _interactive_loop(self) -> None:
        """Handle interactive course and speed changes.

        Runs continuously to allow real-time updates of course and speed
        while the emulator is running. Monitors thread health and applies
        changes to all active NMEA server threads or the NMEA object directly.

        Returns:
            None

        Raises:
            SystemExit: When thread dies or user presses Ctrl+C

        """
        first_run = True
        while True:
            if not self.nmea_thread or not self.nmea_thread.is_alive():
                print("\n[ERROR] NMEA thread died unexpectedly\n")
                logging.error("NMEA thread terminated unexpectedly")
                raise SystemExit(1)
            try:
                if first_run:
                    time.sleep(THREAD_STARTUP_DELAY_SEC)
                    first_run = False
                try:
                    prompt = input('Press "Enter" to change course/speed or "Ctrl+C" to exit...\n')
                except KeyboardInterrupt:
                    handle_keyboard_interrupt()
                if prompt == "":
                    new_head, new_speed = heading_speed_input()
                    # Get all 'nmea_srv*' telnet server threads
                    thread_list = [thread for thread in threading.enumerate() if isinstance(thread, NmeaSrvThread)]
                    if thread_list:
                        for thr in thread_list:
                            thr.set_heading(new_head)
                            thr.set_speed(new_speed)
                    elif self.nmea_obj:
                        # Set targeted head and speed without connected clients
                        self.nmea_obj.heading_targeted = new_head
                        self.nmea_obj.speed_targeted = new_speed
                    print()
            except KeyboardInterrupt:
                handle_keyboard_interrupt()

    def nmea_serial(self) -> None:
        """Run serial emulation of NMEA server device.

        Prompts for serial port configuration and starts a NmeaSerialThread
        to transmit NMEA data over the specified serial connection. Handles
        RS-232/USB serial communication with configurable port settings.

        Returns:
            None

        """
        # serial_port = '/dev/ttyUSB0'
        # Serial configuration query
        serial_config = serial_config_input()
        self.nmea_thread = NmeaSerialThread(
            name=f"nmea_srv{uuid.uuid4().hex}",
            daemon=True,
            serial_config=serial_config,
            nmea_object=self.nmea_obj,
        )
        self.nmea_thread.start()

    def nmea_tcp_server(self) -> None:
        """Run telnet server that emulates NMEA device.

        Prompts for local IP address and port, then starts a TCP server
        that accepts multiple client connections and streams NMEA data
        to all connected clients simultaneously.

        Returns:
            None

        """
        # Local TCP server IP address and port number.
        srv_ip_address, srv_port = ip_port_input("telnet")
        self.nmea_thread = threading.Thread(
            target=run_telnet_server_thread,
            args=[srv_ip_address, srv_port, self.nmea_obj],
            daemon=True,
            name="nmea_thread",
        )
        self.nmea_thread.start()

    def nmea_stream(self) -> None:
        """Run TCP or UDP NMEA stream to designated host.

        Prompts for remote IP address, port, and protocol selection,
        then starts a client stream connection to send NMEA data to
        a remote server using either TCP or UDP transport.

        Returns:
            None

        """
        # IP address and port number query
        ip_add, port = ip_port_input("stream")
        # Transport protocol query.
        stream_proto = trans_proto_input()
        self.nmea_thread = NmeaStreamThread(
            name=f"nmea_srv{uuid.uuid4().hex}",
            daemon=True,
            ip_add=ip_add,
            port=port,
            proto=stream_proto,
            nmea_object=self.nmea_obj,
        )
        self.nmea_thread.start()

    def quit(self) -> NoReturn:
        """Exit script gracefully with proper cleanup.

        Displays exit message and terminates the application cleanly
        with exit code 0. Provides opportunity for cleanup before exit.

        Returns:
            Never returns (NoReturn) - terminates the application

        Raises:
            SystemExit: Always exits with code 0

        """
        print("\n[INFO] Exiting...\n")

        # Give threads a moment to finish current operations
        if self.nmea_thread and self.nmea_thread.is_alive():
            logging.info("Waiting for threads to finish...")
            # Don't wait too long, daemon threads will be terminated anyway
            self.nmea_thread.join(timeout=0.5)

        raise SystemExit(0)
