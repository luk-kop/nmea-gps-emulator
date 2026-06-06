#!/usr/bin/env python3

"""Main module for NMEA GPS Emulator application."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from typing import NoReturn

from .constants import (
    DEFAULT_ALTITUDE_AMSL,
    MENU_CHOICE_QUIT,
    MENU_CHOICE_SERIAL,
    MENU_CHOICE_STREAM,
    MENU_CHOICE_TCP_SERVER,
    THREAD_HEALTHCHECK_INTERVAL_SEC,
    THREAD_STARTUP_DELAY_SEC,
)
from .custom_thread import (
    NmeaSerialThread,
    NmeaSrvThread,
    NmeaStreamThread,
    run_telnet_server_thread,
)
from .nmea_gps import NmeaMsg
from .types import CliConfig
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
    """
    Display a menu and respond to choices when run.

    Main application controller that provides an interactive menu system
    for selecting NMEA emulation modes (Serial, TCP Server, Stream) and
    manages the lifecycle of NMEA threads and user interactions.
    """

    def __init__(self, quiet: bool = False, cli_config: CliConfig | None = None) -> None:
        """
        Initialize Menu with empty thread and NMEA object references.

        Sets up the menu choice mapping and initializes thread and NMEA object
        references that will be populated during menu execution.

        Args:
            quiet: If True, suppress informational logging messages
            cli_config: Optional parsed CLI configuration for non-interactive mode

        Returns:
            None

        """
        self.quiet = quiet
        self.cli_config = cli_config
        self.nmea_thread: threading.Thread | None = None
        self.nmea_obj: NmeaMsg | None = None
        self.choices: dict[str, Callable[[], None]] = {
            MENU_CHOICE_SERIAL: self.nmea_serial,
            MENU_CHOICE_TCP_SERVER: self.nmea_tcp_server,
            MENU_CHOICE_STREAM: self.nmea_stream,
            MENU_CHOICE_QUIT: self.quit,
        }

    def display_menu(self) -> None:
        """
        Display the main menu options.

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
        """
        Display the menu and respond to choices.

        Main execution method that displays the menu, handles user input,
        sets up navigation data, starts the selected emulation mode, and
        enters the interactive loop for runtime course/speed changes.

        When a non-interactive CLI config is provided, the interactive menu
        is bypassed and the emulator starts directly in the specified mode.

        Returns:
            None

        Raises:
            SystemExit: If user presses Ctrl+C (handled by handle_keyboard_interrupt)

        """
        if self.cli_config is not None and self.cli_config.mode != "interactive":
            self._run_cli_mode()
            if self.cli_config.headless:
                self._headless_loop()
            else:
                self._interactive_loop()
            return

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

    def _run_cli_mode(self) -> None:
        """
        Start emulation directly from CLI configuration without interactive prompts.

        Creates the NMEA message object from CLI-provided navigation parameters
        and launches the appropriate mode thread based on the configured mode.

        Returns:
            None

        """
        assert self.cli_config is not None  # noqa: S101

        self.nmea_obj = NmeaMsg(
            position=self.cli_config.position,
            altitude=self.cli_config.altitude,
            speed=self.cli_config.speed,
            heading=self.cli_config.heading,
        )

        mode = self.cli_config.mode
        if mode == "serial":
            self.nmea_serial(
                serial_port=self.cli_config.serial_port,
                baudrate=self.cli_config.baudrate,
            )
        elif mode == "tcp-server":
            self.nmea_tcp_server(
                ip=self.cli_config.ip,
                port=self.cli_config.port,
            )
        elif mode == "stream":
            self.nmea_stream(
                ip=self.cli_config.ip,
                port=self.cli_config.port,
                protocol=self.cli_config.protocol,
            )

    def _setup_navigation_data(self) -> None:
        """
        Collect navigation data from user input.

        Prompts user for GPS position, heading, and speed, then creates
        the NMEA message object with the collected navigation parameters.

        Navigation arguments the user supplied explicitly on the command line
        (even in interactive mode) are used to pre-seed the corresponding
        prompts, so pressing Enter accepts the CLI-provided value. Altitude,
        which has no prompt, is taken directly from the CLI when provided.

        Returns:
            None

        Raises:
            SystemExit: If user presses Ctrl+C during input (handled by input functions)

        """
        cfg = self.cli_config
        provided = cfg.provided if cfg is not None else frozenset()

        position_default = cfg.position if cfg is not None and "position" in provided else None
        heading_default = cfg.heading if cfg is not None and "heading" in provided else None
        speed_default = cfg.speed if cfg is not None and "speed" in provided else None
        altitude = cfg.altitude if cfg is not None and "altitude" in provided else DEFAULT_ALTITUDE_AMSL

        position = position_input(default=position_default)
        heading = heading_input(default=heading_default)
        speed = speed_input(default=speed_default)

        self.nmea_obj = NmeaMsg(
            position=position,
            altitude=altitude,
            speed=speed,
            heading=heading,
        )

    def _interactive_loop(self) -> None:
        """
        Handle interactive course and speed changes.

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
                        logging.info(f"Updated course to {new_head}° and speed to {new_speed} knots")
                    elif self.nmea_obj:
                        # Set targeted head and speed without connected clients
                        self.nmea_obj.heading_targeted = new_head
                        self.nmea_obj.speed_targeted = new_speed
                        logging.info(f"Updated course to {new_head}° and speed to {new_speed} knots")
                    print()
            except KeyboardInterrupt:
                handle_keyboard_interrupt()

    def _headless_loop(self) -> NoReturn:
        """Keep the emulator running without reading runtime input."""
        logging.info("Headless mode enabled; runtime input prompts disabled")
        while True:
            if not self.nmea_thread or not self.nmea_thread.is_alive():
                print("\n[ERROR] NMEA thread died unexpectedly\n")
                logging.error("NMEA thread terminated unexpectedly")
                raise SystemExit(1)
            try:
                time.sleep(THREAD_HEALTHCHECK_INTERVAL_SEC)
            except KeyboardInterrupt:
                handle_keyboard_interrupt()

    def nmea_serial(
        self,
        serial_port: str | None = None,
        baudrate: int | None = None,
    ) -> None:
        """
        Run serial emulation of NMEA server device.

        When called with parameters (CLI mode), uses the provided values directly.
        When called without parameters (interactive mode), prompts the user for
        serial port configuration.

        Args:
            serial_port: Serial device path. If None, prompts interactively.
            baudrate: Serial baudrate. If None, uses interactive default.

        Returns:
            None

        """
        if serial_port is not None:
            serial_config: dict[str, str | int] = {
                "port": serial_port,
                "baudrate": baudrate if baudrate is not None else 4800,
                "bytesize": 8,
                "parity": "N",
                "stopbits": 1,
                "timeout": 1,
            }
        else:
            serial_config = serial_config_input()
        self.nmea_thread = NmeaSerialThread(
            name=f"nmea_srv{uuid.uuid4().hex}",
            daemon=True,
            serial_config=serial_config,
            nmea_object=self.nmea_obj,
        )
        self.nmea_thread.start()

    def nmea_tcp_server(
        self,
        ip: str | None = None,
        port: int | None = None,
    ) -> None:
        """
        Run telnet server that emulates NMEA device.

        When called with parameters (CLI mode), uses the provided values directly.
        When called without parameters (interactive mode), prompts the user for
        IP address and port.

        Args:
            ip: Local bind IP address. If None, prompts interactively.
            port: Listen port number. If None, prompts interactively.

        Returns:
            None

        """
        if ip is not None and port is not None:
            srv_ip_address, srv_port = ip, port
        else:
            srv_ip_address, srv_port = ip_port_input("telnet")
        self.nmea_thread = threading.Thread(
            target=run_telnet_server_thread,
            args=[srv_ip_address, srv_port, self.nmea_obj],
            daemon=True,
            name="nmea_thread",
        )
        self.nmea_thread.start()

    def nmea_stream(
        self,
        ip: str | None = None,
        port: int | None = None,
        protocol: str | None = None,
    ) -> None:
        """
        Run TCP or UDP NMEA stream to designated host.

        When called with parameters (CLI mode), uses the provided values directly.
        When called without parameters (interactive mode), prompts the user for
        IP address, port, and protocol selection.

        Args:
            ip: Remote target IP address. If None, prompts interactively.
            port: Target port number. If None, prompts interactively.
            protocol: Transport protocol ('tcp' or 'udp'). If None, prompts interactively.

        Returns:
            None

        """
        if ip is not None and port is not None and protocol is not None:
            ip_add, port_num, stream_proto = ip, port, protocol
        else:
            ip_add, port_num = ip_port_input("stream")
            stream_proto = trans_proto_input()
        self.nmea_thread = NmeaStreamThread(
            name=f"nmea_srv{uuid.uuid4().hex}",
            daemon=True,
            ip_add=ip_add,
            port=port_num,
            proto=stream_proto,
            nmea_object=self.nmea_obj,
        )
        self.nmea_thread.start()

    def quit(self) -> NoReturn:
        """
        Exit script gracefully with proper cleanup.

        Displays exit message and terminates the application cleanly
        with exit code 0. Provides opportunity for cleanup before exit.

        Returns:
            Never returns (NoReturn) - terminates the application

        Raises:
            SystemExit: Always exits with code 0

        """
        print("\nExiting...")

        # Give threads a moment to finish current operations
        if self.nmea_thread and self.nmea_thread.is_alive():
            logging.info("Waiting for threads to finish...")
            # Don't wait too long, daemon threads will be terminated anyway
            self.nmea_thread.join(timeout=0.5)

        raise SystemExit(0)
