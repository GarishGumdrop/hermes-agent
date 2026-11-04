"""Fork change 19 (GarishGumdrop/hermes-agent): undo for user session deletes.

A user delete (desktop, dashboard, CLI, TUI) copies the doomed rows into ``session_trash`` /
``session_trash_messages`` inside the delete's own write transaction, so a copy exists exactly
when a delete commits. Nothing else in Hermes reads these tables: the delete itself, its
retirement fence and every listing behave as before. A copy lives ``sessions.trash_retention_days``
days (default 7; 0 turns the trash off) and is purged by the next delete or trash read after that.

Restore re-inserts the conversation under NEW session ids: the retirement fence keeps a deleted id
dead for good (``hermes_state_mutation_retirement.create_conflict``). The restored rows carry no
gateway route (``session_key`` / ``chat_id`` / ``origin_json``), so a local surface's chat is
adopted on its next native resume exactly like pre-gateway local history
(``hermes_state_local_migration.validate_legacy_row``), and continues from there.

Housekeeping deletes (empty-session sweeps, age prunes) are not trashed: they are not undo cases.
Media and spillover archives a trashed message mentions are kept until its copy is purged
(``trash_media_mentions``, ``trash_spillover_rows``).
"""
from __future__ import annotations

import base64
import json
import math
import time
import uuid
from typing import Any, Optional

TRASH_TABLE = 'session_trash'
TRASH_MESSAGES_TABLE = 'session_trash_messages'
DEFAULT_RETENTION_DAYS = 7.0
PAYLOAD_VERSION = 1

_DDL = (
    f"""CREATE TABLE IF NOT EXISTS {TRASH_TABLE} (
        trash_id TEXT PRIMARY KEY,
        deleted_at REAL NOT NULL,
        root_session_id TEXT NOT NULL,
        title TEXT,
        session_count INTEGER NOT NULL,
        message_count INTEGER NOT NULL,
        payload TEXT NOT NULL)""",
    f"""CREATE TABLE IF NOT EXISTS {TRASH_MESSAGES_TABLE} (
        id INTEGER PRIMARY KEY,
        trash_id TEXT NOT NULL,
        content TEXT,
        api_content TEXT,
        row_json TEXT NOT NULL)""",
    f"CREATE INDEX IF NOT EXISTS idx_{TRASH_MESSAGES_TABLE}_trash ON {TRASH_MESSAGES_TABLE}(trash_id)",
)

# Restored rows must not carry the deleted conversation's gateway route: the route was dropped by
# the delete, and a row that still names it is refused adoption (it would look owned elsewhere).
_ROUTE_COLUMNS = ('session_key', 'chat_id', 'origin_json')
_RESET_COLUMNS = {'runtime_revision': 0, 'runtime_generation': 0, 'handoff_state': None,
                  'handoff_platform': None, 'handoff_error': None}


class TrashNotFound(LookupError):
    """No trash entry matches the request (never trashed, already restored, or purged)."""


# ── config ──────────────────────────────────────────────────────────────────────────────────────

def retention_days() -> float:
    """``sessions.trash_retention_days`` (default 7). 0 or less turns the trash off."""
    try:
        from hermes_cli.config import load_config_readonly
        value = (load_config_readonly().get('sessions') or {}).get('trash_retention_days', DEFAULT_RETENTION_DAYS)
        days = float(DEFAULT_RETENTION_DAYS if value is None else value)
    except Exception:  # health: allow BLE001 -- an unreadable config keeps the default
        return DEFAULT_RETENTION_DAYS
    return days if math.isfinite(days) else DEFAULT_RETENTION_DAYS


# ── encoding (BLOB columns survive the JSON copy) ───────────────────────────────────────────────

