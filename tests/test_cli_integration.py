"""Integration tests for Menu Controller behavior with CLI config."""

import unittest
from unittest.mock import patch

from nmea_gps_emulator.constants import DEFAULT_HEADING, DEFAULT_SPEED
from nmea_gps_emulator.main import Menu
from nmea_gps_emulator.types import CliConfig

DEFAULT_POSITION_DICT = {
    "latitude_value": "5430.000",
    "latitude_direction": "N",
    "longitude_value": "01920.000",
    "longitude_direction": "E",
}


def make_config(**overrides: object) -> CliConfig:
    """Build a CliConfig with sensible defaults, overriding individual fields."""
    base = {
        "mode": "tcp-server",
        "position": DEFAULT_POSITION_DICT,
        "speed": 12.5,
        "heading": 90.0,
        "altitude": 42.0,
        "ip": "127.0.0.1",
        "port": 2020,
        "protocol": "tcp",
        "serial_port": "/dev/ttyUSB0",
        "baudrate": 9600,
        "headless": False,
        "provided": frozenset(),
    }
    base.update(overrides)
    return CliConfig(**base)  # type: ignore[arg-type]


class TestRunCliModeDispatch(unittest.TestCase):
    """_run_cli_mode should create the NMEA object and dispatch by mode."""

    def test_serial_dispatch(self) -> None:
        """Serial mode calls nmea_serial with the configured port/baudrate."""
        menu = Menu(cli_config=make_config(mode="serial"))
        with (
            patch.object(menu, "nmea_serial") as serial,
            patch.object(menu, "nmea_tcp_server") as tcp,
            patch.object(menu, "nmea_stream") as stream,
        ):
            menu._run_cli_mode()
        serial.assert_called_once_with(serial_port="/dev/ttyUSB0", baudrate=9600)
        tcp.assert_not_called()
        stream.assert_not_called()
        self.assertIsNotNone(menu.nmea_obj)

    def test_tcp_server_dispatch(self) -> None:
        """TCP-server mode calls nmea_tcp_server with the configured ip/port."""
        menu = Menu(cli_config=make_config(mode="tcp-server", ip="0.0.0.0", port=3000))
        with (
            patch.object(menu, "nmea_serial") as serial,
            patch.object(menu, "nmea_tcp_server") as tcp,
            patch.object(menu, "nmea_stream") as stream,
        ):
            menu._run_cli_mode()
        tcp.assert_called_once_with(ip="0.0.0.0", port=3000)
        serial.assert_not_called()
        stream.assert_not_called()

    def test_stream_dispatch(self) -> None:
        """Stream mode calls nmea_stream with the configured ip/port/protocol."""
        menu = Menu(cli_config=make_config(mode="stream", ip="192.168.1.1", port=5000, protocol="udp"))
        with (
            patch.object(menu, "nmea_serial") as serial,
            patch.object(menu, "nmea_tcp_server") as tcp,
            patch.object(menu, "nmea_stream") as stream,
        ):
            menu._run_cli_mode()
        stream.assert_called_once_with(ip="192.168.1.1", port=5000, protocol="udp")
        serial.assert_not_called()
        tcp.assert_not_called()

    def test_nmea_object_uses_cli_navigation(self) -> None:
        """The NMEA object is built from CLI navigation parameters."""
        menu = Menu(cli_config=make_config(mode="tcp-server", speed=7.0, heading=120.0))
        with (
            patch.object(menu, "nmea_tcp_server"),
        ):
            menu._run_cli_mode()
        self.assertIsNotNone(menu.nmea_obj)
        self.assertEqual(menu.nmea_obj.speed, 7.0)
        self.assertEqual(menu.nmea_obj.heading, 120.0)
        self.assertEqual(menu.nmea_obj.position, DEFAULT_POSITION_DICT)


class TestRunRouting(unittest.TestCase):
    """run() should route between CLI mode and the interactive menu."""

    def test_non_interactive_mode_bypasses_menu(self) -> None:
        """A non-interactive mode runs _run_cli_mode then the interactive loop."""
        menu = Menu(cli_config=make_config(mode="tcp-server"))
        with (
            patch.object(menu, "_run_cli_mode") as run_cli,
            patch.object(menu, "_interactive_loop") as loop,
            patch.object(menu, "_headless_loop") as headless_loop,
            patch.object(menu, "display_menu") as show_menu,
        ):
            menu.run()
        run_cli.assert_called_once()
        loop.assert_called_once()
        headless_loop.assert_not_called()
        show_menu.assert_not_called()

    def test_headless_mode_bypasses_runtime_prompt(self) -> None:
        """Headless direct-start mode runs the monitor loop instead of stdin prompts."""
        menu = Menu(cli_config=make_config(mode="tcp-server", headless=True))
        with (
            patch.object(menu, "_run_cli_mode") as run_cli,
            patch.object(menu, "_interactive_loop") as interactive_loop,
            patch.object(menu, "_headless_loop") as headless_loop,
            patch.object(menu, "display_menu") as show_menu,
        ):
            menu.run()
        run_cli.assert_called_once()
        headless_loop.assert_called_once()
        interactive_loop.assert_not_called()
        show_menu.assert_not_called()

    def test_interactive_mode_uses_menu(self) -> None:
        """An interactive config does not invoke the CLI-mode shortcut."""
        menu = Menu(cli_config=make_config(mode="interactive"))
        with (
            patch.object(menu, "_run_cli_mode") as run_cli,
            patch.object(menu, "display_menu"),
            patch("builtins.input", side_effect=["4"]),  # choose "Quit"
            self.assertRaises(SystemExit),
        ):
            menu.run()
        run_cli.assert_not_called()


class TestInteractivePreSeeding(unittest.TestCase):
    """_setup_navigation_data should honor explicitly-provided CLI params."""

    def _build_obj(self, config: CliConfig) -> Menu:
        """Run _setup_navigation_data with all prompts left blank (Enter)."""
        menu = Menu(cli_config=config)
        with patch("nmea_gps_emulator.utils.safe_input", return_value=""):
            menu._setup_navigation_data()
        return menu

    def test_provided_values_seed_prompts(self) -> None:
        """Explicitly provided params become the Enter-defaults."""
        config = make_config(
            mode="interactive",
            speed=33.0,
            heading=210.0,
            altitude=99.0,
            provided=frozenset({"speed", "heading", "altitude"}),
        )
        menu = self._build_obj(config)
        self.assertIsNotNone(menu.nmea_obj)
        self.assertEqual(menu.nmea_obj.speed, 33.0)
        self.assertEqual(menu.nmea_obj.heading, 210.0)

    def test_unprovided_values_use_interactive_defaults(self) -> None:
        """Params not supplied on the CLI keep the original interactive defaults."""
        config = make_config(mode="interactive", speed=0.0, heading=0.0, provided=frozenset())
        menu = self._build_obj(config)
        self.assertIsNotNone(menu.nmea_obj)
        self.assertEqual(menu.nmea_obj.heading, DEFAULT_HEADING)
        self.assertEqual(menu.nmea_obj.speed, DEFAULT_SPEED)

    def test_provided_position_seeds_prompt(self) -> None:
        """An explicitly provided position is used when the prompt is left blank."""
        custom = {
            "latitude_value": "4807.000",
            "latitude_direction": "N",
            "longitude_value": "01131.000",
            "longitude_direction": "E",
        }
        config = make_config(mode="interactive", position=custom, provided=frozenset({"position"}))
        menu = self._build_obj(config)
        self.assertIsNotNone(menu.nmea_obj)
        self.assertEqual(menu.nmea_obj.position, custom)


if __name__ == "__main__":
    unittest.main()
