# Client-Server File Transfer Application

[![CI](https://github.com/lolopikcz/client_server_app/actions/workflows/ci.yml/badge.svg)](https://github.com/lolopikcz/client_server_app/actions/workflows/ci.yml)

A TCP client-server application for transferring files in Python, with support for multiple files per connection and an interactive REPL.

## Features

- Multi-file transfer per connection
- Interactive REPL mode for sending files on-the-fly
- Server responses (OK/ERROR) after each file
- Upload progress display
- File existence check (no overwrites)
- Filename validation with adversarial security tests
- Rotating file logs for debugging
- Configurable host, port, destination directory, and log mode

## Project Structure

```
client_server_app/
├── .github/workflows/
│   └── ci.yml             # CI: lint (ruff), typecheck (mypy), test (pytest)
├── .pre-commit-config.yaml # Pre-commit hooks (ruff, formatting)
├── pyproject.toml         # Project metadata, deps, tool config
├── client.py              # Client (batch + interactive REPL)
├── server.py              # Server (multi-file, persistent)
├── protocol.py            # Wire protocol (metadata, responses, done signal)
├── config.py              # Argparse configuration
├── utils.py               # Validation and logging
├── .gitignore
├── logs/                  # Rotating log files (gitignored)
└── tests/
    ├── sample_data/       # Test fixture files
    ├── test_client.py     # Client unit tests
    ├── test_server.py     # Server unit tests
    ├── test_integration.py
    ├── test_protocol.py
    └── test_utils.py
```

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

### Start the server

```bash
python server.py
```

With options:

```bash
python server.py --host 127.0.0.1 --port 65432 --dest-dir received --log-mode append
```

### Batch mode (send multiple files at once)

```bash
python client.py --file file1.txt file2.txt file3.jpg
```

### Interactive REPL mode

```bash
python client.py
```

Then type commands:

```
> send_file file1.txt file2.txt
  Uploading... [##################################] 100%
  Waiting for server...
  file1.txt: OK
  file2.txt: OK
> send_done
Server: GOODBYE
```

### Run tests

```bash
python -m pytest tests/ -v
```

Tests include coverage reporting. Coverage threshold is enforced at 80%.

## CI/CD

GitHub Actions runs on push/PR to `main`:

| Job | Tool | What it checks |
|-----|------|----------------|
| lint | ruff | Style, formatting, import order |
| typecheck | mypy | Static type errors |
| test | pytest | Unit + integration tests across Python 3.11/3.12/3.13 |

## Protocol

### Message types

| Sender | Message | Format |
|--------|---------|--------|
| Client | File metadata | `filename_length` (4B) + `filename` (UTF-8) + `file_size` (8B) |
| Client | File content | Raw bytes in 65536-byte chunks |
| Client | Done signal | `filename_length = 0` (4B) |
| Server | Response | `msg_length` (4B) + `message` (UTF-8, e.g. `OK`, `ERROR: ...`, `GOODBYE`) |

### Transfer flow

```
Client                              Server
  │                                   │
  ├─ connect ────────────────────────►│
  │                                   │
  ├─ metadata (file1.txt, 1024B) ───►│
  ├─ file content (1024 bytes) ─────►│
  │◄── "OK" ─────────────────────────┤
  │                                   │
  ├─ metadata (file2.jpg, 9999B) ───►│
  ├─ file content (9999 bytes) ─────►│
  │◄── "OK" ─────────────────────────┤
  │                                   │
  ├─ done signal (length=0) ────────►│
  │◄── "GOODBYE" ────────────────────┤
  ├─ disconnect ─────────────────────►│
  │                                   ├─ back to accept()
```

### Server queue behavior

If a second client connects while the first is active, it waits in the TCP backlog queue until the server accepts the connection.

### Filename validation

Rejected filenames:
- Path traversal (`../`, `..\`)
- Null bytes
- Reserved Windows names (`CON`, `NUL`, `COM1`, etc.)
- Filenames over 255 bytes
- Characters outside `[\w\-. ]`

## Future Improvements

- Async implementation using asyncio (concurrent client handling)
- TLS encryption
- Authentication
- File integrity verification (SHA-256)
- Resume interrupted transfers
- Compression
- Audit test suite: review edge cases, remove redundant mocks, and improve coverage of error paths
