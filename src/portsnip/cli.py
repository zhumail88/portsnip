"""Command line interface for portsnip."""

from __future__ import annotations

import argparse
import os
import sys

from portsnip import __version__


def create_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="portsnip",
        description="Instant port and process terminator for Linux developers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  portsnip 3000                 Inspect and terminate process holding port 3000
  portsnip 8080 --force         Terminate process on port 8080 without confirmation
  portsnip --list               List all active listening local ports
  portsnip 3000 --pid-only      Print only the PID bound to port 3000
""",
    )

    parser.add_argument(
        "port",
        nargs="?",
        type=int,
        help="Local network port to inspect or terminate (1-65535)",
    )

    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all active listening ports and their associated processes",
    )

    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Bypass interactive confirmation prompt and escalate to SIGKILL if necessary",
    )

    parser.add_argument(
        "--pid-only",
        action="store_true",
        help="Output only the target PID without formatting (scripting mode)",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress informational messages and disable ANSI colors",
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def format_process_box(proc) -> str:
    """Format process details matching the terminal preview."""
    header = f"Port {proc.port} ({proc.protocol}) is currently held by:"
    col1_w = 17
    total_w = 64
    col2_w = total_w - col1_w - 3

    # Truncate cmdline if extremely long
    cmd = proc.cmdline
    if len(cmd) > col2_w - 1:
        cmd = cmd[: col2_w - 4] + "..."

    lines = [
        "+" + "-" * (total_w - 2) + "+",
        f"| {header:<{total_w - 4}} |",
        "+" + "-" * col1_w + "+" + "-" * (total_w - col1_w - 3) + "+",
        f"| {'Process Name':<{col1_w - 1}} | {proc.name:<{col2_w}} |",
        f"| {'PID':<{col1_w - 1}} | {proc.pid!s:<{col2_w}} |",
        f"| {'User':<{col1_w - 1}} | {proc.formatted_user:<{col2_w}} |",
        f"| {'Memory Footprint':<{col1_w - 1}} | {proc.formatted_memory:<{col2_w}} |",
        f"| {'Runtime Command':<{col1_w - 1}} | {cmd:<{col2_w}} |",
        "+" + "-" * col1_w + "+" + "-" * (total_w - col1_w - 3) + "+",
    ]
    return "\n".join(lines)


def render_list(processes: list, quiet: bool = False) -> None:
    """Render list of active listening sockets."""
    if not processes:
        if not quiet:
            print("[INFO] No active listening sockets found.")
        return

    # Try rich rendering if available and not quiet
    if not quiet and sys.stdout.isatty():
        try:
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(title="Active Listening Sockets", title_justify="left")
            table.add_column("Port", style="cyan", justify="right")
            table.add_column("Proto", style="magenta")
            table.add_column("PID", style="green", justify="right")
            table.add_column("Process Name", style="bold")
            table.add_column("User", style="yellow")
            table.add_column("Memory", justify="right")
            table.add_column("Runtime Command", style="dim")

            for p in processes:
                pid_str = str(p.pid) if p.pid is not None else "[dim]unknown[/dim]"
                cmd = p.cmdline
                if len(cmd) > 40:
                    cmd = cmd[:37] + "..."
                table.add_row(
                    str(p.port),
                    p.protocol,
                    pid_str,
                    p.name,
                    p.user,
                    p.formatted_memory,
                    cmd,
                )

            console.print(table)
            return
        except ImportError:
            pass

    # Plain text output for scripts / pipes
    header = (
        f"{'PORT':<8} {'PROTO':<6} {'PID':<8} {'PROCESS':<16} {'USER':<14} {'MEMORY':<10} COMMAND"
    )
    print(header)
    print("-" * 80)
    for p in processes:
        pid_str = str(p.pid) if p.pid is not None else "-"
        cmd = p.cmdline
        if len(cmd) > 30:
            cmd = cmd[:27] + "..."
        print(
            f"{p.port:<8} {p.protocol:<6} {pid_str:<8} {p.name:<16} {p.user:<14} {p.formatted_memory:<10} {cmd}"
        )


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # Import core components lazily to minimize startup overhead
    from portsnip.core.reader import PortScanner
    from portsnip.core.signals import (
        PermissionDeniedError,
        PortsnipError,
        ProtectedProcessError,
        TerminationTimeoutError,
        terminate_process,
    )

    try:
        # Handle --list
        if args.list:
            scanner = PortScanner()
            items = scanner.list_all()
            render_list(items, quiet=args.quiet)
            return 0

        # Validate port argument
        if args.port is None:
            parser.print_help()
            return 0

        if not (1 <= args.port <= 65535):
            print(
                f"[ERROR] Invalid port number: {args.port}. Port must be between 1 and 65535.",
                file=sys.stderr,
            )
            return 2

        port = args.port

        # Scripting mode: --pid-only
        if args.pid_only:
            scanner = PortScanner()
            proc = scanner.find_by_port(port)
            if proc is not None and proc.pid is not None:
                print(proc.pid)
                return 0
            return 1

        if not args.quiet:
            print(f"Scanning socket bindings for port {port}...\n")

        scanner = PortScanner()
        proc = scanner.find_by_port(port)

        if proc is None:
            if not args.quiet:
                print(f"[INFO] No active listening process found on port {port}.")
            return 0

        # Process found, check privilege barrier
        if proc.pid is None:
            user_info = proc.formatted_user
            print(
                f"[ERROR] Port {port} is held by {user_info}. Unable to inspect process. Please run: sudo portsnip {port}",
                file=sys.stderr,
            )
            return 1

        # Check PID protection
        if proc.pid <= 10:
            print(
                f"[ERROR] Refusing to terminate PID {proc.pid}: protected system/kernel process.",
                file=sys.stderr,
            )
            return 1

        # Check UID match
        current_uid = os.getuid()
        if current_uid != 0 and proc.uid != current_uid:
            print(
                f"[ERROR] Unable to terminate PID {proc.pid} (owned by {proc.user}). Please run: sudo portsnip {port}",
                file=sys.stderr,
            )
            return 1

        # Display process details
        if not args.quiet:
            print(format_process_box(proc))
            print()

        # Confirmation prompt unless --force is specified
        if not args.force:
            try:
                prompt_text = f"? Terminate PID {proc.pid}? [y/N]: "
                reply = input(prompt_text).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                if not args.quiet:
                    print("[INFO] Operation cancelled.")
                return 0

            if reply not in ("y", "yes"):
                if not args.quiet:
                    print("[INFO] Operation cancelled.")
                return 0

        # Escalation prompt callback
        def prompt_escalate() -> bool:
            try:
                esc_reply = (
                    input(
                        f"? Process {proc.pid} did not exit after SIGTERM. Escalate to SIGKILL (9)? [y/N]: "
                    )
                    .strip()
                    .lower()
                )
                return esc_reply in ("y", "yes")
            except (EOFError, KeyboardInterrupt):
                return False

        # Execute termination
        res = terminate_process(
            pid=proc.pid,
            force=args.force,
            owner_uid=proc.uid,
            owner_name=proc.user,
            escalate_prompt=prompt_escalate,
        )

        if res.success:
            if not args.quiet:
                if res.escalated:
                    print("[OK] Dispatched SIGKILL (9)... Process evicted.")
                elif res.signal_sent == 15:
                    print("[OK] Dispatched SIGTERM (15)... Clean exit confirmed.")
                else:
                    print(f"[OK] {res.message}")
                print(f"[OK] Port {port} is now free.")
            return 0

        return 1

    except ProtectedProcessError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    except PermissionDeniedError as e:
        print(f"[ERROR] {e} Please run: sudo portsnip {args.port or ''}".rstrip(), file=sys.stderr)
        return 1
    except TerminationTimeoutError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    except PortsnipError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[INFO] Operation interrupted.", file=sys.stderr)
        return 130
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
