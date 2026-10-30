"""Core package containing low-level socket inspection, process modeling, and signals."""

from portsnip.core.models import ProcessInfo
from portsnip.core.reader import PortScanner, find_process_by_port, list_listening_ports
from portsnip.core.signals import (
    PermissionDeniedError,
    ProcessTerminator,
    ProtectedProcessError,
    TerminationResult,
    TerminationTimeoutError,
    terminate_process,
)

__all__ = [
    "PermissionDeniedError",
    "PortScanner",
    "ProcessInfo",
    "ProcessTerminator",
    "ProtectedProcessError",
    "TerminationResult",
    "TerminationTimeoutError",
    "find_process_by_port",
    "list_listening_ports",
    "terminate_process",
]
