"""Entry point for running the package with python -m nmea_gps_emulator."""

import argparse
import logging
import sys

from nmea_gps_emulator.main import Menu


def main() -> None:
    """Run the NMEA GPS Emulator."""
    parser = argparse.ArgumentParser(
        description="NMEA GPS Emulator - Generate and transmit NMEA 0183 sentences",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress informational messages (only show errors and user prompts)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output with detailed debug information",
    )

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

    # Validate conflicting flags
    if args.quiet and args.verbose:
        print("Error: --quiet and --verbose flags cannot be used together", file=sys.stderr)
        sys.exit(1)

    Menu(quiet=args.quiet).run()


if __name__ == "__main__":
    main()
