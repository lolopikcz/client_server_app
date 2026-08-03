"""File transfer client."""

from __future__ import annotations

import logging
import socket
from enum import Enum
from pathlib import Path

from tqdm import tqdm

from config import CHUNK_SIZE, parse_client_args
from protocol import recv_response, send_done, send_metadata
from utils import setup_logging


class FileTransferResult(Enum):
    """Result of a single file transfer attempt."""

    SUCCESS = "success"
    REJECTED = "rejected"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "denied"
    FAILED = "failed"


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
    except (ConnectionRefusedError, OSError) as exc:
        sock.close()
        raise ConnectionError(f"Cannot connect to {host}:{port}") from exc
    logger.info("Connected")
    return sock


def send_files(sock: socket.socket, files: list[Path], logger: logging.Logger) -> list[FileTransferResult]:
    """Send multiple files to the server.

    Args:
        sock: Connected socket.
        files: List of file paths to send.
        logger: Logger instance.

    Returns:
        List of FileTransferResult, one per file.
    """
    results = []
    for file_path in files:
        result = _send_single_file(sock, file_path, logger)
        results.append(result)
    return results


def _send_single_file(
    sock: socket.socket, file_path: Path, logger: logging.Logger
) -> FileTransferResult:
    """Send a single file and return the result.

    Args:
        sock: Connected socket.
        file_path: Path to the file to send.
        logger: Logger instance.

    Returns:
        FileTransferResult indicating outcome.
    """
    if not file_path.exists():
        logger.warning("%s: skipped (file not found)", file_path.name)
        return FileTransferResult.NOT_FOUND

    file_size = file_path.stat().st_size
    logger.debug("Sending file: %s (%d bytes)", file_path.name, file_size)

    try:
        send_metadata(sock, file_path.name, file_size)
        _send_file_content(sock, file_path, file_size)
        logger.info("Waiting for server response...")
        response = recv_response(sock)
        logger.info("%s: %s", file_path.name, response)
        if response.startswith("ERROR"):
            return FileTransferResult.REJECTED
        return FileTransferResult.SUCCESS
    except PermissionError:
        logger.warning("%s: skipped (permission denied)", file_path.name)
        return FileTransferResult.PERMISSION_DENIED
    except ConnectionError as exc:
        logger.error("%s: failed (%s)", file_path.name, exc)
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
    try:
        with open(file_path, "rb") as f, \
             tqdm(total=file_size, unit="B", unit_scale=True, desc=file_path.name) as pbar:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                sock.sendall(chunk)
                pbar.update(len(chunk))
    except PermissionError:
        raise PermissionError(f"Cannot read file: {file_path}")


def run_batch(sock: socket.socket, files: list[Path], logger: logging.Logger) -> str:
    """Send files in batch mode, then disconnect.

    Args:
        sock: Connected socket.
        files: List of file paths to send.
        logger: Logger instance.

    Returns:
        Server's final response (e.g., 'GOODBYE').
    """
    send_files(sock, files, logger)
    send_done(sock)
    response = recv_response(sock)
    logger.info("Server: %s", response)
    return response


def run_repl(sock: socket.socket, logger: logging.Logger) -> None:
    """Run interactive REPL for sending files.

    Args:
        sock: Connected socket.
        logger: Logger instance.
    """
    logger.info("Connected. Commands:")
    logger.info("  send_file <file1> [file2] ...  - Send files")
    logger.info("  send_done                      - Disconnect and exit")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            send_done(sock)
            recv_response(sock)
            break

        if not line:
            continue

        if line == "send_done":
            send_done(sock)
            try:
                response = recv_response(sock)
                logger.info("Server: %s", response)
            except ConnectionError:
                logger.warning("Server disconnected")
            break

        if line.startswith("send_file"):
            parts = line.split()

            if len(parts) < 2:
                logger.info("Usage: send_file <file1> [file2] ...")
                continue

            files = [Path(p) for p in parts[1:]]
            send_files(sock, files, logger)
        else:
            logger.warning("Unknown command: %s", line)
            logger.info("Available: send_file, send_done")


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
