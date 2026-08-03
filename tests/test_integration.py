"""Integration tests for client-server file transfer."""

from __future__ import annotations

import socket
import tempfile
import threading
import unittest
from pathlib import Path

from config import CHUNK_SIZE
from protocol import send_metadata, send_done, recv_response
from server import _handle_client, _receive_single_file
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

    def _start_server(self) -> tuple[socket.socket, int]:
        """Start a test server, return (server_socket, port)."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        return server, port

    def test_full_transfer(self) -> None:
        """Send a file and verify it arrives correctly."""
        content = b"Hello, this is a test file content!"
        src_path = Path(self.tmpdir) / "test_input.bin"
        src_path.write_bytes(content)

        server, port = self._start_server()
        received_path: list[Path] = []

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                _handle_client(conn, self.dest_dir, self.logger)
                received_path.extend(self.dest_dir.iterdir())

        t = threading.Thread(target=server_thread)
        t.start()

        # Client side
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_metadata(client, "test_input.bin", len(content))
        client.sendall(content)
        response = recv_response(client)
        send_done(client)
        goodbye = recv_response(client)
        client.close()

        t.join()
        server.close()

        # Verify
        self.assertEqual(response, "OK")
        self.assertEqual(goodbye, "GOODBYE")
        self.assertEqual(len(received_path), 1)
        self.assertEqual(received_path[0].read_bytes(), content)

    def test_reject_existing_file(self) -> None:
        """Server should reject transfer if file already exists."""
        content = b"Duplicate file"
        existing = self.dest_dir / "existing.txt"
        existing.write_bytes(b"original")

        server, port = self._start_server()

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                _handle_client(conn, self.dest_dir, self.logger)

        t = threading.Thread(target=server_thread)
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        send_metadata(client, "existing.txt", len(content))
        client.sendall(content)
        response = recv_response(client)
        send_done(client)
        client.close()

        t.join()
        server.close()

        # Should get error response
        self.assertIn("ERROR", response)
        # Original file should be untouched
        self.assertEqual(existing.read_bytes(), b"original")

    def test_multi_file_transfer(self) -> None:
        """Send multiple files in one connection."""
        files = {
            "file1.txt": b"Content of file 1",
            "file2.txt": b"Content of file 2",
            "file3.jpg": b"Binary content for image",
        }

        server, port = self._start_server()
        received: dict[str, bytes] = {}

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                _handle_client(conn, self.dest_dir, self.logger)
                for f in self.dest_dir.iterdir():
                    received[f.name] = f.read_bytes()

        t = threading.Thread(target=server_thread)
        t.start()

        # Client side
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))

        responses = []
        for filename, content in files.items():
            send_metadata(client, filename, len(content))
            client.sendall(content)
            responses.append(recv_response(client))

        send_done(client)
        goodbye = recv_response(client)
        client.close()

        t.join()
        server.close()

        # Verify
        self.assertEqual(responses, ["OK", "OK", "OK"])
        self.assertEqual(goodbye, "GOODBYE")
        self.assertEqual(received, files)

    def test_mixed_valid_and_invalid(self) -> None:
        """Send valid and invalid files in same connection."""
        server, port = self._start_server()
        received: dict[str, bytes] = {}

        # Pre-create a file that will cause duplicate error
        (self.dest_dir / "existing.txt").write_bytes(b"original")

        def server_thread() -> None:
            conn, _ = server.accept()
            with conn:
                _handle_client(conn, self.dest_dir, self.logger)
                for f in self.dest_dir.iterdir():
                    received[f.name] = f.read_bytes()

        t = threading.Thread(target=server_thread)
        t.start()

        # Client side
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))

        # Send new file (should succeed)
        send_metadata(client, "new.txt", 5)
        client.sendall(b"hello")
        r1 = recv_response(client)

        # Send duplicate file (should fail)
        send_metadata(client, "existing.txt", 5)
        client.sendall(b"world")
        r2 = recv_response(client)

        # Send another new file (should succeed)
        send_metadata(client, "another.txt", 4)
        client.sendall(b"test")
        r3 = recv_response(client)

        send_done(client)
        client.close()

        t.join()
        server.close()

        # Verify
        self.assertEqual(r1, "OK")
        self.assertIn("ERROR", r2)
        self.assertEqual(r3, "OK")
        self.assertIn("new.txt", received)
        self.assertIn("another.txt", received)
        # existing.txt should still be original
        self.assertEqual(received["existing.txt"], b"original")


if __name__ == "__main__":
    unittest.main()
