"""Data models for processes and network sockets."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProcessInfo:
    """Represents a running process holding a network socket.

    Attributes:
        pid: The process ID (None if inaccessible due to privilege barrier).
        name: Short name of the process executable.
        cmdline: Full command line invocation with arguments.
        user: The username of the process owner.
        memory_mb: Resident memory footprint in megabytes (RSS).
        port: The local network port held by the process.
        protocol: Socket protocol ('TCP' or 'UDP').
        uid: User ID of the process owner.
        inode: Socket inode number.
        state: Socket connection state (e.g. 'LISTEN').
        local_address: Formatted local IP address (e.g. '127.0.0.1' or '0.0.0.0').
    """

    pid: Optional[int]
    name: str
    cmdline: str
    user: str
    memory_mb: float
    port: int
    protocol: str = "TCP"
    uid: int = 1000
    inode: int = 0
    state: str = "LISTEN"
    local_address: str = "0.0.0.0"

    @property
    def formatted_user(self) -> str:
        """Return formatted user with UID."""
        return f"{self.user} (UID: {self.uid})"

    @property
    def formatted_memory(self) -> str:
        """Return human-readable memory string."""
        return f"{self.memory_mb:.1f} MB"
