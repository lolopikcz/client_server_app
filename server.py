"""File transfer server."""

from __future__ import annotations

import logging
import socket
from pathlib import Path

from config import CHUNK_SIZE, parse_server_args
from protocol import recv_metadata, send_response
from utils import setup_logging, validate_filename


def start_server(host: str, port: int, dest_dir: Path, log_mode: str = "append") -> None:
    """Start the file transfer server.

    Listens for client connections, receives files, and saves them to the
    destination directory. Runs until interrupted with Ctrl+C.

    Args:
        host: Host address to bind to.
        port: Port number to listen on.
        dest_dir: Directory to save received files.
        log_mode: 'append' to keep old logs, 'overwrite' to clear on start.

    Raises:
        OSError: If the server socket cannot be created or bound.
    """
    logger = setup_logging(log_mode=log_mode, name="server")
    dest_dir.mkdir(parents=True, exist_ok=True)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        # Enables quick server restarts without "Address already in use" errors.
        # TCP keeps ports in TIME_WAIT for ~60-120s after closing; this bypasses
        # that wait. Acceptable here (localhost, dev tool) but not recommended
        # for production — a malicious process could bind the port in that window.
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((host, port))
        logger.info("Server started on %s:%d", host, port)
        logger.info("Waiting for incoming connection...")
        server_sock.listen(1)

        try:
            while True:
                conn, addr = server_sock.accept()
                with conn:
                    logger.info("Accepted connection from %s", addr[0])
                    _handle_client(conn, dest_dir, logger)
                    logger.info("Client disconnected")
                    logger.info("Waiting for incoming connection...")
        except KeyboardInterrupt:
            logger.info("Server shutting down")


def _handle_client(conn: socket.socket, dest_dir: Path, logger: logging.Logger) -> None:
    """Handle a connected client, receiving multiple files.

    Loops receiving files until the client sends a done signal.

    Args:
        conn: Connected client socket.
        dest_dir: Directory to save received files.
        logger: Logger instance.
    """
    try:
        while True:
            result = recv_metadata(conn)
            if result is None:
                send_response(conn, "GOODBYE")
                logger.info("Done signal received")
                break

            filename, file_size = result
            response = _receive_single_file(conn, filename, file_size, dest_dir, logger)
            send_response(conn, response)
    except ConnectionError as exc:
        logger.error("Connection interrupted: %s", exc)
    except Exception:
        logger.exception("Unexpected error")


def _receive_single_file(
    conn: socket.socket,
    filename: str,
    file_size: int,
    dest_dir: Path,
    logger: logging.Logger,
) -> str:
    """Receive a single file from the client.

    Args:
        conn: Connected client socket.
        filename: Name of the file being sent.
        file_size: Size of the file in bytes.
        dest_dir: Directory to save the file.
        logger: Logger instance.

    Returns:
        Response message: 'OK' on success, 'ERROR: ...' on failure.
    """
    try:
        safe_name = validate_filename(filename)
    except ValueError as exc:
        logger.warning("Invalid filename: %s", exc)
        _drain_content(conn, file_size)
        return f"ERROR: {exc}"

    dest_path = dest_dir / safe_name

    if dest_path.exists():
        logger.warning("File already exists: %s", safe_name)
        _drain_content(conn, file_size)
        return f"ERROR: file already exists: {safe_name}"

    logger.info("Receiving file: %s (%d bytes)", safe_name, file_size)

    received = 0
    with open(dest_path, "wb") as f:
        while received < file_size:
            chunk = conn.recv(CHUNK_SIZE)
            if not chunk:
                f.close()
                dest_path.unlink(missing_ok=True)
                return "ERROR: client disconnected during transfer"
            f.write(chunk)
            received += len(chunk)

    logger.info("Saved: %s", dest_path)
    return "OK"


def _drain_content(conn: socket.socket, file_size: int) -> None:
    """Read and discard file content to keep protocol in sync.

    Args:
        conn: Connected client socket.
        file_size: Number of bytes to drain.
    """
    received = 0
    while received < file_size:
        chunk = conn.recv(CHUNK_SIZE)
        if not chunk:
            break
        received += len(chunk)


def main() -> None:
    """Entry point for the server."""
    args = parse_server_args()
    start_server(args.host, args.port, args.dest_dir, args.log_mode)


if __name__ == "__main__":
    main()
