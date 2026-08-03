# Client-Server File Transfer Application
Author: Martin Hlavoň

## Goal

Implement a simple client-server application in Python.

The client connects to the server and transfers a file.

The server receives the file and stores it in a configured directory.

The application should demonstrate clean architecture, maintainability, error handling and good software engineering practices rather than simply satisfying the minimum requirements.

---

# Requirements

## Server

- Configurable host
- Configurable port
- Configurable destination directory
- Wait for incoming connections
- Accept one client
- Receive file
- Save file into destination directory
- Never overwrite an existing file
- Use NumPy style docstrings

## Client

- Configurable server address
- Configurable port
- Accept input file path
- Display upload progress
- Use Google style docstrings

---

# Non-functional goals

- Readable code
- Modular architecture
- Type hints
- Logging
- Proper exception handling
- Small but professional GitHub repository
- Easy to extend

---

# Proposed Project Structure

```
client_server_app/

│
├── README.md
├── requirements.txt
│
├── client.py
├── server.py
├── protocol.py
├── config.py
├── utils.py
│
├── received/
│
├── sample_data/
│
└── tests/
```

---

# Development Plan

## Step 1 — Design communication protocol

The protocol should be simple and deterministic.

Client sends:

```
filename_length (4 bytes)

↓

filename

↓

file_size (8 bytes)

↓

file_content
```

The server always knows what to expect next.

---

## Step 2 — Configuration

Use argparse.

Server:

- host
- port
- destination directory

Client:

- host
- port
- input file

---

## Step 3 — Implement Server

Responsibilities:

- create listening socket
- accept client
- receive metadata
- validate filename
- check if file exists
- receive bytes
- write file
- close connection

---

## Step 4 — Implement Client

Responsibilities:

- validate input file
- connect to server
- send metadata
- send file in chunks
- display upload progress
- close connection

---

## Step 5 — Progress reporting

While sending:

```
Uploading...

███████░░░░░░░░░

42 %
```

Possible implementation:

- tqdm
- manual progress calculation

---

## Step 6 — Error handling

Client

- file not found
- cannot connect
- permission denied
- connection lost

Server

- invalid protocol
- client disconnect
- write failure
- destination directory missing

---

## Step 7 — Logging

Use Python logging module.

Examples:

INFO

```
Server started.
```

```
Accepted connection from 127.0.0.1
```

```
Receiving file...
```

WARNING

```
File already exists.
```

ERROR

```
Connection interrupted.
```

---

## Step 8 — Tests

Possible unit tests:

- protocol encoding
- protocol decoding
- filename validation
- utility functions

---

# Implementation Details

## File Transfer

Transfer in chunks.

Recommended chunk size:

```
4096 bytes
```

Advantages:

- lower memory usage
- works with large files
- progress calculation

---

## Existing files

If file already exists:

Reject transfer.

Reason:

The assignment explicitly states that existing files must not be overwritten.

---

## Type hints

Use type hints everywhere.

Example:

```python
def receive_file(sock: socket.socket) -> Path:
```

---

## Documentation

Client:

Google docstrings

Server:

NumPy docstrings

---

# Future Improvements

These are intentionally **not implemented**, but demonstrate awareness during the interview.

- Multiple simultaneous clients
- TLS encryption
- Authentication
- File integrity verification (SHA-256)
- Resume interrupted transfers
- Compression
- GUI
- IPv6 support
- Async implementation using asyncio

---

# Questions to Prepare For

## Why TCP instead of UDP?

Reliable delivery.

Ordered packets.

Suitable for file transfer.

---

## Why chunk the file?

Avoid loading the entire file into memory.

Support very large files.

Enable progress reporting.

---

## Why send metadata first?

The server needs to know:

- filename
- expected file size

before receiving the data.

---

## Why argparse?

Simple configuration.

No code changes required to run on another machine.

---

## Why logging instead of print?

Better debugging.

Configurable log levels.

Production-ready.

---

# Time Estimate

Planning

30–60 min

Protocol implementation

30 min

Server

1–2 h

Client

1–2 h

Progress reporting

30 min

Error handling

1 h

Testing

1–2 h

Documentation

1 h

README

1 h

Total

~8–10 hours

---

# Success Criteria

The application should:

- satisfy every assignment requirement
- be easy to understand
- be easy to extend
- demonstrate good engineering practices
- be something I can confidently discuss during the interview