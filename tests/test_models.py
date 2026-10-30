"""Unit tests for ProcessInfo data model."""

import unittest
from portsnip.core.models import ProcessInfo


class TestProcessInfo(unittest.TestCase):
    def test_process_info_instantiation(self):
        info = ProcessInfo(
            pid=1234,
            name="node",
            cmdline="node server.js",
            user="alex",
            memory_mb=128.5,
            port=3000,
            protocol="TCP",
            uid=1000,
            state="LISTEN",
            local_address="127.0.0.1",
        )
        self.assertEqual(info.pid, 1234)
        self.assertEqual(info.name, "node")
        self.assertEqual(info.port, 3000)
        self.assertEqual(info.formatted_user, "alex (UID: 1000)")
        self.assertEqual(info.formatted_memory, "128.5 MB")

    def test_process_info_optional_pid(self):
        info = ProcessInfo(
            pid=None,
            name="root_daemon",
            cmdline="daemon",
            user="root",
            memory_mb=0.0,
            port=80,
            protocol="TCP",
            uid=0,
        )
        self.assertIsNone(info.pid)
        self.assertEqual(info.formatted_user, "root (UID: 0)")


if __name__ == "__main__":
    unittest.main()
