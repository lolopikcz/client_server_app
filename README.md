# Client-Server File Transfer Application

A simple TCP client-server application for transferring files in Python.

## Features

- Configurable host, port, and destination directory
- Chunked file transfer (4096 bytes per chunk)
- Upload progress display
- File existence check (no overwrites)
- Structured logging
- Type hints and docstrings

## Project Structure

```
client_server_app/
├── client.py          # File transfer client
├── server.py          # File transfer server
├── protocol.py        # Wire protocol (metadata exchange)
├── config.py          # Configuration and argument parsing
├── utils.py           # Validation and logging utilities
├── requirements.txt   # Dependencies
├── received/          # Default directory for received files
├── sample_data/       # Sample files for testing
└── tests/             # Unit and integration tests
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Start the server

```bash
python server.py --host 127.0.0.1 --port 65432 --dest-dir received
```

### Send a file

```bash
python client.py --host 127.0.0.1 --port 65432 --file path/to/file.txt
```

### Run tests

```bash
python -m pytest tests/ -v
```

## Protocol

The wire protocol is simple and deterministic:

1. Client sends `filename_length` (4 bytes, unsigned int)
2. Client sends `filename` (UTF-8 encoded)
3. Client sends `file_size` (8 bytes, unsigned long long)
4. Client sends `file_content` in 4096-byte chunks

## Future Improvements

- Multiple simultaneous clients
- TLS encryption
- Authentication
- File integrity verification (SHA-256)
- Resume interrupted transfers
- Compression
- GUI
- Async implementation using asyncio
