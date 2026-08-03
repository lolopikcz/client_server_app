"""File transfer client."""

from __future__ import annotations

import logging
import shlex
import socket
import sys
from pathlib import Path

from config import CHUNK_SIZE, parse_client_args
from protocol import recv_response, send_done, send_metadata
from utils import setup_logging


def connect(host: str, port: int, logger: logging.Logger) -> socket.socket:
    """Connect to the server.

    Args:
        host: Server host address.
        port: Server port number.
        logger: Logger instance.

    Returns:
        Connected socket.

    Raises:
        ConnectionError: If connection fails.
    """
    logger.info("Connecting to %s:%d...", host, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
    except ConnectionRefusedError:
        sock.close()
        raise ConnectionError(f"Cannot connect to {host}:{port}")
    logger.info("Connected")
    return sock


def send_files(sock: socket.socket, files: list[Path], logger: logging.Logger) -> None:
    """Send multiple files to the server.

    Args:
        sock: Connected socket.
        files: List of file paths to send.
        logger: Logger instance.
    """
    for file_path in files:
        _send_single_file(sock, file_path, logger)


def _send_single_file(
    sock: socket.socket, file_path: Path, logger: logging.Logger
) -> None:
    """Send a single file and print the server response.

    Args:
        sock: Connected socket.
        file_path: Path to the file to send.
        logger: Logger instance.
    """
    if not file_path.exists():
        print(f"  {file_path.name}: SKIPPED (file not found)")
        return

    file_size = file_path.stat().st_size
    logger.debug("Sending file: %s (%d bytes)", file_path.name, file_size)

    try:
        send_metadata(sock, file_path.name, file_size)
        _send_file_content(sock, file_path, file_size)
        response = recv_response(sock)
        print(f"  {file_path.name}: {response}")
    except PermissionError:
        print(f"  {file_path.name}: SKIPPED (permission denied)")
    except ConnectionError as exc:
        print(f"  {file_path.name}: FAILED ({exc})")
        raise


def _send_file_content(
    sock: socket.socket,
    file_path: Path,
    file_size: int,
) -> None:
    """Send file content in chunks with progress display.

    Args:
        sock: Connected socket.
        file_path: Path to the file to send.
        file_size: Total size of the file in bytes.

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


def run_batch(sock: socket.socket, files: list[Path], logger: logging.Logger) -> None:
    """Send files in batch mode, then disconnect.

    Args:
        sock: Connected socket.
        files: List of file paths to send.
        logger: Logger instance.
    """
    send_files(sock, files, logger)
    send_done(sock)
    response = recv_response(sock)
    print(f"Server: {response}")


def run_repl(sock: socket.socket, logger: logging.Logger) -> None:
    """Run interactive REPL for sending files.

    Args:
        sock: Connected socket.
        logger: Logger instance.
    """
    print("Connected. Commands:")
    print("  send_file <file1> [file2] ...  - Send files")
    print("  send_done                      - Disconnect and exit")
    print()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            send_done(sock)
            recv_response(sock)
            break

        if not line:
            continue

        if line == "send_done":
            send_done(sock)
            response = recv_response(sock)
            print(f"Server: {response}")
            break

        if line.startswith("send_file"):
            try:
                parts = shlex.split(line)
            except ValueError as exc:
                print(f"  Parse error: {exc}")
                continue

            if len(parts) < 2:
                print("  Usage: send_file <file1> [file2] ...")
                continue

            files = [Path(p) for p in parts[1:]]
            send_files(sock, files, logger)
        else:
            print(f"  Unknown command: {line}")
            print("  Available: send_file, send_done")


def main() -> None:
    """Entry point for the client."""
    args = parse_client_args()
    logger = setup_logging(log_mode=args.log_mode)
    sock = connect(args.host, args.port, logger)

    try:
        if args.file:
            run_batch(sock, args.file, logger)
        else:
            run_repl(sock, logger)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
