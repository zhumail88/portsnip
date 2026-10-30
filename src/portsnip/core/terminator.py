"""Compatibility alias for signals.py as referenced in architecture specification."""

from portsnip.core.signals import (
    PermissionDeniedError,
    PortsnipError,
    ProcessNotFoundError,
    ProcessTerminator,
    ProtectedProcessError,
    TerminationResult,
    TerminationTimeoutError,
    check_safety_guards,
    is_process_alive,
    poll_process_exit,
    send_kill,
    send_term,
    terminate_process,
)

__all__ = [
    "PortsnipError",
    "ProtectedProcessError",
    "PermissionDeniedError",
    "ProcessNotFoundError",
    "TerminationTimeoutError",
    "TerminationResult",
    "ProcessTerminator",
    "is_process_alive",
    "check_safety_guards",
    "send_term",
    "send_kill",
    "poll_process_exit",
    "terminate_process",
]
