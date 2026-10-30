"""Low-level socket discovery and process resolution for Linux."""

from __future__ import annotations

import os
import pwd
import socket
import struct

from portsnip.core.models import ProcessInfo

# Linux TCP states (from /include/net/tcp_states.h)
TCP_ESTABLISHED = "01"
TCP_SYN_SENT = "02"
TCP_SYN_RECV = "03"
TCP_FIN_WAIT1 = "04"
TCP_FIN_WAIT2 = "05"
TCP_TIME_WAIT = "06"
TCP_CLOSE = "07"
TCP_CLOSE_WAIT = "08"
TCP_LAST_ACK = "09"
TCP_LISTEN = "0A"
TCP_CLOSING = "0B"

# Map of pseudo-files in /proc/net to (protocol, expected_listening_states)
PROC_NET_FILES = [
    ("/proc/net/tcp", "TCP", {TCP_LISTEN}),
    ("/proc/net/tcp6", "TCP", {TCP_LISTEN}),
    ("/proc/net/udp", "UDP", {TCP_CLOSE}),  # Bound UDP sockets use state 07
    ("/proc/net/udp6", "UDP", {TCP_CLOSE}),
]


def decode_ipv4_hex(hex_ip: str) -> str:
    """Decode an 8-character little-endian hexadecimal IPv4 address into dotted decimal."""
    try:
        raw = struct.pack("<I", int(hex_ip, 16))
        return socket.inet_ntoa(raw)
    except (ValueError, struct.error, OSError):
        return hex_ip


def decode_ipv6_hex(hex_ip: str) -> str:
    """Decode a 32-character hexadecimal IPv6 address into standard representation."""
    try:
        words = [int(hex_ip[i : i + 8], 16) for i in range(0, 32, 8)]
        raw = struct.pack("<4I", *words)
        return socket.inet_ntop(socket.AF_INET6, raw)
    except (ValueError, struct.error, OSError):
        return hex_ip


def decode_address(raw_addr: str) -> tuple[str, int]:
    """Parse a Linux /proc/net address string (e.g. '0100007F:0BB8').

    Returns:
        (ip_address, port)
    """
    if ":" not in raw_addr:
        return ("0.0.0.0", 0)
    hex_ip, hex_port = raw_addr.split(":", 1)
    port = int(hex_port, 16)

    if len(hex_ip) == 8:
        ip = decode_ipv4_hex(hex_ip)
    elif len(hex_ip) == 32:
        ip = decode_ipv6_hex(hex_ip)
    else:
        ip = hex_ip

    return ip, port


def parse_proc_net_file(file_path: str, valid_states: set[str]) -> list[dict]:
    """Parse a single /proc/net/ socket file.

    Returns a list of dicts with:
    {'protocol': ..., 'local_ip': ..., 'port': ..., 'uid': ..., 'inode': ..., 'state': ...}
    """
    results = []
    if not os.path.exists(file_path):
        return results

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, PermissionError):
        return results

    # Skip header line
    for line in lines[1:]:
        parts = line.strip().split()
        if len(parts) < 10:
            continue

        raw_local = parts[1]
        state = parts[3]
        uid_str = parts[7]
        inode_str = parts[9]

        if valid_states and state not in valid_states:
            continue

        try:
            ip, port = decode_address(raw_local)
            uid = int(uid_str)
            inode = int(inode_str)
        except ValueError:
            continue

        results.append(
            {
                "local_ip": ip,
                "port": port,
                "state": "LISTEN" if state == TCP_LISTEN else "BOUND",
                "uid": uid,
                "inode": inode,
            }
        )

    return results


def build_inode_to_pid_map() -> dict[int, int]:
    """Traverse /proc/[pid]/fd/* to map socket inodes to process IDs."""
    inode_to_pid: dict[int, int] = {}
    proc_dir = "/proc"

    if not os.path.exists(proc_dir):
        return inode_to_pid

    try:
        entries = os.listdir(proc_dir)
    except (OSError, PermissionError):
        return inode_to_pid

    for entry in entries:
        if not entry.isdigit():
            continue

        pid = int(entry)
        fd_dir = os.path.join(proc_dir, entry, "fd")

        try:
            fd_list = os.listdir(fd_dir)
        except (OSError, PermissionError, ProcessLookupError):
            # Process may have exited or belong to another unreadable user
            continue

        for fd in fd_list:
            fd_path = os.path.join(fd_dir, fd)
            try:
                target = os.readlink(fd_path)
            except (OSError, PermissionError, ProcessLookupError):
                continue

            # Socket symlinks typically look like 'socket:[12345]'
            if target.startswith("socket:[") and target.endswith("]"):
                try:
                    inode = int(target[8:-1])
                    inode_to_pid[inode] = pid
                except ValueError:
                    pass

    return inode_to_pid


