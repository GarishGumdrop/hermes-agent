"""Fork change 19: ``hermes sessions trash`` (list / restore / purge) — undo for session deletes.

The trash itself lives in ``hermes_state_trash``; this is only the terminal surface for it.
"""
from __future__ import annotations

import time


def add_trash_parser(sessions_subparsers) -> None:
    trash = sessions_subparsers.add_parser(
        "trash", help="Recently deleted sessions: list, restore, or delete forever",
        description="Deleted sessions are kept for sessions.trash_retention_days days (default 7) "
                    "so an accidental delete can be undone.")
    actions = trash.add_subparsers(dest="trash_action")
    actions.add_parser("list", help="List recently deleted sessions (default)")
    restore = actions.add_parser("restore", help="Restore a deleted session (it gets a new id)")
    restore.add_argument("id", help="Trash id, or the deleted session's id, from `hermes sessions trash list`")
    purge = actions.add_parser("purge", help="Delete trashed sessions forever")
    purge.add_argument("id", nargs="?", help="Trash id to purge (omit with --all for everything)")
    purge.add_argument("--all", action="store_true", dest="purge_all", help="Purge every trashed session")


def _age(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def cmd_trash(db, args) -> int | None:
    import hermes_state_trash as trash

    action = getattr(args, "trash_action", None) or "list"
    if action == "list":
        entries = trash.list_trash(db)
        if not entries:
            days = trash.retention_days()
            print("No recently deleted sessions." if days > 0 else
                  "The session trash is off (sessions.trash_retention_days is 0).")
            return None
        now = time.time()
        print(f"{'TRASH ID':<34} {'DELETED':>8} {'LEFT':>5} {'MSGS':>5}  TITLE")
        for e in entries:
            left = _age(e["expires_at"] - now) if e.get("expires_at") else "-"
            extra = f" (+{e['session_count'] - 1} linked)" if e["session_count"] > 1 else ""
            print(f"{e['trash_id']:<34} {_age(now - e['deleted_at']) + ' ago':>8} {left:>5} "
                  f"{e['message_count']:>5}  {e['title']}{extra}")
        print("\nRestore with: hermes sessions trash restore <trash id>")
        return None
    if action == "restore":
        key = args.id
        try:
            result = trash.restore_from_trash(db, key) if _is_trash_id(db, key) else \
                trash.restore_from_trash(db, session_id=key)
        except trash.TrashNotFound:
            print(f"Nothing in the trash matches '{key}'.")
            return 1
        print(f"Restored as session '{result['session_id']}'.")
        return None
    if action == "purge":
        if args.purge_all:
            n = trash.purge_trash(db, everything=True)
        elif args.id:
            n = trash.purge_trash(db, args.id)
        else:
            print("Give a trash id, or --all.")
            return 1
        print(f"Deleted {n} trashed session{'s' if n != 1 else ''} forever.")
        return None
    print(f"Unknown trash action '{action}'.")
    return 1


def _is_trash_id(db, key: str) -> bool:
    import hermes_state_trash as trash
    return any(e["trash_id"] == key for e in trash.list_trash(db))
