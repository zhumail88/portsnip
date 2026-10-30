"""Unit tests for low-level socket reader and process scanner."""

import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from portsnip.core.reader import (
    PortScanner,
    decode_address,
    decode_ipv4_hex,
    decode_ipv6_hex,
    parse_proc_net_file,
)


class TestReader(unittest.TestCase):
    def test_decode_ipv4_hex(self):
        # 0100007F is 127.0.0.1 in Linux little-endian hex representation
        ip = decode_ipv4_hex("0100007F")
        self.assertEqual(ip, "127.0.0.1")

        # 00000000 is 0.0.0.0
        ip_zero = decode_ipv4_hex("00000000")
        self.assertEqual(ip_zero, "0.0.0.0")

    def test_decode_ipv6_hex(self):
        # Loopback ::1 in Linux /proc/net/tcp6 hex
        hex_ip = "00000000000000000000000001000000"
        ip = decode_ipv6_hex(hex_ip)
        self.assertEqual(ip, "::1")

    def test_decode_address(self):
        # 127.0.0.1:3000 (3000 = 0x0BB8)
        ip, port = decode_address("0100007F:0BB8")
        self.assertEqual(ip, "127.0.0.1")
        self.assertEqual(port, 3000)

    def test_parse_proc_net_file(self):
        # Mock /proc/net/tcp content
        content = (
            "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
            "   0: 0100007F:1F90 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 54321 1\n"
            "   1: 0100007F:0050 00000000:0000 01 00000000:00000000 00:00000000 00000000     0        0 99999 1\n"
        )
        with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # We filter for 0A (TCP_LISTEN)
            sockets = parse_proc_net_file(tmp_path, {"0A"})
            self.assertEqual(len(sockets), 1)
            sock = sockets[0]
            self.assertEqual(sock["port"], 8080)  # 0x1F90 is 8080
            self.assertEqual(sock["local_ip"], "127.0.0.1")
            self.assertEqual(sock["inode"], 54321)
            self.assertEqual(sock["uid"], 1000)
            self.assertEqual(sock["state"], "LISTEN")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_ephemeral_socket_server_detection(self):
        """Task 1.4: Start ephemeral socket server and verify detection."""
        # Find an available random port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        _, port = sock.getsockname()
        sock.close()

        # Launch an ephemeral Python socket server subprocess
        server_code = f"""
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('127.0.0.1', {port}))
s.listen(1)
print('READY', flush=True)
while True:
    time.sleep(0.5)
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", server_code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Wait for server to indicate READY
            ready_line = proc.stdout.readline()
            self.assertEqual(ready_line.strip(), "READY")

            # Allow /proc/net/tcp to register
            time.sleep(0.1)

            # Detect with reader
            scanner = PortScanner()
            info = scanner.find_by_port(port)

            self.assertIsNotNone(info, f"Failed to detect server listening on port {port}")
            self.assertEqual(info.port, port)
            self.assertEqual(info.pid, proc.pid)
            self.assertEqual(info.protocol, "TCP")
        finally:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            proc.terminate()
            proc.wait()


if __name__ == "__main__":
    unittest.main()
