"""Unit tests for server error paths."""

from __future__ import annotations

import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from protocol import send_done
from server import _drain_content, _handle_client, _receive_single_file
from utils import setup_logging

SAMPLE_DATA_DIR = Path(__file__).parent / "sample_data"


def _start_test_server() -> tuple[socket.socket, int]:
    """Create a test server socket bound to a random port."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    port = server.getsockname()[1]
    return server, port


class TestDrainContent(unittest.TestCase):
    """Test _drain_content function."""

    def test_drain_exact_amount(self) -> None:
        """Should drain exactly file_size bytes."""
        mock_conn = MagicMock()
        mock_conn.recv.return_value = b"hello"

        _drain_content(mock_conn, 5)

        mock_conn.recv.assert_called()

    def test_drain_client_disconnects(self) -> None:
        """Should handle client disconnect during drain."""
        mock_conn = MagicMock()
        mock_conn.recv.return_value = b""

        _drain_content(mock_conn, 100)

        mock_conn.recv.assert_called()


class TestReceiveSingleFile(unittest.TestCase):
    """Test _receive_single_file function."""

    def setUp(self) -> None:
        """Create temporary directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.dest_dir = Path(self.tmpdir) / "received"
        self.dest_dir.mkdir()
        self.logger = setup_logging()

    def tearDown(self) -> None:
        """Clean up."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_invalid_filename(self) -> None:
        """Invalid filename should return error and drain content."""
        mock_conn = MagicMock()
        mock_conn.recv.return_value = b"x" * 10

        response = _receive_single_file(mock_conn, "../evil.txt", 10, self.dest_dir, self.logger)

        self.assertIn("ERROR", response)

    def test_existing_file(self) -> None:
        """Existing file should return error and drain content."""
        mock_conn = MagicMock()
        existing = self.dest_dir / "existing.txt"
        existing.write_bytes(b"original")
        mock_conn.recv.return_value = b"x" * 10

        response = _receive_single_file(mock_conn, "existing.txt", 10, self.dest_dir, self.logger)

        self.assertIn("ERROR", response)
        self.assertEqual(existing.read_bytes(), b"original")

    def test_client_disconnects_during_transfer(self) -> None:
        """Client disconnect during transfer should return error."""
        mock_conn = MagicMock()
        mock_conn.recv.return_value = b""

        response = _receive_single_file(mock_conn, "new.txt", 100, self.dest_dir, self.logger)

        self.assertIn("ERROR", response)

    def test_partial_file_cleaned_up_on_disconnect(self) -> None:
        """Partial file should be deleted if client disconnects mid-transfer."""
        mock_conn = MagicMock()
        mock_conn.recv.side_effect = [b"partial data", b""]

        response = _receive_single_file(mock_conn, "new.txt", 100, self.dest_dir, self.logger)

        self.assertIn("ERROR", response)
        self.assertFalse((self.dest_dir / "new.txt").exists())

    def test_successful_receive(self) -> None:
        """Valid file should be received and saved."""
        mock_conn = MagicMock()
        content = b"hello world"
        mock_conn.recv.return_value = content

        response = _receive_single_file(mock_conn, "new.txt", len(content), self.dest_dir, self.logger)

        self.assertEqual(response, "OK")
        saved = self.dest_dir / "new.txt"
        self.assertTrue(saved.exists())
        self.assertEqual(saved.read_bytes(), content)


class TestHandleClient(unittest.TestCase):
    """Test _handle_client function."""

    def setUp(self) -> None:
        """Create temporary directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.dest_dir = Path(self.tmpdir) / "received"
        self.dest_dir.mkdir()
        self.logger = setup_logging()

    def tearDown(self) -> None:
        """Clean up."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_done_signal_sends_goodbye(self) -> None:
        """Done signal should trigger GOODBYE response."""
        server, port = _start_test_server()

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                _handle_client(conn, self.dest_dir, self.logger)

        t = threading.Thread(target=server_thread)
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_done(client)
        goodbye = recv_response(client)
        client.close()

        t.join()
        server.close()

        self.assertEqual(goodbye, "GOODBYE")

    def test_connection_error_handled(self) -> None:
        """Connection error should be caught without crashing."""
        mock_conn = MagicMock()
        mock_conn.recv.side_effect = ConnectionError("lost")

        _handle_client(mock_conn, self.dest_dir, self.logger)

    def test_unexpected_exception_handled(self) -> None:
        """Unexpected exception should be caught without crashing."""
        mock_conn = MagicMock()
        mock_conn.recv.side_effect = RuntimeError("unexpected")

        _handle_client(mock_conn, self.dest_dir, self.logger)


def recv_response(sock: socket.socket) -> str:
    """Receive a text response from the server."""
    raw_len = sock.recv(4)
    (msg_len,) = struct.unpack("!I", raw_len)
    data = sock.recv(msg_len)
    return data.decode("utf-8")


if __name__ == "__main__":
    unittest.main()
