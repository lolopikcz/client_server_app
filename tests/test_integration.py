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

SAMPLE_DATA_DIR = Path(__file__).parent / "sample_data"


def _start_test_server() -> tuple[socket.socket, int]:
    """Create a test server socket bound to a random port.

    Returns:
        Tuple of (server_socket, port).
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    port = server.getsockname()[1]
    return server, port


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
        src_path = SAMPLE_DATA_DIR / "file1.txt"
        content = src_path.read_bytes()

        server, port = _start_test_server()
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
        send_metadata(client, src_path.name, len(content))
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

        server, port = _start_test_server()

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
            "file1.txt": (SAMPLE_DATA_DIR / "file1.txt").read_bytes(),
            "file2.txt": (SAMPLE_DATA_DIR / "file2.txt").read_bytes(),
            "binary.bin": (SAMPLE_DATA_DIR / "binary.bin").read_bytes(),
        }

        server, port = _start_test_server()
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
        server, port = _start_test_server()
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

    def test_sequential_clients(self) -> None:
        """Server should handle multiple clients one after another."""
        server, port = _start_test_server()
        received: dict[str, bytes] = {}
        client_count = 0
        clients_done = threading.Event()

        def server_thread() -> None:
            nonlocal client_count
            while client_count < 3:
                conn, _ = server.accept()
                with conn:
                    _handle_client(conn, self.dest_dir, self.logger)
                    client_count += 1
            clients_done.set()

        t = threading.Thread(target=server_thread)
        t.start()

        def client_work(name: str, filename: str, content: bytes) -> None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", port))
            send_metadata(sock, filename, len(content))
            sock.sendall(content)
            self.assertEqual(recv_response(sock), "OK")
            send_done(sock)
            self.assertEqual(recv_response(sock), "GOODBYE")
            sock.close()

        # Client 1
        client_work("client1", "client1.txt", b"from one")
        # Client 2
        client_work("client2", "client2.txt", b"from two")
        # Client 3
        client_work("client3", "client3.txt", b"from three")

        clients_done.wait(timeout=5)
        t.join(timeout=5)
        server.close()

        # Collect received files
        for f in self.dest_dir.iterdir():
            received[f.name] = f.read_bytes()

        # Verify all 3 files arrived
        self.assertEqual(client_count, 3)
        self.assertEqual(len(received), 3)
        self.assertEqual(received["client1.txt"], b"from one")
        self.assertEqual(received["client2.txt"], b"from two")
        self.assertEqual(received["client3.txt"], b"from three")


if __name__ == "__main__":
    unittest.main()
