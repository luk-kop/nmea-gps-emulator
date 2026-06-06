"""Entry point for running the package with python -m nmea_gps_emulator."""

import argparse
import logging
import sys

from .main import Menu
from .types import CliConfig
from .validators import parse_ipv4, parse_position, parse_speed


def validate_args(args: argparse.Namespace) -> dict[str, str]:
    """
    Validate parsed CLI arguments relevant to the selected mode.

    Navigation arguments (``--position``, ``--speed``, ``--heading``) are
    validated in every mode, since they are honored both in non-interactive
    modes and as interactive prompt defaults. Network arguments (``--ip``,
    ``--port``) are only validated for the network modes that use them, and
    ``--serial-port`` only for serial mode, so arguments irrelevant to the
    selected mode are silently ignored (consistent with the documented
    behavior).

    Args:
        args: Parsed argument namespace.

    Returns:
        The parsed position dict, so callers can reuse it without parsing
        ``--position`` a second time.

    Raises:
        SystemExit: With exit code 1 if validation fails.

    """
    try:
        position = parse_position(args.position)
    except ValueError:
        print(f"Error: invalid position format '{args.position}'. Expected: '5430N 01920E'", file=sys.stderr)
        sys.exit(1)
    try:
        parse_speed(str(args.speed))
    except ValueError:
        print("Error: --speed must be between 0 and 999", file=sys.stderr)
        sys.exit(1)
    if not (0 <= args.heading < 360):
        print("Error: --heading must be between 0 and 359", file=sys.stderr)
        sys.exit(1)

    if args.headless and args.mode == "interactive":
        print("Error: --headless requires --mode serial, tcp-server, or stream", file=sys.stderr)
        sys.exit(1)

    if args.mode in ("tcp-server", "stream"):
        try:
            parse_ipv4(args.ip)
        except ValueError:
            print(f"Error: invalid IPv4 address '{args.ip}'", file=sys.stderr)
            sys.exit(1)
        if not (1 <= args.port <= 65535):
            print("Error: --port must be between 1 and 65535", file=sys.stderr)
            sys.exit(1)

    if args.mode == "serial" and args.serial_port is None:
        print("Error: --serial-port is required when --mode is 'serial'", file=sys.stderr)
        sys.exit(1)

    return position


def build_cli_config(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    position: dict[str, str],
) -> CliConfig:
    """
    Convert parsed argparse namespace into a CliConfig.

    Args:
        args: Parsed argument namespace.
        parser: The parser that produced *args*, used to detect which
            navigation arguments the user set explicitly (value differs from
            the parser default).
        position: The already-parsed position dict (from :func:`validate_args`).

    Returns:
        A populated :class:`CliConfig` instance.

    """
    nav_fields = ("position", "speed", "heading", "altitude")
    provided = frozenset(name for name in nav_fields if getattr(args, name) != parser.get_default(name))
    return CliConfig(
        mode=args.mode,
        position=position,
        speed=args.speed,
        heading=args.heading,
        altitude=args.altitude,
        ip=args.ip,
        port=args.port,
        protocol=args.protocol,
        serial_port=args.serial_port,
        baudrate=args.baudrate,
        headless=args.headless,
        provided=provided,
    )


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser for the NMEA GPS Emulator CLI.

    Returns:
        A configured :class:`argparse.ArgumentParser`.

    """
    parser = argparse.ArgumentParser(
        description="NMEA GPS Emulator - Generate and transmit NMEA 0183 sentences",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Mutually exclusive logging group
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress informational messages (only show errors and user prompts)",
    )
    log_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output with detailed debug information",
    )

    # Operating mode
    parser.add_argument(
        "-m",
        "--mode",
        choices=["serial", "tcp-server", "stream", "interactive"],
        default="interactive",
        help="Emulator operating mode (default: interactive)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help=("Run without runtime stdin prompts after startup (requires --mode serial, tcp-server, or stream)"),
    )

    # Navigation parameters
    parser.add_argument(
        "-p",
        "--position",
        type=str,
        default="5430N 01920E",
        help="GPS position in compact format, e.g. '5430N 01920E' (default: 5430N 01920E)",
    )
    parser.add_argument(
        "-s",
        "--speed",
        type=float,
        default=0.0,
        help="Speed in knots, 0-999 (default: 0.0)",
    )
    parser.add_argument(
        "-c",
        "--heading",
        type=float,
        default=0.0,
        help="Course in degrees, 0-359 (default: 0.0)",
    )
    parser.add_argument(
        "-a",
        "--altitude",
        type=float,
        default=15.2,
        help="Altitude in meters (default: 15.2)",
    )

    # Network parameters
    parser.add_argument(
        "--ip",
        type=str,
        default="127.0.0.1",
        help="IPv4 address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=2020,
        help="Port number, 1-65535 (default: 2020)",
    )
    parser.add_argument(
        "--protocol",
        choices=["tcp", "udp"],
        default="tcp",
        help="Transport protocol for stream mode (default: tcp)",
    )

    # Serial parameters
    parser.add_argument(
        "--serial-port",
        type=str,
        default=None,
        help="Serial device path, e.g. /dev/ttyUSB0 or COM1 (required for serial mode)",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        choices=[4800, 9600, 19200, 38400, 57600, 115200],
        default=4800,
        help="Serial baudrate (default: 4800)",
    )

    return parser


def main() -> None:
    """Parse CLI arguments, configure logging, and launch the NMEA GPS Emulator."""
    parser = build_parser()
    args = parser.parse_args()

    # Configure logging based on flags
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    if args.verbose:
        log_level = logging.DEBUG
    elif args.quiet:
        log_level = logging.ERROR
    else:
        log_level = logging.INFO

    logging.basicConfig(format=log_format, level=log_level, datefmt="%H:%M:%S")

    # Post-parse validation (returns the parsed position for reuse)
    position = validate_args(args)

    # Build CLI config and launch
    config = build_cli_config(args, parser, position)
    Menu(quiet=args.quiet, cli_config=config).run()


if __name__ == "__main__":
    main()
