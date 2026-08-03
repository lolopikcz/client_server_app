"""Wire protocol for metadata exchange."""

from __future__ import annotations

import socket
import struct

METADATA_FMT = "!I"  # 4 bytes unsigned int for filename length
FILE_SIZE_FMT = "!Q"  # 8 bytes unsigned long long for file size


def send_metadata(sock: socket.socket, filename: str, file_size: int) -> None:
    """Send file metadata over the socket.

    Sends: filename_length (4 bytes) + filename + file_size (8 bytes).

    Args:
        sock: Connected socket.
        filename: Name of the file being sent.
        file_size: Size of the file in bytes.

    Raises:
        socket.error: If sending fails.
    """
    filename_bytes = filename.encode("utf-8")
    header = struct.pack(METADATA_FMT, len(filename_bytes))
    size_header = struct.pack(FILE_SIZE_FMT, file_size)
    sock.sendall(header + filename_bytes + size_header)


def recv_metadata(sock: socket.socket) -> tuple[str, int]:
    """Receive file metadata from the socket.

    Args:
        sock: Connected socket.

    Returns:
        Tuple of (filename, file_size).

    Raises:
        ConnectionError: If the connection is closed prematurely.
        ValueError: If received data is malformed.
    """
    raw_len = _recv_exact(sock, struct.calcsize(METADATA_FMT))
    (filename_len,) = struct.unpack(METADATA_FMT, raw_len)

    filename_bytes = _recv_exact(sock, filename_len)
    filename = filename_bytes.decode("utf-8")

    raw_size = _recv_exact(sock, struct.calcsize(FILE_SIZE_FMT))
    (file_size,) = struct.unpack(FILE_SIZE_FMT, raw_size)

    return filename, file_size


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes from the socket.

    Args:
        sock: Connected socket.
        n: Number of bytes to receive.

    Returns:
        Received bytes.

    Raises:
        ConnectionError: If the connection is closed before n bytes received.
    """
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Connection closed while receiving metadata")
        data.extend(chunk)
    return bytes(data)
