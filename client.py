"""File transfer client."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

from config import CHUNK_SIZE, parse_client_args
from protocol import send_metadata
from utils import setup_logging


def send_file(host: str, port: int, file_path: Path) -> None:
    """Send a file to the server.

    Connects to the server, sends file metadata and content in chunks,
    and displays upload progress.

    Args:
        host: Server host address.
        port: Server port number.
        file_path: Path to the file to send.

    Raises:
        FileNotFoundError: If the input file does not exist.
        ConnectionError: If the connection to the server fails.
        PermissionError: If the file cannot be read.
    """
    logger = setup_logging()

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = file_path.stat().st_size
    filename = file_path.name

    logger.info("Connecting to %s:%d...", host, port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.connect((host, port))
        except ConnectionRefusedError:
            raise ConnectionError(f"Cannot connect to {host}:{port}")

        logger.info("Connected. Sending file: %s (%d bytes)", filename, file_size)
        send_metadata(sock, filename, file_size)

        _send_file_content(sock, file_path, file_size, logger)

    logger.info("Upload complete")


def _send_file_content(
    sock: socket.socket,
    file_path: Path,
    file_size: int,
    logger: object,
) -> None:
    """Send file content in chunks with progress display.

    Args:
        sock: Connected socket.
        file_path: Path to the file to send.
        file_size: Total size of the file in bytes.
        logger: Logger instance.

    Raises:
        ConnectionError: If the connection drops during transfer.
        PermissionError: If the file cannot be read.
    """
    sent = 0
    try:
        with open(file_path, "rb") as f:
            while sent < file_size:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                sock.sendall(chunk)
                sent += len(chunk)
                _print_progress(sent, file_size)
    except PermissionError:
        raise PermissionError(f"Cannot read file: {file_path}")

    print()  # newline after progress bar


def _print_progress(sent: int, total: int) -> None:
    """Print a progress bar to stdout.

    Args:
        sent: Bytes sent so far.
        total: Total bytes to send.
    """
    if total == 0:
        return
    percent = sent / total * 100
    bar_len = 30
    filled = int(bar_len * sent / total)
    bar = "#" * filled + "-" * (bar_len - filled)
    sys.stdout.write(f"\rUploading... [{bar}] {percent:.0f}%")
    sys.stdout.flush()


def main() -> None:
    """Entry point for the client."""
    args = parse_client_args()
    send_file(args.host, args.port, args.file)


if __name__ == "__main__":
    main()
