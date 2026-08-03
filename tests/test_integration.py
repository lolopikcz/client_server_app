"""Integration tests for client-server file transfer."""

from __future__ import annotations

import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from config import CHUNK_SIZE
from protocol import send_metadata, recv_metadata
from server import _receive_file
from utils import setup_logging


class TestIntegration(unittest.TestCase):
    """Test end-to-end file transfer."""

    def setUp(self) -> None:
        """Create temporary directories for testing."""
        self.tmpdir = tempfile.mkdtemp()
        self.dest_dir = Path(self.tmpdir) / "received"
        self.dest_dir.mkdir()
        self.logger = setup_logging()

    def tearDown(self) -> None:
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_full_transfer(self) -> None:
        """Send a file and verify it arrives correctly."""
        content = b"Hello, this is a test file content!"
        src_path = Path(self.tmpdir) / "test_input.bin"
        src_path.write_bytes(content)

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        received_path: list[Path] = []

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                _receive_file(conn, self.dest_dir, self.logger)
                received_path.append(list(self.dest_dir.iterdir())[0])

        t = threading.Thread(target=server_thread)
        t.start()

        # Client side
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_metadata(client, "test_input.bin", len(content))

        sent = 0
        with open(src_path, "rb") as f:
            while sent < len(content):
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                client.sendall(chunk)
                sent += len(chunk)

        client.close()
        t.join()
        server.close()

        # Verify
        self.assertEqual(len(received_path), 1)
        self.assertEqual(received_path[0].read_bytes(), content)

    def test_reject_existing_file(self) -> None:
        """Server should reject transfer if file already exists."""
        content = b"Duplicate file"
        existing = self.dest_dir / "existing.txt"
        existing.write_bytes(b"original")

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                # This should raise ValueError because file exists
                with self.assertRaises(ValueError):
                    _receive_file(conn, self.dest_dir, self.logger)

        t = threading.Thread(target=server_thread)
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_metadata(client, "existing.txt", len(content))
        client.sendall(content)
        client.close()

        t.join()
        server.close()

        # Original file should be untouched
        self.assertEqual(existing.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
