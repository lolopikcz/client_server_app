"""Tests for the wire protocol."""

from __future__ import annotations

import socket
import threading
import unittest
from unittest.mock import MagicMock

from protocol import (
    recv_metadata,
    recv_response,
    send_done,
    send_metadata,
    send_response,
)


class TestProtocol(unittest.TestCase):
    """Test metadata encoding and decoding."""

    def test_round_trip(self) -> None:
        """send_metadata and recv_metadata should be inverses."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        result: list[tuple[str, int] | None] = []

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                result.append(recv_metadata(conn))

        t = threading.Thread(target=server_thread)
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_metadata(client, "test.txt", 12345)
        client.close()

        t.join()
        server.close()

        self.assertEqual(result[0], ("test.txt", 12345))

    def test_unicode_filename(self) -> None:
        """Should handle unicode filenames."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        result: list[tuple[str, int] | None] = []

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                result.append(recv_metadata(conn))

        t = threading.Thread(target=server_thread)
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_metadata(client, "\u00e4\u00f6\u00fc.txt", 999)
        client.close()

        t.join()
        server.close()

        self.assertEqual(result[0], ("\u00e4\u00f6\u00fc.txt", 999))

    def test_done_signal(self) -> None:
        """recv_metadata should return None for done signal."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        result: list[tuple[str, int] | None] = []

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                result.append(recv_metadata(conn))

        t = threading.Thread(target=server_thread)
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_done(client)
        client.close()

        t.join()
        server.close()

        self.assertIsNone(result[0])

    def test_multiple_metadata_then_done(self) -> None:
        """Should receive multiple metadata then done signal."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        results: list[tuple[str, int] | None] = []

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                results.append(recv_metadata(conn))
                results.append(recv_metadata(conn))
                results.append(recv_metadata(conn))

        t = threading.Thread(target=server_thread)
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_metadata(client, "file1.txt", 100)
        send_metadata(client, "file2.txt", 200)
        send_done(client)
        client.close()

        t.join()
        server.close()

        self.assertEqual(results[0], ("file1.txt", 100))
        self.assertEqual(results[1], ("file2.txt", 200))
        self.assertIsNone(results[2])


class TestProtocolResponse(unittest.TestCase):
    """Test response encoding and decoding."""

    def test_response_round_trip(self) -> None:
        """send_response and recv_response should be inverses."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        result: list[str] = []

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                result.append(recv_response(conn))

        t = threading.Thread(target=server_thread)
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_response(client, "OK")
        client.close()

        t.join()
        server.close()

        self.assertEqual(result[0], "OK")

    def test_error_response(self) -> None:
        """Should handle error responses."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        result: list[str] = []

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                result.append(recv_response(conn))

        t = threading.Thread(target=server_thread)
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_response(client, "ERROR: file already exists")
        client.close()

        t.join()
        server.close()

        self.assertEqual(result[0], "ERROR: file already exists")

    def test_empty_response(self) -> None:
        """Empty response (length=0) should return empty string."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        result: list[str] = []

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                result.append(recv_response(conn))

        t = threading.Thread(target=server_thread)
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        import struct

        client.sendall(struct.pack("!I", 0))
        client.close()

        t.join()
        server.close()

        self.assertEqual(result[0], "")

    def test_recv_exact_connection_closed(self) -> None:
        """_recv_exact should raise ConnectionError on premature close."""
        from protocol import _recv_exact

        mock_sock = MagicMock()
        mock_sock.recv.return_value = b""

        with self.assertRaises(ConnectionError):
            _recv_exact(mock_sock, 10)


if __name__ == "__main__":
    unittest.main()
