"""Unit tests for process termination, safety gates, and signal escalation."""

import os
import subprocess
import sys
import time
import unittest

from portsnip.core.signals import (
    PermissionDeniedError,
    ProcessTerminator,
    ProtectedProcessError,
    check_safety_guards,
    is_process_alive,
    send_kill,
    send_term,
    terminate_process,
)


class TestSignals(unittest.TestCase):
    def test_protected_pids(self):
        """Must reject PID <= 10."""
        for protected_pid in [1, 2, 5, 10]:
            with self.assertRaises(ProtectedProcessError):
                check_safety_guards(protected_pid)

    def test_uid_mismatch_check(self):
        """Must reject foreign UID when not running as root."""
        current_uid = os.getuid()
        if current_uid != 0:
            foreign_uid = current_uid + 1
            with self.assertRaises(PermissionDeniedError):
                check_safety_guards(pid=99999, owner_uid=foreign_uid, owner_name="someone")

    def test_is_process_alive(self):
        # Current process is alive
        self.assertTrue(is_process_alive(os.getpid()))

        # Non-existent large PID should not be alive
        self.assertFalse(is_process_alive(4194304))

    def test_graceful_termination_sigterm(self):
        """Start a normal subprocess and ensure it cleanly terminates on SIGTERM."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertTrue(is_process_alive(proc.pid))

        try:
            res = terminate_process(proc.pid, force=False)
            self.assertTrue(res.success)
            self.assertEqual(res.signal_sent, 15)
            self.assertFalse(res.escalated)
            self.assertFalse(is_process_alive(proc.pid))
        finally:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            if is_process_alive(proc.pid):
                proc.kill()
            proc.wait()

    def test_escalation_to_sigkill_on_force(self):
        """Start a subprocess that ignores SIGTERM and verify escalation to SIGKILL."""
        # Subprocess ignores SIGTERM (signal 15)
        ignore_code = """
import signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
print('IGNORING', flush=True)
while True:
    time.sleep(0.5)
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", ignore_code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            ready = proc.stdout.readline()
            self.assertEqual(ready.strip(), "IGNORING")

            # Terminate with short timeout to speed up test
            terminator = ProcessTerminator(timeout=0.3, poll_interval=0.05)
            res = terminator.terminate(proc.pid, force=True)

            self.assertTrue(res.success)
            self.assertEqual(res.signal_sent, 9)
            self.assertTrue(res.escalated)
            self.assertFalse(is_process_alive(proc.pid))
        finally:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            if is_process_alive(proc.pid):
                proc.kill()
            proc.wait()


if __name__ == "__main__":
    unittest.main()
