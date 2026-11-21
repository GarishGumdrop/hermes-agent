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
from typing import Any, Optional, Sequence

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
    """Listing filters (``SessionQuery`` fields) for the desktop's main list. With the switch on,
    the internal sessions join it: their sources leave the exclusions (cron and messaging keep
    their own sections), and hidden rows, empty rows and subagent runs are admitted."""
    if not show:
        return {"include_subagents": include_subagents, "exclude_sources": exclude_sources or None,
                "min_message_count": 1}
    kept = [s for s in (exclude_sources or []) if s not in INTERNAL_SESSION_SOURCES]
    return {"include_subagents": True, "exclude_sources": kept or None, "include_hidden": True,
            "min_message_count": 0}


def project_tree_scope(hermes_home: str | Path | None,
                       excluded: Sequence[str] = _OWN_SECTION_SOURCES) -> dict[str, Any]:
    """``SessionQuery`` filters for the desktop's project view: the same rule over the view's own
    exclusions *excluded* (cron, messaging)."""
    if show_internal_sessions(hermes_home):
        return {"exclude_sources": tuple(s for s in excluded if s not in INTERNAL_SESSION_SOURCES),
                "min_message_count": 0, "include_hidden": True, "include_subagents": True}
    return {"exclude_sources": tuple(dict.fromkeys([*excluded, *INTERNAL_SESSION_SOURCES])),
            "min_message_count": 1}


def terminal_list_scope(source: Optional[str]) -> dict[str, Any]:
    """Listing filters for ``hermes sessions list``: the same rule, unless the user asked for one
    source."""
    if source:
        return {"exclude_sources": None}
    if show_internal_sessions():
        return {"exclude_sources": None, "include_hidden": True, "include_subagents": True}
    return {"exclude_sources": list(INTERNAL_SESSION_SOURCES), "min_message_count": 1}


def scoped_session_rows(store, *, limit: int, offset: int = 0, order_by_last_active: bool = False,
                        compact_rows: bool = False, include_pinned: bool = False,
                        include_hidden: bool = False, **filters) -> list[dict[str, Any]]:
    """``web_server_sessions._session_rows`` with ``include_hidden``, which a :func:`main_list_scope`
    carries."""
    from hermes_cli.web_server_sessions import _listing_filters
    from persistence.conversation.sessions import SessionOrder, SessionQuery, SessionWindow

    query = SessionQuery(**_listing_filters(**filters), include_pinned=include_pinned,
                         include_hidden=include_hidden,
                         order=SessionOrder.LAST_ACTIVE if order_by_last_active else SessionOrder.STARTED_AT)
    entries = store.sessions.list_sessions(query, SessionWindow(limit=limit, offset=offset),
                                           compact_rows=compact_rows)
    return [entry.as_list_row() for entry in entries]


# -- the Internal section's rows ---------------------------------------------------------------

def count_internal_sessions(store) -> int:
    return int(store.sessions.count_internal(INTERNAL_SESSION_SOURCES, _OWN_SECTION_SOURCES))


def _text(value: Any) -> Optional[str]:
    return value.strip() if isinstance(value, str) and value.strip() else None


def list_internal_sessions(store, limit: int = 200) -> list[dict[str, Any]]:
    """The newest internal sessions, shaped like the sidebar's other rows, each with
    ``internal_origin`` (the heading it is grouped under) and its "Started by" fields."""
    limit = max(0, min(int(limit), MAX_INTERNAL_ROWS))
    if not limit:
        return []
    entries = store.sessions.list_internal(INTERNAL_SESSION_SOURCES, _OWN_SECTION_SOURCES, limit=limit)
    launchers: dict[str, Any] = {}
    rows = []
    for entry in entries:
        config = entry.session.model_config or {}
        delegate_from = _text(config.get("_delegate_from"))
        launched_from = _text(config.get(LAUNCHED_FROM_KEY)) or delegate_from
        if launched_from and launched_from not in launchers:
            launchers[launched_from] = store.sessions.list_row(launched_from)
        launcher = launchers.get(launched_from) if launched_from else None
        row = entry.as_list_row()
        row["launched_from"] = launched_from
        row["launched_from_title"] = launcher.title if launcher is not None else None
        row["launched_by"] = _text(config.get(LAUNCHED_BY_KEY))
        row["internal_origin"] = origin_label(row, hidden=bool(entry.session.hidden),
                                              subagent=bool(delegate_from),
                                              launcher_found=launcher is not None)
        rows.append(row)
    return rows


def internal_slice(store, limit: int) -> dict[str, Any]:
    """The Internal section's payload for one profile's store."""
    return {"sessions": list_internal_sessions(store, limit), "total": count_internal_sessions(store)}


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


def terminal_list_note(store, source: Optional[str]) -> Optional[str]:
    """The line under ``hermes sessions list`` saying how many internal sessions it left out."""
    if source or show_internal_sessions():
        return None
    count = count_internal_sessions(store)
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
    from persistence.core.errors import AuthorityRefusal

    out: dict[str, str] = {}
    for name, limit in (("launched_from", _MAX_SESSION_ID_CHARS),
                        ("launched_by", _MAX_LAUNCHED_BY_CHARS)):
        if name not in params:
            continue
        value = params.pop(name)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise AuthorityRefusal("invalid_params", field=name,
                                    detail=f"must be a non-empty string of at most {limit} characters")
        out[name] = value.strip()
    return out


def record_provenance(store, session_id: str, provenance: dict[str, str]) -> None:
    """Write the provenance into the new session's model_config (merged, like the other
    creation markers)."""
    patch: dict[str, str] = {}
    if provenance.get("launched_from") and provenance["launched_from"] != session_id:
        patch[LAUNCHED_FROM_KEY] = provenance["launched_from"]
    if provenance.get("launched_by"):
        patch[LAUNCHED_BY_KEY] = provenance["launched_by"]
    if patch:
        store.sessions.patch_model_config(session_id, patch)
