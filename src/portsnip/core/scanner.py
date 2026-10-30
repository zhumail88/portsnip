"""Compatibility alias for reader.py as referenced in architecture specification."""

from portsnip.core.reader import (
    PortScanner,
    build_inode_to_pid_map,
    find_process_by_port,
    get_process_info_from_proc,
    list_listening_ports,
    parse_proc_net_file,
    scan_via_proc,
    scan_via_psutil,
)

__all__ = [
    "PortScanner",
    "build_inode_to_pid_map",
    "find_process_by_port",
    "get_process_info_from_proc",
    "list_listening_ports",
    "parse_proc_net_file",
    "scan_via_proc",
    "scan_via_psutil",
]
