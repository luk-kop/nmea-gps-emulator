"""Custom threading classes for NMEA GPS emulator connections."""

import logging
import re
import socket
import sys
import threading
import time
import uuid
from typing import Any, NoReturn

import serial
import serial.tools.list_ports

from .constants import (
    MAX_LOOP_EXECUTION_TIME_SEC,
    MAX_TCP_CONNECTIONS,
    MIN_SLEEP_TIME_SEC,
    NMEA_SEND_INTERVAL_SEC,
    NMEA_SENTENCE_DELAY_SEC,
    SOCKET_BIND_RETRY_MINUTES,
    TIMING_PRECISION_TOLERANCE,
)
from .nmea_gps import NmeaMsg
from .utils import exit_script


def safe_sleep_with_timing_check(target_interval: float, timer_start: float, thread_name: str = "") -> None:
    """Safely sleep for the remaining time in a target interval with timing validation.

    Calculates the remaining sleep time and ensures it's never negative. Logs warnings
    if loop execution time exceeds expected thresholds.

    Args:
        target_interval: Target loop interval in seconds (typically 1.0)
        timer_start: Start time from time.perf_counter()
        thread_name: Optional thread name for logging purposes

    Returns:
        None

    """
    elapsed_time: float = time.perf_counter() - timer_start
    remaining_time: float = target_interval - elapsed_time

    # Log warning if loop execution is taking too long
    if elapsed_time > MAX_LOOP_EXECUTION_TIME_SEC:
        logging.warning(
            f"Loop execution time ({elapsed_time:.3f}s) exceeds threshold "
            f"({MAX_LOOP_EXECUTION_TIME_SEC}s) in {thread_name or 'thread'}"
        )

    # Ensure sleep time is never negative and has minimum precision
    sleep_time: float = max(remaining_time, MIN_SLEEP_TIME_SEC)

    # Add small tolerance to prevent busy waiting
    if sleep_time < TIMING_PRECISION_TOLERANCE:
        sleep_time = TIMING_PRECISION_TOLERANCE

    time.sleep(sleep_time)


def validate_timing_performance(elapsed_time: float, thread_name: str = "") -> None:
    """Validate timing performance and log issues.

    Checks if loop execution time is within acceptable bounds and logs
    appropriate warnings or errors for timing issues.

    Args:
        elapsed_time: Actual elapsed time for the loop iteration
        thread_name: Optional thread name for logging purposes

    Returns:
        None

    """
    if elapsed_time > NMEA_SEND_INTERVAL_SEC:
        logging.error(
            f"Critical timing issue: Loop execution ({elapsed_time:.3f}s) "
            f"exceeds target interval ({NMEA_SEND_INTERVAL_SEC}s) in {thread_name or 'thread'}"
        )
    elif elapsed_time > MAX_LOOP_EXECUTION_TIME_SEC:
        logging.warning(
            f"Timing warning: Loop execution ({elapsed_time:.3f}s) "
            f"approaching target interval in {thread_name or 'thread'}"
        )


