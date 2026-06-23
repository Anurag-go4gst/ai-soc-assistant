#!/usr/bin/env python3
"""Operator CLI for the AI-SOC auth registry (``backend/app/auth/users.json``).

Supported, race-safe provisioning instead of hand-editing the JSON. Examples::

    # add or update a user (password prompted if omitted)
    python3 scripts/manage_users.py add --username jane@velocis.in --role analyst

    # full-rights operator with debug access
    python3 scripts/manage_users.py add --username lead@velocis.in \
        --role soc_lead --debug-access --password 'secret'

    python3 scripts/manage_users.py list
    python3 scripts/manage_users.py delete --username jane@velocis.in

Roles: ``viewer`` < ``analyst`` < ``soc_lead`` (highest session role; full Splunk
read + ``splunk_run_query`` via RBAC inheritance). ``debug_access`` defaults to the
role default (true for ``soc_lead``) unless ``--debug-access/--no-debug-access`` is
given. The registry file is operator-protected and git-ignored.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.auth import user_registry  # noqa: E402

_VALID_ROLES = ("viewer", "analyst", "soc_lead")


def _resolve_password(args: argparse.Namespace) -> str:
    if args.password:
        return args.password
    password = getpass.getpass("Password: ")
    if not password:
        raise SystemExit("password_required")
    return password


def _cmd_add(args: argparse.Namespace) -> int:
    debug_access: bool | None
    if args.debug_access is None:
        debug_access = None
    else:
        debug_access = args.debug_access
    user = user_registry.upsert_user(
        args.username,
        password=_resolve_password(args),
        role=args.role,
        debug_access=debug_access,
    )
    print(
        f"upserted user username={user.username} role={user.role} "
        f"debug_access={user.debug_access}"
    )
    return 0


def _cmd_list(_args: argparse.Namespace) -> int:
    for user in user_registry.list_public_users():
        print(f"{user['username']}\trole={user['role']}\tdebug_access={user['debug_access']}")
    return 0


def _cmd_delete(args: argparse.Namespace) -> int:
    removed = user_registry.delete_user(args.username)
    print(f"deleted={removed} username={args.username}")
    return 0 if removed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Create or update a user")
    add.add_argument("--username", required=True)
    add.add_argument("--password", default=None, help="Prompted securely if omitted")
    add.add_argument("--role", default="analyst", choices=_VALID_ROLES)
    debug_group = add.add_mutually_exclusive_group()
    debug_group.add_argument("--debug-access", dest="debug_access", action="store_true", default=None)
    debug_group.add_argument("--no-debug-access", dest="debug_access", action="store_false")
    add.set_defaults(func=_cmd_add)

    list_cmd = sub.add_parser("list", help="List users (no secrets)")
    list_cmd.set_defaults(func=_cmd_list)

    delete = sub.add_parser("delete", help="Remove a user")
    delete.add_argument("--username", required=True)
    delete.set_defaults(func=_cmd_delete)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
