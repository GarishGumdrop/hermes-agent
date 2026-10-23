"""Internal sessions (fork change 16): one rule for the sessions that the human session lists
leave out, the list and count behind the desktop sidebar's Internal section, and the
``sessions.show_internal`` switch that puts them back into the main lists.

A saved session is internal when it was not started as a conversation with the user:

- its source is one of ``INTERNAL_SESSION_SOURCES`` (a program that asked to stay out of the
  list, a one-off ``hermes chat`` command, a subagent run, a kanban worker, an editor);
- it is hidden (Bot Mode's chats and its group-room plumbing);
- it has no messages; or
- it is a subagent run (``_delegate_from``), whatever its source.

Cron runs are not internal: the sidebar gives them a section of their own.

"Started by": ``hermes chat`` records in the session's model_config the conversation whose
command started it (``_launched_from``, from ``HERMES_SESSION_ID``, which every agent command
carries) and a program's own name (``_launched_by``). The Internal section groups its rows by
that origin.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

INTERNAL_SESSION_SOURCES: tuple[str, ...] = ("acp", "kanban", "oneshot", "subagent", "tool")
# Sources with a sidebar section of their own; never listed as internal.
_OWN_SECTION_SOURCES: tuple[str, ...] = ("cron",)
LAUNCHED_FROM_KEY = "_launched_from"
LAUNCHED_BY_KEY = "_launched_by"
_MAX_SESSION_ID_CHARS = 200
_MAX_LAUNCHED_BY_CHARS = 120
MAX_INTERNAL_ROWS = 500


# -- the switch ------------------------------------------------------------------------------

def show_internal_sessions(hermes_home: str | Path | None = None) -> bool:
    """``sessions.show_internal`` from *hermes_home*'s config.yaml (this process's home when
    None). One server lists many profiles, so the store's own home decides. False when the
    config cannot be read."""
    from hermes_cli.config import load_config_readonly
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override
    from utils import is_truthy_value

    token = set_hermes_home_override(str(hermes_home)) if hermes_home is not None else None
    try:
        sessions_cfg = load_config_readonly().get("sessions") or {}
    except Exception:
        return False
    finally:
        if token is not None:
            reset_hermes_home_override(token)
    return isinstance(sessions_cfg, dict) and is_truthy_value(sessions_cfg.get("show_internal"))


def internal_exclusions(hermes_home: str | Path | None = None) -> list[str]:
    """The sources a human session list leaves out: the internal ones, none with the switch on."""
    return [] if show_internal_sessions(hermes_home) else list(INTERNAL_SESSION_SOURCES)


def main_list_scope(show: bool, include_subagents: bool,
                    exclude_sources: Optional[list[str]]) -> dict[str, Any]:
    """``list_sessions_rich`` arguments for the desktop's main list. With the switch on, the
    internal sessions join it: their sources leave the exclusions (cron and messaging keep their
    own sections), and hidden rows, empty rows and subagent runs are admitted."""
    if not show:
        return {"include_subagents": include_subagents, "exclude_sources": exclude_sources or None,
                "min_message_count": 1}
    kept = [s for s in (exclude_sources or []) if s not in INTERNAL_SESSION_SOURCES]
    return {"include_subagents": True, "exclude_sources": kept or None, "include_hidden": True,
            "min_message_count": 0}


def project_tree_scope(hermes_home: str | Path | None) -> dict[str, Any]:
    """``list_sessions_rich`` arguments for the desktop's project view: the same rule."""
    if show_internal_sessions(hermes_home):
        return {"exclude_sources": list(_OWN_SECTION_SOURCES), "min_message_count": 0,
                "include_hidden": True, "include_subagents": True}
    return {"exclude_sources": [*_OWN_SECTION_SOURCES, *INTERNAL_SESSION_SOURCES],
            "min_message_count": 1}


