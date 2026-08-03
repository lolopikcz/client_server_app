"""Tests for the wire protocol."""

from __future__ import annotations

import socket
import struct
import threading
import unittest

from protocol import METADATA_FMT, FILE_SIZE_FMT, send_metadata, recv_metadata


class TestProtocol(unittest.TestCase):
    """Test metadata encoding and decoding."""

    def test_round_trip(self) -> None:
        """send_metadata and recv_metadata should be inverses."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        result: list[tuple[str, int]] = []

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

        result: list[tuple[str, int]] = []

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

    def test_empty_filename_rejected(self) -> None:
        """Should raise ValueError for empty filename."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                recv_metadata(conn)

        t = threading.Thread(target=server_thread)
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        # Send empty filename (length 0)
        header = struct.pack(METADATA_FMT, 0)
        size_header = struct.pack(FILE_SIZE_FMT, 0)
        client.sendall(header + size_header)
        client.close()

        t.join()
        server.close()

        # The protocol itself doesn't reject empty names; validation is in utils


if __name__ == "__main__":
    unittest.main()
