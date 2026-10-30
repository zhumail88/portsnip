# portsnip

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange.svg)](https://www.kernel.org/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A high-precision, low-friction Linux CLI utility to identify, inspect, and terminate orphan processes holding network ports.

---

## Table of Contents

- [The Problem](#the-problem)
- [Terminal Preview](#terminal-preview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Architecture and System Internals](#architecture-and-system-internals)
- [Development and Testing](#development-and-testing)
- [License](#license)

---

## The Problem

Every developer has encountered this:

```text
Error: listen EADDRINUSE: address already in use :::3000
```

The standard Linux resolution workflow requires chaining multiple commands:

```bash
lsof -i :3000                  # 1. Identify PID
kill -15 <PID>                 # 2. Attempt graceful kill
sleep 1 && kill -9 <PID>       # 3. Escalate if unyielding
```

`portsnip` replaces this manual pipeline with a single safe, deterministic command.

---

## Terminal Preview

```text
$ portsnip 3000

Scanning socket bindings for port 3000...

+--------------------------------------------------------------+
| Port 3000 (TCP) is currently held by:                        |
+-----------------+--------------------------------------------+
| Process Name    | node                                       |
| PID             | 41209                                      |
| User            | alex (UID: 1000)                           |
| Memory Footprint| 184.2 MB                                   |
| Runtime Command | node /home/alex/projects/api/server.js     |
+-----------------+--------------------------------------------+

? Terminate PID 41209? [y/N]: y

[OK] Dispatched SIGTERM (15)... Clean exit confirmed.
[OK] Port 3000 is now free.
```

---

## Features

- **POSIX signal safety:** Uses a tiered termination strategy. Dispatches `SIGTERM` first, monitors the process lifecycle for up to 3 seconds, and escalates to `SIGKILL` only on timeout or explicit request.
- **Kernel-level inspection:** Reads `/proc/net/tcp` and process file descriptors directly to resolve socket inodes to PIDs.
- **Accidental termination prevention:** Hardcoded safeguards prevent termination of PID 1 (init/systemd) and system-critical supervisor processes.
- **Clean fallbacks:** Provides clear elevation guidance (`sudo`) when target processes belong to other system users, rather than raw runtime tracebacks.
- **Scripting friendly:** Machine-readable output flags (`--pid-only`, `--quiet`) support integration into CI pipelines and shell aliases.

---

## Installation

### Option 1: Debian / Ubuntu Package (.deb)

Download and install the latest `.deb` release:

```bash
wget https://github.com/zhumail88/portsnip/releases/latest/download/portsnip_1.0.0-1_all.deb
sudo apt install ./portsnip_1.0.0-1_all.deb
```

### Option 2: Automated Installation Script

```bash
curl -sSL https://raw.githubusercontent.com/zhumail88/portsnip/main/scripts/install.sh | sudo bash
```

### Option 3: Install from Source (Developer Setup)

```bash
git clone https://github.com/zhumail88/portsnip.git
cd portsnip
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Usage

### Basic Port Termination

Target an occupied port. Process details are displayed and confirmation is requested:

```bash
portsnip 8080
```

### Non-Interactive / Force Kill

Bypass the confirmation prompt and terminate immediately. This is useful for shell scripts and build runners:

```bash
portsnip 8080 --force
# or short flag:
portsnip 8080 -f
```

### List All Active Listening Sockets

Scan the workstation for all listening TCP/UDP sockets and display the processes holding them:

```bash
portsnip --list
```

### Script / Automation Mode

Print only the PID bound to a port, without formatting:

```bash
PID=$(portsnip 3000 --pid-only)
echo "Target is running on PID $PID"
```

---

## Architecture and System Internals

`portsnip` does not rely on heavy shell wrappers. It inspects Linux virtual file systems directly:

1. **Socket inode resolution:** Reads `/proc/net/tcp` (and `/proc/net/tcp6`), translating network addresses from network byte-order hexadecimal to human-readable IP and port endpoints.
2. **File descriptor correlation:** Scans `/proc/[pid]/fd/*` symlinks to cross-reference socket inodes against running processes.
3. **Graceful signal loop:**

```text
Target process --> SIGTERM --> Poll /proc/<pid> (3000 ms) --> On timeout: escalate to SIGKILL
```

For an in-depth breakdown of the component hierarchy, see [system_architecture.md](system_architecture.md).

---

## Development and Testing

Run the tests and code linter locally:

```bash
# Run test suite
pytest tests/

# Run code style linter
ruff check .
```

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.