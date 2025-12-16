"""Entry point for running the package with python -m nmea_gps_emulator."""

import logging

from nmea_gps_emulator.main import Menu


def main() -> None:
    """Run the NMEA GPS Emulator."""
    log_format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=log_format, level=logging.INFO, datefmt="%H:%M:%S")
    Menu().run()


if __name__ == "__main__":
    main()