def terminal_list_scope(source: Optional[str]) -> dict[str, Any]:
    """``list_sessions_rich`` arguments for ``hermes sessions list``: the same rule, unless the
    user asked for one source."""
    if source:
        return {"exclude_sources": None}
    if show_internal_sessions():
        return {"exclude_sources": None, "include_hidden": True, "include_subagents": True}
    return {"exclude_sources": list(INTERNAL_SESSION_SOURCES), "min_message_count": 1}


# -- the Internal section's rows ---------------------------------------------------------------

def _internal_where() -> str:
    from hermes_state_common import _LISTABLE_CHILD_SQL
    from hermes_state_sessions import _delegate_from_json

    delegate = _delegate_from_json("s.model_config")
    internal = ", ".join(f"'{s}'" for s in INTERNAL_SESSION_SOURCES)
    own = ", ".join(f"'{s}'" for s in _OWN_SECTION_SOURCES)
    # Compression continuations are left out: the list shows the conversation they continue.
    return (
        "s.archived = 0"
        f" AND COALESCE(s.source, '') NOT IN ({own})"
        f" AND ({_LISTABLE_CHILD_SQL} OR {delegate} IS NOT NULL)"
        f" AND (s.source IN ({internal}) OR s.hidden <> 0 OR s.message_count = 0"
        f" OR {delegate} IS NOT NULL)"
    )


def count_internal_sessions(db) -> int:
    row = db._read_one(f"SELECT COUNT(*) FROM sessions s WHERE {_internal_where()}")
    return int(row[0]) if row else 0


def list_internal_sessions(db, limit: int = 200) -> list[dict[str, Any]]:
    """The newest internal sessions, shaped like the sidebar's other rows, each with
    ``internal_origin`` (the heading it is grouped under) and its "Started by" fields."""
    from hermes_state_common import _sql_json_extract, _sql_preview_raw, _sql_session_last_active

    limit = max(0, min(int(limit), MAX_INTERNAL_ROWS))
    if not limit:
        return []
    launched_from = _sql_json_extract("s.model_config", f"$.{LAUNCHED_FROM_KEY}")
    launched_by = _sql_json_extract("s.model_config", f"$.{LAUNCHED_BY_KEY}")
    delegate_from = _sql_json_extract("s.model_config", "$._delegate_from")
    launcher = f"COALESCE({launched_from}, {delegate_from})"
    query = f"""
        SELECT {db._compact_session_cols()},
               s.hidden AS _internal_hidden,
               {launched_from} AS _internal_launched_from,
               {launched_by} AS _internal_launched_by,
               {delegate_from} AS _internal_delegate_from,
               (SELECT l.title FROM sessions l WHERE l.id = {launcher}) AS _internal_launcher_title,
               (SELECT COUNT(*) FROM sessions l WHERE l.id = {launcher}) AS _internal_launcher_found,
               {_sql_preview_raw()},
               {_sql_session_last_active("s")} AS last_active
        FROM sessions s
        WHERE {_internal_where()}
        ORDER BY last_active DESC, s.started_at DESC, s.id DESC
        LIMIT ?
    """
    rows = []
    for raw in db._read_all(query, [limit]):
        row = db._list_row(raw)
        fields = {key: row.pop(f"_internal_{key}", None) for key in (
            "hidden", "launched_from", "launched_by", "delegate_from", "launcher_title",
            "launcher_found")}
        row["launched_from"] = fields["launched_from"] or fields["delegate_from"]
        row["launched_from_title"] = fields["launcher_title"]
        row["launched_by"] = fields["launched_by"]
        row["internal_origin"] = origin_label(row, hidden=bool(fields["hidden"]),
                                              subagent=bool(fields["delegate_from"]),
                                              launcher_found=bool(fields["launcher_found"]))
        row["unread"] = db.session_unread(row)
        rows.append(row)
    return rows


def internal_slice(db, limit: int) -> dict[str, Any]:
    """The Internal section's payload for one profile's store."""
    return {"sessions": list_internal_sessions(db, limit), "total": count_internal_sessions(db)}


