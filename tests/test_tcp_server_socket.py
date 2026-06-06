"""Tests for TCP server socket setup."""

import socket
import unittest
from unittest.mock import Mock, call, patch

from nmea_gps_emulator.custom_thread import run_telnet_server_thread


class TestTcpServerSocketSetup(unittest.TestCase):
    """TCP server socket setup should support quick restarts."""

    def test_reuseaddr_is_set_before_bind(self) -> None:
        """SO_REUSEADDR is enabled before binding the TCP server socket."""
        sock = Mock()
        sock.__enter__ = Mock(return_value=sock)
        sock.__exit__ = Mock(return_value=None)
        sock.accept.side_effect = KeyboardInterrupt

        with (
            patch("nmea_gps_emulator.custom_thread.socket.socket", return_value=sock),
            self.assertRaises(KeyboardInterrupt),
        ):
            run_telnet_server_thread("0.0.0.0", 3000, Mock())

        sock.setsockopt.assert_called_once_with(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind.assert_called_once_with(("0.0.0.0", 3000))
        self.assertLess(
            sock.mock_calls.index(call.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)),
            sock.mock_calls.index(call.bind(("0.0.0.0", 3000))),
        )


if __name__ == "__main__":
    unittest.main()
