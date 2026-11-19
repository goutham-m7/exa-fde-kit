"""Offline configuration, local receipt and daily digest commands."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import sqlite3

from . import Inbox, definition, receiver


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    define = sub.add_parser("definition", help="print request bodies; create no resources")
    define.add_argument("webset")
    define.add_argument("callback")
    serve = sub.add_parser("serve")
    digest = sub.add_parser("digest")
    for p in (serve, digest):
        p.add_argument("webset")
        p.add_argument("db", type=Path)
    serve.add_argument("--port", type=int, default=8765)
    digest.add_argument("day", type=date.fromisoformat)
    args = parser.parse_args()
    try:
        if args.cmd == "definition":
            print(json.dumps(definition(args.webset, args.callback), indent=2))
        elif args.cmd == "digest":
            print(Inbox(args.db, args.webset).digest(args.day), end="")
        else:
            secret = os.environ.get("EXA_WEBHOOK_SECRET", "").encode()
            with receiver(Inbox(args.db, args.webset), secret, args.port) as server:
                server.serve_forever()
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
