"""Unit tests for client module."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from client import (
    _send_file_content,
    _send_single_file,
    connect,
    run_batch,
    send_files,
)
from utils import setup_logging

SAMPLE_DATA_DIR = Path(__file__).parent / "sample_data"


class TestConnect(unittest.TestCase):
    """Test client connect function."""

    @patch("client.socket.socket")
    def test_connect_success(self, mock_socket_cls: MagicMock) -> None:
        """Successful connection returns socket."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        logger = setup_logging()

        result = connect("127.0.0.1", 65432, logger)

        mock_sock.connect.assert_called_once_with(("127.0.0.1", 65432))
        self.assertEqual(result, mock_sock)

    @patch("client.socket.socket")
    def test_connect_failure(self, mock_socket_cls: MagicMock) -> None:
        """Connection refused raises ConnectionError."""
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError
        mock_socket_cls.return_value = mock_sock
        logger = setup_logging()

        with self.assertRaises(ConnectionError):
            connect("127.0.0.1", 65432, logger)

        mock_sock.close.assert_called_once()


class TestSendSingleFile(unittest.TestCase):
    """Test sending a single file."""

    def test_file_not_found(self) -> None:
        """Non-existent file should be skipped."""
        mock_sock = MagicMock()
        logger = setup_logging()
        non_existent = Path("non_existent_file.txt")

        _send_single_file(mock_sock, non_existent, logger)

        mock_sock.sendall.assert_not_called()

    def test_send_file_success(self) -> None:
        """Valid file should be sent with metadata and content."""
        mock_sock = MagicMock()
        logger = setup_logging()
        src_path = SAMPLE_DATA_DIR / "file1.txt"

        with patch("client.recv_response", return_value="OK"):
            _send_single_file(mock_sock, src_path, logger)

        self.assertTrue(mock_sock.sendall.called)

    def test_permission_error(self) -> None:
        """Permission error should be caught and printed."""
        mock_sock = MagicMock()
        logger = setup_logging()
        src_path = SAMPLE_DATA_DIR / "file1.txt"

        with patch("client.send_metadata", side_effect=PermissionError), \
             patch("builtins.print") as mock_print:
            _send_single_file(mock_sock, src_path, logger)

        mock_print.assert_any_call(f"  {src_path.name}: SKIPPED (permission denied)")

    def test_connection_error(self) -> None:
        """Connection error should be caught, printed, and re-raised."""
        mock_sock = MagicMock()
        logger = setup_logging()
        src_path = SAMPLE_DATA_DIR / "file1.txt"

        with patch("client.send_metadata", side_effect=ConnectionError("lost")), \
             patch("builtins.print") as mock_print, self.assertRaises(ConnectionError):
            _send_single_file(mock_sock, src_path, logger)

        mock_print.assert_any_call(f"  {src_path.name}: FAILED (lost)")


class TestSendFileContent(unittest.TestCase):
    """Test file content sending."""

    def test_send_content(self) -> None:
        """File content should be sent in chunks."""
        mock_sock = MagicMock()
        src_path = SAMPLE_DATA_DIR / "file1.txt"
        content = src_path.read_bytes()

        _send_file_content(mock_sock, src_path, len(content))

        mock_sock.sendall.assert_called()

    def test_permission_error_on_read(self) -> None:
        """Permission error reading file should propagate."""
        mock_sock = MagicMock()
        fake_path = Path("fake_file.bin")

        with patch("builtins.open", side_effect=PermissionError), \
             self.assertRaises(PermissionError):
            _send_file_content(mock_sock, fake_path, 100)


class TestSendFiles(unittest.TestCase):
    """Test sending multiple files."""

    def test_send_multiple_files(self) -> None:
        """Should send each file in the list."""
        mock_sock = MagicMock()
        logger = setup_logging()
        files = [SAMPLE_DATA_DIR / "file1.txt", SAMPLE_DATA_DIR / "file2.txt"]

        with patch("client._send_single_file") as mock_send:
            send_files(mock_sock, files, logger)

        self.assertEqual(mock_send.call_count, 2)


