"""Configuration module for client and server."""

from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 65432
DEFAULT_DEST_DIR = Path("received")
CHUNK_SIZE = 65536
LOG_MODES = ("append", "overwrite")


def parse_server_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the server.

    Args:
        argv: Optional list of arguments to parse. Defaults to sys.argv.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="File transfer server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    parser.add_argument(
        "--dest-dir",
        type=Path,
        default=DEFAULT_DEST_DIR,
        help="Directory to store received files",
    )
    parser.add_argument(
        "--log-mode",
        choices=LOG_MODES,
        default="append",
        help="Log file mode: append (keep old) or overwrite (default: append)",
    )
    return parser.parse_args(argv)


def parse_client_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the client.

    Args:
        argv: Optional list of arguments to parse. Defaults to sys.argv.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="File transfer client")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Server host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Server port")
    parser.add_argument("--file", type=Path, nargs="+", help="Files to send (batch mode, omit for interactive REPL)")
    parser.add_argument(
        "--log-mode",
        choices=LOG_MODES,
        default="append",
        help="Log file mode: append (keep old) or overwrite (default: append)",
    )
    return parser.parse_args(argv)
