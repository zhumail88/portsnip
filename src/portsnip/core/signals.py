"""POSIX process signaling, termination lifecycle, and safety boundaries."""

from __future__ import annotations

import os
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass

PROTECTED_PID_THRESHOLD = 10


class PortsnipError(Exception):
    """Base exception for all portsnip errors."""


class ProtectedProcessError(PortsnipError):
    """Raised when an attempt is made to terminate a protected kernel/init process."""


class PermissionDeniedError(PortsnipError):
    """Raised when the user lacks permissions to signal the target process."""


class ProcessNotFoundError(PortsnipError):
    """Raised when the target process does not exist."""


class TerminationTimeoutError(PortsnipError):
    """Raised when a process does not terminate within the expected duration."""


@dataclass
class TerminationResult:
    """Outcome of a process termination request."""

    pid: int
    success: bool
    signal_sent: int
    escalated: bool
    message: str


def is_process_alive(pid: int) -> bool:
    """Check if a process exists and is actively running.

    Returns False if process does not exist or is in zombie state.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists, though we might not have kill privileges
        return True

    # Check for zombie state in /proc/<pid>/status
    status_path = f"/proc/{pid}/status"
    if os.path.exists(status_path):
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("State:"):
                        # 'Z (zombie)' means the process has exited and is awaiting reaping
                        if "Z" in line.split(":", 1)[1]:
                            return False
                        break
        except (OSError, PermissionError):
            pass

    return True


def check_safety_guards(
    pid: int, owner_uid: int | None = None, owner_name: str | None = None
) -> None:
    """Verify that the target PID is safe and permitted to be terminated.

    Raises:
        ProtectedProcessError: If PID is <= 10.
        PermissionDeniedError: If running unprivileged and target is owned by another user.
    """
    if pid <= PROTECTED_PID_THRESHOLD:
        raise ProtectedProcessError(
            f"Refusing to terminate PID {pid}: protected kernel/system initialization process."
        )

    current_uid = os.getuid()
    if current_uid != 0 and owner_uid is not None and owner_uid != current_uid:
        user_desc = owner_name if owner_name else f"UID {owner_uid}"
        raise PermissionDeniedError(f"Unable to terminate PID {pid} (owned by {user_desc}).")


def send_term(pid: int) -> bool:
    """Dispatch SIGTERM (15) to request graceful process exit."""
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False
    except PermissionError as e:
        raise PermissionDeniedError(f"Permission denied when sending SIGTERM to PID {pid}.") from e


def send_kill(pid: int) -> bool:
    """Dispatch SIGKILL (9) for forced kernel-level process termination."""
    try:
        os.kill(pid, signal.SIGKILL)
        return True
    except ProcessLookupError:
        return False
    except PermissionError as e:
        raise PermissionDeniedError(f"Permission denied when sending SIGKILL to PID {pid}.") from e


def poll_process_exit(pid: int, timeout_sec: float = 3.0, poll_interval: float = 0.1) -> bool:
    """Poll every poll_interval seconds until process exits or timeout expires.

    Returns True if process exited, False if still alive after timeout.
    """
    end_time = time.monotonic() + timeout_sec
    while time.monotonic() < end_time:
        if not is_process_alive(pid):
            return True
        time.sleep(poll_interval)
    return not is_process_alive(pid)


class ProcessTerminator:
    """Manages the tiered termination lifecycle for target processes."""

    def __init__(
        self,
        timeout: float = 3.0,
        poll_interval: float = 0.1,
    ):
        self.timeout = timeout
        self.poll_interval = poll_interval

    def terminate(
        self,
        pid: int,
        force: bool = False,
        owner_uid: int | None = None,
        owner_name: str | None = None,
        escalate_prompt: Callable[[], bool] | None = None,
    ) -> TerminationResult:
        """Execute the tiered termination sequence.

        1. Validate safety boundaries (PID <= 10 and UID check).
        2. Send SIGTERM (15).
        3. Poll for up to timeout seconds.
        4. If alive:
           - If force=True, escalate immediately to SIGKILL (9).
           - Else if escalate_prompt provided and accepted, dispatch SIGKILL (9).
           - Otherwise raise TerminationTimeoutError.
        """
        check_safety_guards(pid, owner_uid=owner_uid, owner_name=owner_name)

        if not is_process_alive(pid):
            return TerminationResult(
                pid=pid,
                success=True,
                signal_sent=0,
                escalated=False,
                message="Process already terminated.",
            )

        # Stage 1: Graceful SIGTERM
        send_term(pid)
        exited = poll_process_exit(pid, timeout_sec=self.timeout, poll_interval=self.poll_interval)

        if exited:
            return TerminationResult(
                pid=pid,
                success=True,
                signal_sent=signal.SIGTERM,
                escalated=False,
                message="Clean exit confirmed.",
            )

        # Stage 2: Escalation to SIGKILL
        should_escalate = force
        if not should_escalate and escalate_prompt is not None:
            should_escalate = escalate_prompt()

        if should_escalate:
            send_kill(pid)
            # Brief poll to ensure kernel eviction
            kill_exited = poll_process_exit(pid, timeout_sec=1.0, poll_interval=self.poll_interval)
            if kill_exited:
                return TerminationResult(
                    pid=pid,
                    success=True,
                    signal_sent=signal.SIGKILL,
                    escalated=True,
                    message="Process evicted via SIGKILL.",
                )
            else:
                raise TerminationTimeoutError(
                    f"Process {pid} persisted even after SIGKILL (uninterruptible state)."
                )

        raise TerminationTimeoutError(f"Process {pid} did not exit after SIGTERM (15).")


def terminate_process(
    pid: int,
    force: bool = False,
    owner_uid: int | None = None,
    owner_name: str | None = None,
    escalate_prompt: Callable[[], bool] | None = None,
) -> TerminationResult:
    """Convenience helper to terminate a process."""
    terminator = ProcessTerminator()
    return terminator.terminate(
        pid=pid,
        force=force,
        owner_uid=owner_uid,
        owner_name=owner_name,
        escalate_prompt=escalate_prompt,
    )