class TestRunBatch(unittest.TestCase):
    """Test batch mode."""

    def test_batch_sends_and_disconnects(self) -> None:
        """Batch should send files, done signal, and print server response."""
        mock_sock = MagicMock()
        logger = setup_logging()
        files = [SAMPLE_DATA_DIR / "file1.txt"]

        with patch("client.send_files") as mock_send_files, \
             patch("client.send_done") as mock_send_done, \
             patch("client.recv_response", return_value="GOODBYE"), \
             patch("builtins.print") as mock_print:
            run_batch(mock_sock, files, logger)

        mock_send_files.assert_called_once_with(mock_sock, files, logger)
        mock_send_done.assert_called_once_with(mock_sock)
        mock_print.assert_any_call("Server: GOODBYE")


class TestRunRepl(unittest.TestCase):
    """Test interactive REPL mode."""

    def test_repl_send_done(self) -> None:
        """REPL should exit on send_done command."""
        from client import run_repl
        mock_sock = MagicMock()
        logger = setup_logging()

        with patch("builtins.input", side_effect=["send_done"]), \
             patch("client.send_done") as mock_send_done, \
             patch("client.recv_response", return_value="GOODBYE"), \
             patch("builtins.print"):
            run_repl(mock_sock, logger)

        mock_send_done.assert_called_once_with(mock_sock)

    def test_repl_send_file(self) -> None:
        """REPL should send files when send_file command given."""
        from client import run_repl
        mock_sock = MagicMock()
        logger = setup_logging()
        src_path = SAMPLE_DATA_DIR / "file1.txt"

        with patch("builtins.input", side_effect=[f"send_file {src_path}", "send_done"]), \
             patch("client.send_files") as mock_send_files, \
             patch("client.send_done"), \
             patch("client.recv_response", return_value="GOODBYE"), \
             patch("builtins.print"):
            run_repl(mock_sock, logger)

        mock_send_files.assert_called_once()
        args = mock_send_files.call_args[0]
        self.assertEqual(args[0], mock_sock)
        self.assertEqual(len(args[1]), 1)

    def test_repl_unknown_command(self) -> None:
        """REPL should print error for unknown commands."""
        from client import run_repl
        mock_sock = MagicMock()
        logger = setup_logging()

        with patch("builtins.input", side_effect=["unknown", "send_done"]), \
             patch("client.send_done"), \
             patch("client.recv_response", return_value="GOODBYE"), \
             patch("builtins.print") as mock_print:
            run_repl(mock_sock, logger)

        mock_print.assert_any_call("  Unknown command: unknown")

    def test_repl_send_file_no_args(self) -> None:
        """REPL should print usage when send_file has no args."""
        from client import run_repl
        mock_sock = MagicMock()
        logger = setup_logging()

        with patch("builtins.input", side_effect=["send_file", "send_done"]), \
             patch("client.send_done"), \
             patch("client.recv_response", return_value="GOODBYE"), \
             patch("builtins.print") as mock_print:
            run_repl(mock_sock, logger)

        mock_print.assert_any_call("  Usage: send_file <file1> [file2] ...")

    def test_repl_empty_input(self) -> None:
        """REPL should skip empty input."""
        from client import run_repl
        mock_sock = MagicMock()
        logger = setup_logging()

        with patch("builtins.input", side_effect=["", "  ", "send_done"]), \
             patch("client.send_done"), \
             patch("client.recv_response", return_value="GOODBYE"), \
             patch("builtins.print"):
            run_repl(mock_sock, logger)

    def test_repl_eof_error(self) -> None:
        """REPL should handle EOFError gracefully."""
        from client import run_repl
        mock_sock = MagicMock()
        logger = setup_logging()

        with patch("builtins.input", side_effect=EOFError), \
             patch("client.send_done") as mock_send_done, \
             patch("client.recv_response"), \
             patch("builtins.print"):
            run_repl(mock_sock, logger)

        mock_send_done.assert_called_once_with(mock_sock)


if __name__ == "__main__":
    unittest.main()
