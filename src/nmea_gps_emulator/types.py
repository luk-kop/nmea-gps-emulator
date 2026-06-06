"""Shared type definitions for the NMEA GPS Emulator."""

from dataclasses import dataclass, field


@dataclass
class CliConfig:
    """Parsed CLI configuration passed to the Menu controller."""

    mode: str
    position: dict[str, str]
    speed: float
    heading: float
    altitude: float
    ip: str
    port: int
    protocol: str
    serial_port: str | None
    baudrate: int
    headless: bool
    # Names of navigation arguments the user set explicitly on the command line
    # (i.e. that differ from the parser defaults). Used to pre-seed the
    # interactive prompts so explicitly provided values are honored even in
    # interactive mode.
    provided: frozenset[str] = field(default_factory=frozenset)
