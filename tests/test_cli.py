"""Unit tests for command line parsing and interface behavior."""

import io
import unittest
from unittest.mock import patch

from portsnip.cli import create_parser, format_process_box, main
from portsnip.core.models import ProcessInfo


class TestCLI(unittest.TestCase):
    def test_parser_arguments(self):
        parser = create_parser()

        args = parser.parse_args(["3000"])
        self.assertEqual(args.port, 3000)
        self.assertFalse(args.force)
        self.assertFalse(args.list)

        args = parser.parse_args(["--list"])
        self.assertTrue(args.list)
        self.assertIsNone(args.port)

        args = parser.parse_args(["8080", "-f", "--pid-only", "-q"])
        self.assertEqual(args.port, 8080)
        self.assertTrue(args.force)
        self.assertTrue(args.pid_only)
        self.assertTrue(args.quiet)

    def test_invalid_port_range(self):
        # Port > 65535 should return exit code 2
        with patch("sys.stderr", new_callable=io.StringIO):
            code = main(["70000"])
            self.assertEqual(code, 2)

        # Port < 1 should return exit code 2
        with patch("sys.stderr", new_callable=io.StringIO):
            code = main(["0"])
            self.assertEqual(code, 2)

    def test_format_process_box(self):
        proc = ProcessInfo(
            pid=41209,
            name="node",
            cmdline="node /home/alex/projects/api/server.js",
            user="alex",
            memory_mb=184.2,
            port=3000,
            protocol="TCP",
            uid=1000,
        )
        box = format_process_box(proc)
        self.assertIn("Port 3000 (TCP) is currently held by:", box)
        self.assertIn("Process Name", box)
        self.assertIn("node", box)
        self.assertIn("41209", box)
        self.assertIn("alex (UID: 1000)", box)
        self.assertIn("184.2 MB", box)

    @patch("portsnip.core.reader.PortScanner.find_by_port")
    def test_pid_only_output(self, mock_find):
        proc = ProcessInfo(
            pid=41209,
            name="node",
            cmdline="node server.js",
            user="alex",
            memory_mb=184.2,
            port=3000,
            protocol="TCP",
            uid=1000,
        )
        mock_find.return_value = proc

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["3000", "--pid-only"])
            self.assertEqual(code, 0)
            self.assertEqual(mock_out.getvalue().strip(), "41209")

    @patch("portsnip.core.reader.PortScanner.find_by_port")
    def test_port_not_found(self, mock_find):
        mock_find.return_value = None

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["3000", "-q"])
            self.assertEqual(code, 0)
            self.assertEqual(mock_out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