def _enc(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {'__b64__': base64.b64encode(bytes(value)).decode('ascii')}
    return value


def _dec(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {'__b64__'}:
        return base64.b64decode(value['__b64__'])
    return value


def _row_json(row: dict) -> str:
    return json.dumps({k: _enc(v) for k, v in row.items()}, ensure_ascii=False)


def _row_from_json(raw: str) -> dict:
    return {k: _dec(v) for k, v in json.loads(raw).items()}


# ── schema helpers ──────────────────────────────────────────────────────────────────────────────

def _has_tables(conn) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (TRASH_TABLE,)).fetchone() is not None


def _ensure_tables(conn) -> None:
    for statement in _DDL:  # one statement each: executescript would COMMIT the caller's write
        conn.execute(statement)


def _columns(conn, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()]


def _json_ids(ids) -> str:
    return json.dumps(list(ids))


# ── snapshot (inside the delete's transaction) ──────────────────────────────────────────────────

def snapshot_for_trash(conn, session_ids, *, requested: Optional[str] = None) -> Optional[str]:
    """Copy the sessions a user delete is about to remove (plus their delegate children, which the
    delete cascades) into the trash, in the caller's open write transaction. Returns the trash id,
    or None when the trash is off or nothing worth restoring is in scope (no messages).

    Call it BEFORE ``retire_sessions``: retirement strips receipts and the DELETEs follow. If the
    delete then aborts, the transaction rolls this copy back with it."""
    days = retention_days()
    if days <= 0:
        return None
    from hermes_state_sessions import _collect_delegate_child_ids
    scope = list(dict.fromkeys(sid for sid in (session_ids or ()) if isinstance(sid, str) and sid))
    if not scope:
        return None
    ids = list(dict.fromkeys([*scope, *_collect_delegate_child_ids(conn, scope)]))
    sessions = [dict(row) for row in conn.execute(
        'SELECT * FROM sessions WHERE id IN (SELECT value FROM json_each(?)) ORDER BY started_at, id',
        (_json_ids(ids),)).fetchall()]
    if not sessions:
        return None
    present = [row['id'] for row in sessions]
    messages = [dict(row) for row in conn.execute(
        'SELECT * FROM messages WHERE session_id IN (SELECT value FROM json_each(?)) ORDER BY id',
        (_json_ids(present),)).fetchall()]
    if not messages:
        return None
    _ensure_tables(conn)
    _purge_expired(conn, days)
    hashes = sorted({row.get('system_prompt_hash') for row in sessions if row.get('system_prompt_hash')})
    prompts = {row[0]: row[1] for row in conn.execute(
        'SELECT hash, prompt FROM system_prompts WHERE hash IN (SELECT value FROM json_each(?))',
        (_json_ids(hashes),)).fetchall()} if hashes else {}
    usage = [dict(row) for row in conn.execute(
        'SELECT * FROM session_model_usage WHERE session_id IN (SELECT value FROM json_each(?))',
        (_json_ids(present),)).fetchall()] if _table_exists(conn, 'session_model_usage') else []
    root = requested if requested in present else (scope[0] if scope[0] in present else present[0])
    trash_id = uuid.uuid4().hex
    payload = {
        'version': PAYLOAD_VERSION,
        'root_session_id': root,
        'requested': [sid for sid in scope if sid in present],
        'sessions': [{k: _enc(v) for k, v in row.items()} for row in sessions],
        'system_prompts': prompts,
        'model_usage': [{k: _enc(v) for k, v in row.items()} for row in usage],
    }
    conn.execute(
        f'INSERT INTO {TRASH_TABLE}(trash_id, deleted_at, root_session_id, title, session_count, '
        'message_count, payload) VALUES (?,?,?,?,?,?,?)',
        (trash_id, time.time(), root, _entry_title(sessions, messages, root), len(sessions), len(messages),
         json.dumps(payload, ensure_ascii=False)))
    conn.executemany(
        f'INSERT INTO {TRASH_MESSAGES_TABLE}(trash_id, content, api_content, row_json) VALUES (?,?,?,?)',
        [(trash_id, m.get('content'), m.get('api_content'),
          _row_json({k: v for k, v in m.items() if k not in ('content', 'api_content')})) for m in messages])
    return trash_id


def _table_exists(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _entry_title(sessions: list[dict], messages: list[dict], root: str) -> str:
    by_id = {row['id']: row for row in sessions}
    for row in [by_id.get(root), *sessions]:
        if row and (row.get('title') or '').strip():
            return row['title'].strip()
    for message in messages:
        if message.get('role') == 'user' and isinstance(message.get('content'), str) and message['content'].strip():
            text = ' '.join(message['content'].split())
            return text if len(text) <= 80 else text[:77] + '...'
    return 'Untitled session'


# ── purge ───────────────────────────────────────────────────────────────────────────────────────

def _purge_ids(conn, trash_ids) -> int:
    """Drop the given entries and hand their spillover archives back to the normal collector.
    Media needs no hand-back: its retirement candidate stays while the file exists."""
    trash_ids = list(trash_ids)
    if not trash_ids:
        return 0
    from hermes_state_media import SPILLOVER_PREFIX
    from tools.tool_result_storage import SPILLOVER_SQL_FILTER, spillover_names_in_text
    for content, api_content in conn.execute(
            f'SELECT content, api_content FROM {TRASH_MESSAGES_TABLE} '
            f'WHERE trash_id IN (SELECT value FROM json_each(?)) AND {SPILLOVER_SQL_FILTER}',
            (_json_ids(trash_ids),)).fetchall():
        conn.executemany('INSERT OR IGNORE INTO state_meta(key,value) VALUES(?,?)',
                         [(SPILLOVER_PREFIX + n, json.dumps(n)) for n in spillover_names_in_text(content, api_content)])
    conn.execute(f'DELETE FROM {TRASH_MESSAGES_TABLE} WHERE trash_id IN (SELECT value FROM json_each(?))',
                 (_json_ids(trash_ids),))
    cur = conn.execute(f'DELETE FROM {TRASH_TABLE} WHERE trash_id IN (SELECT value FROM json_each(?))',
                       (_json_ids(trash_ids),))
    return cur.rowcount or 0


def _purge_expired(conn, days: float) -> int:
    cutoff = time.time() - max(days, 0) * 86400
    expired = [row[0] for row in conn.execute(
        f'SELECT trash_id FROM {TRASH_TABLE} WHERE deleted_at < ?', (cutoff,)).fetchall()]
    return _purge_ids(conn, expired)


def purge_trash(db, trash_id: Optional[str] = None, *, everything: bool = False) -> int:
    """Delete forever: one entry, every entry (``everything``), or (neither) only expired ones.
    Releases the media/spillover the purged copies were keeping. Returns entries removed."""
    days = retention_days()

    def _do(conn):
        if not _has_tables(conn):
            return 0
        if everything:
            ids = [row[0] for row in conn.execute(f'SELECT trash_id FROM {TRASH_TABLE}').fetchall()]
            return _purge_ids(conn, ids)
        if trash_id:
            return _purge_ids(conn, [trash_id])
        return _purge_expired(conn, max(0, days))
    removed = db._execute_write(_do)
    if removed:
        from hermes_state_media import collect_retired_media
        collect_retired_media(db)
    return removed


# ── listing ─────────────────────────────────────────────────────────────────────────────────────

def list_trash(db, *, purge: bool = True) -> list[dict]:
    """Restorable entries, newest first. With ``purge`` (and a writable store) expired entries are
    deleted first; either way they are left out of the list."""
    days = retention_days()
    if purge and getattr(db, 'read_only', False) is False:
        try:
            purge_trash(db)
        except Exception:  # health: allow BLE001 -- listing must not fail on a purge hiccup
            pass
    with db._read_ctx() as conn:
        if not _has_tables(conn):
            return []
        rows = conn.execute(
            f'SELECT trash_id, deleted_at, root_session_id, title, session_count, message_count, payload '
            f'FROM {TRASH_TABLE} ORDER BY deleted_at DESC').fetchall()
    out = []
    horizon = max(days, 0) * 86400
    for row in rows:
        if days > 0 and row['deleted_at'] < time.time() - horizon:
            continue
        try:
            payload = json.loads(row['payload'])
            session_ids = [s.get('id') for s in payload.get('sessions', [])]
        except (TypeError, ValueError):
            session_ids = []
        out.append({
            'trash_id': row['trash_id'],
            'deleted_at': row['deleted_at'],
            'expires_at': row['deleted_at'] + horizon if days > 0 else None,
            'root_session_id': row['root_session_id'],
            'title': row['title'],
            'session_count': row['session_count'],
            'message_count': row['message_count'],
            'session_ids': session_ids,
        })
    return out


def _find_entry(conn, trash_id: Optional[str], session_id: Optional[str]):
    if not _has_tables(conn):
        return None
    if trash_id:
        return conn.execute(f'SELECT * FROM {TRASH_TABLE} WHERE trash_id=?', (trash_id,)).fetchone()
    if session_id:
        return conn.execute(
            f"SELECT * FROM {TRASH_TABLE} WHERE root_session_id=? OR EXISTS ("
            "SELECT 1 FROM json_each(payload, '$.sessions') s WHERE json_extract(s.value, '$.id')=?) "
            'ORDER BY deleted_at DESC LIMIT 1', (session_id, session_id)).fetchone()
    return None


# ── restore ─────────────────────────────────────────────────────────────────────────────────────

def restore_from_trash(db, trash_id: Optional[str] = None, *, session_id: Optional[str] = None) -> dict:
    """Put a trashed conversation back under new ids and drop its trash entry, in one write.

    ``trash_id`` names the entry; or ``session_id`` (any id the delete removed) picks the newest
    entry holding it, which is what an Undo right after a delete needs. Returns
    ``{trash_id, session_id, session_ids: {old: new}}`` where ``session_id`` is the new id of the
    row the user deleted. Raises :class:`TrashNotFound`."""
    from hermes_state_ids import new_session_id
    from hermes_state_local_migration import LEGACY_LOCAL_SOURCES

    def _do(conn):
        entry = _find_entry(conn, trash_id, session_id)
        if entry is None:
            raise TrashNotFound(trash_id or session_id or '')
        payload = json.loads(entry['payload'])
        if int(payload.get('version') or 0) > PAYLOAD_VERSION:
            raise ValueError('trash entry was written by a newer Hermes')
        sessions = [{k: _dec(v) for k, v in row.items()} for row in payload.get('sessions', [])]
        mapping: dict[str, str] = {}
        for row in sessions:
            new_id = new_session_id()
            while new_id in mapping.values() or conn.execute(
                    'SELECT 1 FROM sessions WHERE id=?', (new_id,)).fetchone():
                new_id = new_session_id()
            mapping[row['id']] = new_id
        for digest, prompt in (payload.get('system_prompts') or {}).items():
            conn.execute('INSERT OR IGNORE INTO system_prompts(hash, prompt) VALUES (?,?)', (digest, prompt))
        live_session_cols = set(_columns(conn, 'sessions'))
        for row in _parents_first(sessions):
            new_row = _restored_session_row(conn, row, mapping, LEGACY_LOCAL_SOURCES)
            cols = [c for c in new_row if c in live_session_cols]
            conn.execute(f'INSERT INTO sessions ({", ".join(cols)}) VALUES ({", ".join("?" * len(cols))})',
                         [new_row[c] for c in cols])
        live_message_cols = set(_columns(conn, 'messages'))
        for msg_row in conn.execute(
                f'SELECT content, api_content, row_json FROM {TRASH_MESSAGES_TABLE} WHERE trash_id=? ORDER BY id',
                (entry['trash_id'],)).fetchall():
            message = {**_row_from_json(msg_row['row_json']), 'content': msg_row['content'],
                       'api_content': msg_row['api_content']}
            message['session_id'] = mapping.get(message.get('session_id'), message.get('session_id'))
            # Keep the original row id when it is free (it always is: ids are never reused), so
            # display order and anything keyed by message id survive the round trip.
            if message.get('id') is not None and conn.execute(
                    'SELECT 1 FROM messages WHERE id=?', (message['id'],)).fetchone():
                message.pop('id')
            cols = [c for c in message if c in live_message_cols]
            conn.execute(f'INSERT INTO messages ({", ".join(cols)}) VALUES ({", ".join("?" * len(cols))})',
                         [message[c] for c in cols])
        if payload.get('model_usage') and _table_exists(conn, 'session_model_usage'):
            usage_cols = set(_columns(conn, 'session_model_usage'))
            for raw in payload['model_usage']:
                usage = {k: _dec(v) for k, v in raw.items()}
                usage['session_id'] = mapping.get(usage.get('session_id'), usage.get('session_id'))
                cols = [c for c in usage if c in usage_cols]
                conn.execute(f'INSERT OR IGNORE INTO session_model_usage ({", ".join(cols)}) '
                             f'VALUES ({", ".join("?" * len(cols))})', [usage[c] for c in cols])
        conn.execute(f'DELETE FROM {TRASH_MESSAGES_TABLE} WHERE trash_id=?', (entry['trash_id'],))
        conn.execute(f'DELETE FROM {TRASH_TABLE} WHERE trash_id=?', (entry['trash_id'],))
        root = payload.get('root_session_id') or entry['root_session_id']
        return {'trash_id': entry['trash_id'], 'session_id': mapping.get(root), 'session_ids': mapping}
    return db._execute_write(_do)


def _parents_first(sessions: list[dict]) -> list[dict]:
    """Rows ordered so a parent inside the snapshot is inserted before its children (FK)."""
    by_id = {row['id']: row for row in sessions}
    done: set[str] = set()
    ordered: list[dict] = []

    def visit(row, trail=()):
        if row['id'] in done or row['id'] in trail:
            return
        parent = row.get('parent_session_id')
        if parent in by_id:
            visit(by_id[parent], (*trail, row['id']))
        done.add(row['id'])
        ordered.append(row)
    for row in sessions:
        visit(row)
    return ordered


def _restored_session_row(conn, row: dict, mapping: dict, local_sources) -> dict:
    new_row = dict(row)
    new_row['id'] = mapping[row['id']]
    parent = row.get('parent_session_id')
    if parent in mapping:
        new_row['parent_session_id'] = mapping[parent]
    elif parent and not conn.execute('SELECT 1 FROM sessions WHERE id=?', (parent,)).fetchone():
        new_row['parent_session_id'] = None  # the delete orphaned it from a parent that is gone
    model_config = row.get('model_config')
    if isinstance(model_config, str) and model_config:
        try:
            config = json.loads(model_config)
        except ValueError:
            config = None
        if isinstance(config, dict) and config.get('_delegate_from') in mapping:
            config['_delegate_from'] = mapping[config['_delegate_from']]
            new_row['model_config'] = json.dumps(config)
    for column in _ROUTE_COLUMNS:
        if column in new_row:
            new_row[column] = None
    new_row.update({k: v for k, v in _RESET_COLUMNS.items() if k in new_row})
    # A local surface's chat (the gateway labels it ``local``) comes back as that surface's own
    # history row, the form the native resume adopts. Owner stamps other than a Nous account label
    # are dropped with the route: this store's own host owns an unstamped local row.
    created = row.get('created_source')
    if row.get('source') not in local_sources and created in local_sources:
        new_row['source'] = created
    user_id = row.get('user_id')
    if new_row.get('source') in local_sources and not (isinstance(user_id, str) and user_id.startswith('nous:')):
        new_row['user_id'] = None
    title = (row.get('title') or '').strip()
    if title:
        new_row['title'] = _free_title(conn, title)
    return new_row


def _free_title(conn, title: str) -> str:
    candidate, n = title, 1
    while conn.execute('SELECT 1 FROM sessions WHERE title=?', (candidate,)).fetchone():
        n += 1
        candidate = f'{title} (restored)' if n == 2 else f'{title} (restored {n - 1})'
    return candidate


# ── garbage-collector awareness ─────────────────────────────────────────────────────────────────

def trash_media_mentions(conn, references) -> set:
    """Candidate media paths a trashed message mentions (same matching as live transcript rows)."""
    if not references or not _has_tables(conn):
        return set()
    from gateway.session_ingress_media import _history_mentions
    return _history_mentions(conn, references, table=TRASH_MESSAGES_TABLE)


def trash_spillover_rows(conn, sql_filter: str, limit: int):
    """``(content, api_content)`` of trashed messages matching the spillover prefilter."""
    if not _has_tables(conn):
        return []
    return conn.execute(f'SELECT content, api_content FROM {TRASH_MESSAGES_TABLE} WHERE {sql_filter} LIMIT ?',
                        (limit,)).fetchall()
