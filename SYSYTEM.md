# portsnip: System Architecture Specification

## 1. High-Level Overview

`portsnip` is a specialized Linux CLI utility that bridges the gap between network socket allocation and process execution. It removes the multi-command friction of `lsof` or `ss` combined with `kill` by resolving local sockets to their owning process in user space, presenting process context, and performing graceful or forced termination via POSIX signals.

```text
+-------------------------------------------------------------+
|                        CLI Entrypoint                       |
|             (Argparse / Typer / Rich Terminal)              |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                    Port / Socket Engine                     |
|  - Parse target port (TCP/UDP)                              |
|  - Read /proc/net/tcp and /proc/net/tcp6                    |
|  - Extract socket inode                                     |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                 Process Resolution Engine                   |
|  - Scan /proc/[pid]/fd/* for matching inode                 |
|  - Parse /proc/[pid]/status (Name, UID, Memory)             |
|  - Parse /proc/[pid]/cmdline (executable and arguments)     |
|  - Fallback: psutil abstraction layer                       |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                      Signal Dispatcher                      |
|  - Check current user permissions (UID match / root)        |
|  - Stage 1: send SIGTERM (15), poll for up to 3 seconds     |
|  - Stage 2: escalate to SIGKILL (9) if process persists     |
+-------------------------------------------------------------+
```

---

## 2. Low-Level Linux Subsystem Mechanics

### 2.1 Socket-to-PID Resolution via `/proc`

Unlike utilities that invoke external binaries, `portsnip` reads Linux pseudo-filesystems directly when permissions allow.

1. **Inode discovery (`/proc/net/tcp` and `/proc/net/tcp6`)**
   - Fields parsed: `local_address` (hexadecimal `IP:PORT`) and `inode`.
   - Ports are stored as hexadecimal values and converted to decimal. For example, `0x0BB8` converts to `3000`.
2. **File descriptor inspection (`/proc/<pid>/fd/`)**
   - Sockets appear as symbolic links pointing to `socket:[<inode>]`.
   - `portsnip` iterates over accessible numeric directories in `/proc/` and reads link targets with `readlink()`.
3. **Process metadata acquisition**
   - `/proc/<pid>/cmdline`: command-line arguments delimited by null bytes (`\0`).
   - `/proc/<pid>/status`: `Name`, `State`, `VmRSS` (memory footprint), and `Uid`.

### 2.2 Privilege Separation and Permissions

- **Non-root limitations:** An unprivileged user can only read file descriptor links for processes they own.
- **Privilege detection:** If the target process UID differs from the current runtime UID, `portsnip` detects the permission barrier before sending any signal. It then prompts for elevation (`sudo`) with a clear diagnostic instead of failing with an unhandled `PermissionError` (POSIX `EPERM`).

---

## 3. Signal Dispatching Strategy

Terminating a process without data loss requires disciplined signal sequencing.

```text
[Target process identified]
          |
          v
   Send SIGTERM (15)
          |
          v
   Poll /proc/<pid> every 300 ms, up to 3000 ms
          |
          +--> Process exited? --> [SUCCESS]
          |
          v
   Process still alive after timeout?
          |
          v
   Prompt user for SIGKILL (9) --> Send SIGKILL --> Process evicted
```

- **`SIGTERM` (15):** Requests that the application release sockets, flush buffers, and terminate gracefully.
- **`SIGKILL` (9):** Immediate kernel-level termination. It cannot be caught or ignored by the process.

---

## 4. Component Structure

- **`portsnip/core/scanner.py`:** Reads `/proc` or `psutil` to map ports to PIDs.
- **`portsnip/core/process.py`:** Model object representing a running target (PID, command, user, memory, socket information).
- **`portsnip/core/terminator.py`:** Handles POSIX signal dispatch, graceful timeouts, and error handling.
- **`portsnip/ui/cli.py`:** Handles input parsing, tabular rendering, error reporting, and confirmation prompts.