def run_telnet_server_thread(srv_ip_address: str, srv_port: int, nmea_obj: NmeaMsg) -> NoReturn:
    """Start TCP (telnet) server thread sending NMEA data to connected clients.

    Creates a TCP server socket that listens for incoming connections and spawns
    individual NmeaSrvThread instances for each client connection. Manages up to
    MAX_TCP_CONNECTIONS concurrent connections.

    Args:
        srv_ip_address: IP address to bind the server to
        srv_port: Port number to listen on
        nmea_obj: NMEA message object to send to clients

    Returns:
        Never returns (NoReturn) - runs indefinitely until terminated

    Raises:
        SystemExit: If socket binding fails or other critical errors occur

    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Bind socket to local host and port.
        try:
            s.bind((srv_ip_address, srv_port))
        except OSError as err:
            print(f"\n*** Bind failed. Error: {err.strerror}. ***")
            print(f"Change IP/port settings or try again in next {SOCKET_BIND_RETRY_MINUTES} minutes.")
            exit_script()
            # sys.exit()
        # Start listening on socket
        s.listen(MAX_TCP_CONNECTIONS)
        print(f"\n*** Server listening on {srv_ip_address}:{srv_port}... ***\n")
        while True:
            # Scripts waiting for client calls
            # The server is blocked (suspended) and is waiting for a client connection.
            conn: socket.socket
            ip_add: tuple[str, int]
            conn, ip_add = s.accept()
            # print(f'\n*** Connected with {ip_add[0]}:{ip_add[1]} ***')
            logging.info(f"Connected with {ip_add[0]}:{ip_add[1]}")
            thread_list: list[str] = [thread.name for thread in threading.enumerate()]
            if (
                len([thread_name for thread_name in thread_list if thread_name.startswith("nmea_srv")])
                < MAX_TCP_CONNECTIONS
            ):
                nmea_srv_thread = NmeaSrvThread(
                    name=f"nmea_srv{uuid.uuid4().hex}",
                    daemon=True,
                    conn=conn,
                    ip_add=ip_add,
                    nmea_object=nmea_obj,
                )
                nmea_srv_thread.start()
            else:
                # Close connection if number of scheduler jobs > max_sched_jobs
                conn.close()
                # print(f'\n*** Connection closed with {ip_add[0]}:{ip_add[1]} ***')
                logging.info(f"Connection closed with {ip_add[0]}:{ip_add[1]}")


class NmeaSrvThread(threading.Thread):
    """A thread dedicated for TCP (telnet) server-client connection.

    Base class for NMEA data transmission threads that provides thread-safe
    speed and heading updates using RLock synchronization. Handles individual
    client connections and manages NMEA data streaming.
    """

    def __init__(
        self,
        nmea_object: NmeaMsg,
        ip_add: tuple[str, int] | None = None,
        conn: socket.socket | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize NMEA server thread with connection and NMEA object.

        Args:
            nmea_object: NMEA message generator object
            ip_add: Client IP address and port tuple (for server connections)
            conn: Socket connection object (for server connections)
            *args: Additional positional arguments passed to Thread.__init__
            **kwargs: Additional keyword arguments passed to Thread.__init__

        Returns:
            None

        """
        super().__init__(*args, **kwargs)
        self.heading: float | None = None
        self.speed: float | None = None
        self._heading_cache: float = 0
        self._speed_cache: float = 0
        self.conn: socket.socket | None = conn
        self.ip_add: tuple[str, int] | None = ip_add
        self.nmea_object: NmeaMsg = nmea_object
        self._lock: threading.RLock = threading.RLock()

    def set_speed(self, speed: float) -> None:
        """Set the target speed for the NMEA object.

        Thread-safe method to update the target speed using RLock synchronization.
        The speed change will be applied gradually in the next NMEA update cycle.

        Args:
            speed: Target speed in knots

        Returns:
            None

        """
        with self._lock:
            self.speed = speed

    def set_heading(self, heading: float) -> None:
        """Set the target heading for the NMEA object.

        Thread-safe method to update the target heading using RLock synchronization.
        The heading change will be applied gradually in the next NMEA update cycle.

        Args:
            heading: Target heading in degrees (0-359)

        Returns:
            None

        """
        with self._lock:
            self.heading = heading

    def run(self) -> None:
        """Execute main thread loop for sending NMEA data.

        Main execution loop that handles NMEA data generation and transmission
        to connected clients. Manages thread synchronization to ensure consistent
        NMEA data across multiple client connections and handles connection errors.

        Returns:
            None

        Raises:
            SystemExit: When connection is broken or client disconnects

        """
        while True:
            timer_start: float = time.perf_counter()
            with self._lock:
                # Nmea object speed and heading update
                if self.heading and self.heading != self._heading_cache:
                    self.nmea_object.heading_targeted = self.heading
                    self._heading_cache = self.heading
                if self.speed and self.speed != self._speed_cache:
                    self.nmea_object.speed_targeted = self.speed
                    self._speed_cache = self.speed
                # The following commands allow the same copies of NMEA data is sent on all threads
                # Only first thread in a list can iterate over NMEA object (the same nmea output in all threads)
                thread_list: list[str] = [
                    thread.name for thread in threading.enumerate() if thread.name.startswith("nmea_srv")
                ]
                current_thread_name: str = threading.current_thread().name
                if len(thread_list) > 1 and current_thread_name != thread_list[0]:
                    nmea_list: list[str] = [f"{_}" for _ in self.nmea_object.nmea_sentences]
                else:
                    nmea_list: list[str] = [f"{_}" for _ in next(self.nmea_object)]  # type: ignore[no-redef]
                try:
                    for nmea in nmea_list:
                        if self.conn:
                            self.conn.sendall(nmea.encode())
                        time.sleep(NMEA_SENTENCE_DELAY_SEC)
                except (BrokenPipeError, OSError):
                    if self.conn:
                        self.conn.close()
                    if self.ip_add:
                        logging.info(f"Connection closed with {self.ip_add[0]}:{self.ip_add[1]}")
                    # Close thread
                    sys.exit()
            safe_sleep_with_timing_check(NMEA_SEND_INTERVAL_SEC, timer_start, self.name)


