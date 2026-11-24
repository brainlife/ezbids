"""``python -m aimport serve``: run the loopback API.

Binds 127.0.0.1 by default. Outside the container only loopback binds are allowed (127.0.0.1, ::1,
localhost); anything else (0.0.0.0, a LAN address) is refused unless AIMPORT_IN_CONTAINER=1 (the Dockerfile sets it):
inside the container the published port is the only way in, and ``bl aimport`` must publish it on
127.0.0.1 only: ``-p 127.0.0.1:<port>:<port>``. The token comes from the AIMPORT_TOKEN environment
variable (preferred: --token is visible in the process list). Requests whose Host header is not
127.0.0.1/localhost/[::1] with the port (or a --host-allow value, e.g. when the published port
differs from --port) get 421, against DNS rebinding.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

LOOPBACK = ("127.0.0.1", "::1", "localhost")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aimport")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the loopback API")
    serve.add_argument("--input", required=True, type=Path)
    serve.add_argument("--work", required=True, type=Path)
    serve.add_argument("--keys", required=True, type=Path)
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--token", default=None, help="prefer the AIMPORT_TOKEN environment variable")
    serve.add_argument("--host-allow", action="append", default=[], help="allowed Host header (repeatable)")
    serve.add_argument("--origin", action="append", default=[], help="allowed CORS origin (repeatable)")
    args = parser.parse_args(argv)
    token = os.environ.get("AIMPORT_TOKEN") or args.token
    if not token:
        parser.error("AIMPORT_TOKEN (or --token) is required")
    if not os.environ.get("AIMPORT_TOKEN"):
        print("aimport: warning: --token is visible in the process list; use AIMPORT_TOKEN", file=sys.stderr)
    if args.host not in LOOPBACK and os.environ.get("AIMPORT_IN_CONTAINER") != "1":
        parser.error(f"--host {args.host} is only allowed inside the container (AIMPORT_IN_CONTAINER=1); "
                     f"outside it use {', '.join(LOOPBACK)}")
    hosts = args.host_allow or [f"127.0.0.1:{args.port}", f"localhost:{args.port}", f"[::1]:{args.port}"]

    import uvicorn

    from .server import create_app

    try:
        app = create_app(args.input, args.work, args.keys, token, args.origin, hosts)
    except ValueError as e:
        print(f"aimport: {e}", file=sys.stderr)
        return 2
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
