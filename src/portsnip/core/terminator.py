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
    "PermissionDeniedError",
    "PortsnipError",
    "ProcessNotFoundError",
    "ProcessTerminator",
    "ProtectedProcessError",
    "TerminationResult",
    "TerminationTimeoutError",
    "check_safety_guards",
    "is_process_alive",
    "poll_process_exit",
    "send_kill",
    "send_term",
    "terminate_process",
]
