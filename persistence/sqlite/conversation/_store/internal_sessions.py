"""Fork change 16: the rows of the desktop sidebar's Internal section and their count.

The rule (which sources are internal, which have a section of their own) lives in
``hermes_cli/internal_sessions.py``; this module only turns it into SQL. A row is internal when
it is not archived, its source has no section of its own, it is listable (a root, a branch or reset
child, or a subagent run) and it is internal: an internal source, hidden, empty, or a subagent run.
Compression continuations are left out: the list shows the conversation they continue.
"""

from __future__ import annotations

from typing import Any, Sequence

from persistence.sqlite._holder import StoreHolder
from persistence.sqlite._schema_ddl import _sql_json_extract
from persistence.sqlite.conversation._store.portability import _compact_session_cols
from persistence.sqlite.conversation._store.sessions import _list_row
from persistence.sqlite.conversation._store.sql_common import (
    _LISTABLE_CHILD_SQL, _placeholders, _sql_preview_raw, _sql_session_last_active,
)


def _internal_where(internal_sources: Sequence[str], own_section_sources: Sequence[str]) -> tuple[str, list[Any]]:
    delegate = _sql_json_extract("s.model_config", "$._delegate_from")
    clauses = ["s.archived = 0", f"({_LISTABLE_CHILD_SQL} OR {delegate} IS NOT NULL)"]
    params: list[Any] = []
    if own_section_sources:
        clauses.append(f"COALESCE(s.source, '') NOT IN ({_placeholders(own_section_sources)})")
        params += list(own_section_sources)
    internal = (f"s.source IN ({_placeholders(internal_sources)}) OR " if internal_sources else "")
    clauses.append(f"({internal}s.hidden <> 0 OR s.message_count = 0 OR {delegate} IS NOT NULL)")
    params += list(internal_sources)
    return " AND ".join(clauses), params


def count_internal_sessions(holder: StoreHolder, internal_sources: Sequence[str],
                            own_section_sources: Sequence[str]) -> int:
    where, params = _internal_where(internal_sources, own_section_sources)
    row = holder._read_one(f"SELECT COUNT(*) FROM sessions s WHERE {where}", params)
    return int(row[0]) if row else 0


def list_internal_sessions(holder: StoreHolder, internal_sources: Sequence[str],
                           own_section_sources: Sequence[str], limit: int) -> list[dict[str, Any]]:
    """The newest internal rows (compact columns, preview, ``last_active``), newest first."""
    holder.flush_for_read()  # rows carry token/cost totals
    where, params = _internal_where(internal_sources, own_section_sources)
    # The page is ranked and cut on ids alone; only its rows pay for the preview projection.
    query = f"""
        WITH page AS (
            SELECT s.id AS page_id, {_sql_session_last_active("s")} AS ranked_last_active
            FROM sessions s
            WHERE {where}
            ORDER BY ranked_last_active DESC, s.started_at DESC, s.id DESC
            LIMIT ?
        )
        SELECT {_compact_session_cols(holder.db_path.parent)},
               {_sql_preview_raw()},
               {_sql_session_last_active("s")} AS last_active,
               page.ranked_last_active AS _effective_last_active
        FROM page
        JOIN sessions s ON s.id = page.page_id
        ORDER BY _effective_last_active DESC, s.started_at DESC, s.id DESC
    """
    return [_list_row(row) for row in holder._read_all(query, [*params, int(limit)])]