class NmeaStreamThread(NmeaSrvThread):
    """A thread dedicated for TCP or UDP stream connection.

    Extends NmeaSrvThread to provide client-side streaming functionality
    for sending NMEA data to remote servers via TCP or UDP protocols.
    Handles connection establishment and data transmission.
    """

    def __init__(self, proto: str, port: int, ip_add: str, *args: Any, **kwargs: Any) -> None:
        """Initialize NMEA stream thread with protocol and port configuration.

        Args:
            proto: Protocol type - either "tcp" or "udp"
            port: Remote port number to connect to
            ip_add: Remote IP address to connect to
            *args: Additional positional arguments passed to parent class
            **kwargs: Additional keyword arguments passed to parent class

        Returns:
            None

        """
        # Don't pass ip_add to parent since it expects tuple format for server connections
        super().__init__(*args, **kwargs)
        self.proto: str = proto
        self.port: int = port
        self.stream_ip_add: str = ip_add

    def run(self) -> None:
        """Execute TCP or UDP stream connection.

        Establishes connection to remote server and continuously streams NMEA data
        using the specified protocol (TCP or UDP). Handles connection errors and
        provides appropriate error messages for different failure scenarios.

        Returns:
            None

        Raises:
            SystemExit: When connection fails or network errors occur

        """
        if self.proto == "tcp":
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((self.stream_ip_add, self.port))
                    print(f"\n*** Sending NMEA data - TCP stream to {self.stream_ip_add}:{self.port}... ***\n")
                    while True:
                        timer_start: float = time.perf_counter()
                        with self._lock:
                            # Nmea object speed and heading update
                            if self.heading and self.heading != self._heading_cache:
                                self.nmea_object.heading_targeted = self.heading
                                self._heading_cache = self.heading
                            if self.speed and self.speed != self._speed_cache:
                                self.nmea_object.speed_targeted = self.speed
                                self._speed_cache = self.speed
                            nmea_list: list[str] = [f"{_}" for _ in next(self.nmea_object)]
                            for nmea in nmea_list:
                                s.send(nmea.encode())
                                time.sleep(NMEA_SENTENCE_DELAY_SEC)
                            # Start next loop after 1 sec
                        safe_sleep_with_timing_check(NMEA_SEND_INTERVAL_SEC, timer_start, "TCP-Stream")
            except (
                OSError,
                TimeoutError,
                ConnectionRefusedError,
                BrokenPipeError,
            ) as err:
                print(f"\n*** Error: {err.strerror} ***\n")
                exit_script()
        elif self.proto == "udp":
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                print(f"\n*** Sending NMEA data - UDP stream to {self.stream_ip_add}:{self.port}... ***\n")
                while True:
                    timer_start: float = time.perf_counter()  # type: ignore[no-redef]
                    with self._lock:
                        # Nmea object speed and heading update
                        if self.heading and self.heading != self._heading_cache:
                            self.nmea_object.heading_targeted = self.heading
                            self._heading_cache = self.heading
                        if self.speed and self.speed != self._speed_cache:
                            self.nmea_object.speed_targeted = self.speed
                            self._speed_cache = self.speed
                        nmea_list: list[str] = [f"{_}" for _ in next(self.nmea_object)]  # type: ignore[no-redef]
                        for nmea in nmea_list:
                            try:
                                s.sendto(nmea.encode(), (self.stream_ip_add, self.port))
                                time.sleep(NMEA_SENTENCE_DELAY_SEC)
                            except OSError as err:
                                print(f"*** Error: {err.strerror} ***")
                                exit_script()
                        # Start next loop after 1 sec
                    safe_sleep_with_timing_check(NMEA_SEND_INTERVAL_SEC, timer_start, "UDP-Stream")