def origin_label(row: dict[str, Any], *, hidden: bool, subagent: bool,
                 launcher_found: bool) -> str:
    """The heading an internal session is listed under: what started it, in plain words."""
    by = str(row.get("launched_by") or "").strip()
    if row.get("launched_from"):
        prefix = "Subagent runs of" if subagent else "Started by"
        title = str(row.get("launched_from_title") or "").strip()
        if not launcher_found:
            label = f"{prefix} a conversation that was deleted"
        elif title:
            label = f"{prefix} \u201c{title}\u201d"
        else:
            label = f"{prefix} an untitled conversation"
        return f"{label} ({by})" if by and not subagent else label
    if by:
        return by
    title = str(row.get("title") or "")
    if hidden and title == "Bot Chat":
        return "Bot chats (Bots tab)"
    if hidden and title.startswith("Group: "):
        return "Bot group rooms"
    source = str(row.get("source") or "")
    named = {
        "oneshot": "One-off commands, origin not recorded",
        "tool": "Programs, origin not recorded",
        "acp": "Code editors",
        "kanban": "Kanban workers",
        "subagent": "Subagent runs",
    }
    if source in named:
        return named[source]
    if hidden:
        return "Hidden sessions"
    if not row.get("message_count"):
        return "Empty sessions"
    return "Other"


def terminal_list_note(db, source: Optional[str]) -> Optional[str]:
    """The line under ``hermes sessions list`` saying how many internal sessions it left out."""
    if source or show_internal_sessions():
        return None
    count = count_internal_sessions(db)
    if not count:
        return None
    noun = "session" if count == 1 else "sessions"
    return (f"{count} internal {noun} not listed (programs, one-off commands, subagent runs, "
            "bot chats, empty sessions). To list them: hermes config set sessions.show_internal true")


# -- "Started by" --------------------------------------------------------------------------------

def launch_provenance(args: Any = None, parameters: Any = None) -> dict[str, str]:
    """Creation options naming what started a ``hermes chat`` session (client side): the
    conversation whose agent ran the command (its ``HERMES_SESSION_ID``) and a program's own name
    (a ``launched_by`` argument or ``HERMES_LAUNCHED_BY``). Only options the gateway advertises
    are returned, so an older gateway is never refused."""
    out: dict[str, str] = {}
    launched_from = (os.environ.get("HERMES_SESSION_ID") or "").strip()
    if launched_from:
        out["launched_from"] = launched_from[:_MAX_SESSION_ID_CHARS]
    launched_by = (getattr(args, "launched_by", None) or os.environ.get("HERMES_LAUNCHED_BY") or "")
    if isinstance(launched_by, str) and launched_by.strip():
        out["launched_by"] = launched_by.strip()[:_MAX_LAUNCHED_BY_CHARS]
    if parameters is not None:
        out = {key: value for key, value in out.items() if key in parameters}
    return out


def pop_provenance(params: dict[str, Any]) -> dict[str, str]:
    """Server side: take the provenance options out of a ``session.create`` request (they are
    not launch policy, so the frozen request never carries them) and validate them."""
    from hermes_state_runtime import RuntimeStoreError

    out: dict[str, str] = {}
    for name, limit in (("launched_from", _MAX_SESSION_ID_CHARS),
                        ("launched_by", _MAX_LAUNCHED_BY_CHARS)):
        if name not in params:
            continue
        value = params.pop(name)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise RuntimeStoreError("invalid_params", field=name,
                                    detail=f"must be a non-empty string of at most {limit} characters")
        out[name] = value.strip()
    return out


def record_provenance(db, session_id: str, provenance: dict[str, str]) -> None:
    """Write the provenance into the new session's model_config (merged, like the other
    creation markers)."""
    patch: dict[str, str] = {}
    if provenance.get("launched_from") and provenance["launched_from"] != session_id:
        patch[LAUNCHED_FROM_KEY] = provenance["launched_from"]
    if provenance.get("launched_by"):
        patch[LAUNCHED_BY_KEY] = provenance["launched_by"]
    if patch:
        db._write_model_config_patch(session_id, patch)