def get_process_info_from_proc(
    pid: int,
    port: int,
    protocol: str = "TCP",
    uid: int | None = None,
    inode: int = 0,
    local_address: str = "0.0.0.0",
    state: str = "LISTEN",
) -> ProcessInfo | None:
    """Read process details directly from /proc/<pid>/status and /proc/<pid>/cmdline."""
    pid_dir = f"/proc/{pid}"
    if not os.path.exists(pid_dir):
        return None

    name = "unknown"
    cmdline = ""
    resolved_uid = uid if uid is not None else 1000
    memory_mb = 0.0

    # Parse /proc/<pid>/status
    status_path = os.path.join(pid_dir, "status")
    try:
        with open(status_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("Name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("Uid:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        resolved_uid = int(parts[1])
                elif line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            memory_mb = float(parts[1]) / 1024.0
                        except ValueError:
                            pass
    except (OSError, PermissionError, ProcessLookupError):
        pass

    # Parse /proc/<pid>/cmdline
    cmdline_path = os.path.join(pid_dir, "cmdline")
    try:
        with open(cmdline_path, "r", encoding="utf-8", errors="replace") as f:
            raw_cmd = f.read()
            cmdline = raw_cmd.replace("\0", " ").strip()
    except (OSError, PermissionError, ProcessLookupError):
        pass

    if not cmdline:
        cmdline = f"[{name}]"

    # Resolve username
    try:
        user = pwd.getpwuid(resolved_uid).pw_name
    except (KeyError, ValueError):
        user = str(resolved_uid)

    return ProcessInfo(
        pid=pid,
        name=name,
        cmdline=cmdline,
        user=user,
        memory_mb=memory_mb,
        port=port,
        protocol=protocol,
        uid=resolved_uid,
        inode=inode,
        state=state,
        local_address=local_address,
    )


def scan_via_proc(target_port: int | None = None) -> list[ProcessInfo]:
    """Scan sockets and processes using Linux /proc filesystem."""
    results: list[ProcessInfo] = []
    inode_to_pid = build_inode_to_pid_map()

    # Collect socket entries from /proc/net
    all_sockets = []
    for file_path, proto, valid_states in PROC_NET_FILES:
        sockets = parse_proc_net_file(file_path, valid_states)
        for s in sockets:
            s["protocol"] = proto
            all_sockets.append(s)

    # Filter if target_port specified
    if target_port is not None:
        all_sockets = [s for s in all_sockets if s["port"] == target_port]

    seen_pids = set()

    for sock in all_sockets:
        inode = sock["inode"]
        port = sock["port"]
        proto = sock["protocol"]
        sock_uid = sock["uid"]
        local_addr = sock["local_ip"]
        state = sock["state"]

        pid = inode_to_pid.get(inode)

        if pid is not None:
            if pid in seen_pids and target_port is None:
                # Avoid duplicate entries for same process on multiple sockets if listing
                pass
            info = get_process_info_from_proc(
                pid=pid,
                port=port,
                protocol=proto,
                uid=sock_uid,
                inode=inode,
                local_address=local_addr,
                state=state,
            )
            if info:
                seen_pids.add(pid)
                results.append(info)
        else:
            # PID is unknown (possibly owned by root or another user we cannot inspect)
            try:
                user = pwd.getpwuid(sock_uid).pw_name
            except (KeyError, ValueError):
                user = str(sock_uid)

            results.append(
                ProcessInfo(
                    pid=None,
                    name="unknown",
                    cmdline="unknown",
                    user=user,
                    memory_mb=0.0,
                    port=port,
                    protocol=proto,
                    uid=sock_uid,
                    inode=inode,
                    state=state,
                    local_address=local_addr,
                )
            )

    return results


def scan_via_psutil(target_port: int | None = None) -> list[ProcessInfo]:
    """Fallback scanner using the psutil library."""
    try:
        import psutil
    except ImportError:
        return []

    results: list[ProcessInfo] = []
    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, PermissionError, OSError):
        connections = []

    seen = set()

    for conn in connections:
        if conn.status != psutil.CONN_LISTEN and conn.type != socket.SOCK_DGRAM:
            continue

        if not conn.laddr:
            continue

        port = conn.laddr.port
        if target_port is not None and port != target_port:
            continue

        protocol = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"
        local_ip = conn.laddr.ip
        pid = conn.pid

        key = (pid, port, protocol)
        if key in seen:
            continue
        seen.add(key)

        if pid is not None:
            try:
                proc = psutil.Process(pid)
                name = proc.name()
                cmdline = " ".join(proc.cmdline()) or f"[{name}]"
                user = proc.username()
                uid = proc.uids().real if hasattr(proc, "uids") else os.getuid()
                memory_mb = proc.memory_info().rss / (1024.0 * 1024.0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                name = "unknown"
                cmdline = "unknown"
                user = "unknown"
                uid = 0
                memory_mb = 0.0

            results.append(
                ProcessInfo(
                    pid=pid,
                    name=name,
                    cmdline=cmdline,
                    user=user,
                    memory_mb=memory_mb,
                    port=port,
                    protocol=protocol,
                    uid=uid,
                    state="LISTEN",
                    local_address=local_ip,
                )
            )
        else:
            results.append(
                ProcessInfo(
                    pid=None,
                    name="unknown",
                    cmdline="unknown",
                    user="unknown",
                    memory_mb=0.0,
                    port=port,
                    protocol=protocol,
                    uid=0,
                    state="LISTEN",
                    local_address=local_ip,
                )
            )

    return results


class PortScanner:
    """Combines direct Linux /proc inspection with a psutil fallback."""

    def __init__(self, use_proc: bool = True, use_psutil_fallback: bool = True):
        self.use_proc = use_proc
        self.use_psutil_fallback = use_psutil_fallback

    def find_by_port(self, port: int) -> ProcessInfo | None:
        """Find the process listening on a given port."""
        if self.use_proc and os.path.exists("/proc/net"):
            candidates = scan_via_proc(target_port=port)
            # Prefer a candidate that has resolved PID
            for item in candidates:
                if item.pid is not None:
                    return item
            if candidates:
                # If only PID=None candidates exist, check psutil before giving up on PID
                if self.use_psutil_fallback:
                    psutil_results = scan_via_psutil(target_port=port)
                    for p_item in psutil_results:
                        if p_item.pid is not None:
                            return p_item
                return candidates[0]

        if self.use_psutil_fallback:
            candidates = scan_via_psutil(target_port=port)
            if candidates:
                return candidates[0]

        return None

    def list_all(self) -> list[ProcessInfo]:
        """List all processes holding listening sockets."""
        items: list[ProcessInfo] = []
        if self.use_proc and os.path.exists("/proc/net"):
            items = scan_via_proc(target_port=None)

        if not items and self.use_psutil_fallback:
            items = scan_via_psutil(target_port=None)
        elif self.use_psutil_fallback:
            # If some items in proc had PID=None, enrich them with psutil if psutil has permission
            psutil_items = {
                (p.port, p.protocol): p
                for p in scan_via_psutil(target_port=None)
                if p.pid is not None
            }
            enriched = []
            for it in items:
                if it.pid is None and (it.port, it.protocol) in psutil_items:
                    enriched.append(psutil_items[(it.port, it.protocol)])
                else:
                    enriched.append(it)
            items = enriched

        # Sort by port number ascending
        items.sort(key=lambda x: (x.port, x.protocol))
        return items


def find_process_by_port(port: int) -> ProcessInfo | None:
    """Convenience helper to find process holding port."""
    scanner = PortScanner()
    return scanner.find_by_port(port)


def list_listening_ports() -> list[ProcessInfo]:
    """Convenience helper to list all listening processes."""
    scanner = PortScanner()
    return scanner.list_all()