class NmeaSerialThread(NmeaSrvThread):
    """A thread dedicated for serial connection.

    Extends NmeaSrvThread to provide serial port communication functionality
    for sending NMEA data over RS-232/USB serial connections. Handles serial
    port configuration and manages communication errors.
    """

    def __init__(self, serial_config: dict[str, str | int], *args: Any, **kwargs: Any) -> None:
        """Initialize NMEA serial thread with serial port configuration.

        Args:
            serial_config: Dictionary containing serial port settings with keys:
                          - port: Serial port device path/name
                          - baudrate: Communication speed in bps
                          - bytesize: Data bits (typically 8)
                          - parity: Parity setting ('N', 'E', 'O')
                          - stopbits: Stop bits (typically 1)
                          - timeout: Read timeout in seconds
            *args: Additional positional arguments passed to parent class
            **kwargs: Additional keyword arguments passed to parent class

        Returns:
            None

        """
        super().__init__(*args, **kwargs)
        self.serial_config: dict[str, str | int] = serial_config

    def run(self) -> None:
        """Execute serial connection for NMEA data transmission.

        Opens serial port with specified configuration and continuously transmits
        NMEA data. Handles serial port errors and provides helpful error messages
        including permission fix suggestions for Linux systems.

        Returns:
            None

        Raises:
            SystemExit: When serial port cannot be opened or communication fails

        """
        # Open serial port.
        try:
            with serial.Serial(
                self.serial_config["port"],
                baudrate=self.serial_config["baudrate"],
                bytesize=self.serial_config["bytesize"],
                parity=self.serial_config["parity"],
                stopbits=self.serial_config["stopbits"],
                timeout=self.serial_config["timeout"],
            ) as ser:
                print(
                    f"Serial port settings: {self.serial_config['port']} {self.serial_config['baudrate']} "
                    f"{self.serial_config['bytesize']}{self.serial_config['parity']}{self.serial_config['stopbits']}"
                )
                print("Sending NMEA data...")
                while True:
                    timer_start: float = time.perf_counter()
                    with self._lock:
                        # Nmea object speed and heading update
                        if self.heading and self.heading != self._heading_cache:
                            self.nmea_object.heading_targeted = self.heading
                            self._heading_cache = self.heading
                        if self.speed and self.speed != self._speed_cache:
                            self.nmea_object.speed_targeted = self.speed
                            self._speed_cache = self.speed
                        nmea_list: list[str] = [f"{_}" for _ in next(self.nmea_object)]
                        for nmea in nmea_list:
                            ser.write(str.encode(nmea))
                            time.sleep(NMEA_SENTENCE_DELAY_SEC)
                    safe_sleep_with_timing_check(NMEA_SEND_INTERVAL_SEC, timer_start, "Serial")
        except serial.serialutil.SerialException as error:
            # Remove error number from output [...]
            error_formatted = re.sub(r"\[(.*?)\]", "", str(error)).strip().replace("  ", " ").capitalize()
            logging.error(f"{error_formatted}. Please try 'sudo chmod a+rw {self.serial_config['port']}'")
            exit_script()
