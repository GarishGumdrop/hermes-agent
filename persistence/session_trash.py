"""Fork change 19 (GarishGumdrop/hermes-agent): the door to the session trash (undo for deletes).

Surfaces outside ``persistence/`` (the web routes, ``hermes sessions trash``) may not name the
SQLite backend, so they come through here with the storage interface handle they already hold
(``open_persistence`` / ``open_persistence_reader``, or the gateway's own ``authority.persistence``).
The trash itself, and the snapshot each user delete takes, live in the backend
(``persistence.sqlite.conversation._store.trash``).
"""
from __future__ import annotations

from typing import Optional

from persistence.sqlite.conversation._store import trash as _trash

TrashNotFound = _trash.TrashNotFound
DEFAULT_RETENTION_DAYS = _trash.DEFAULT_RETENTION_DAYS


def _holder(store):
    """The backend holder behind a storage handle: a ``Persistence`` handle forwards only the
    storage interface, so its bound store is asked."""
    bound = getattr(store, '_bound_store', None)
    return (bound() if callable(bound) else store).holder()


def retention_days(home=None) -> float:
    """``sessions.trash_retention_days`` of the profile at *home* (default: the active one)."""
    if home is None:
        from hermes_constants import get_hermes_home
        home = get_hermes_home()
    return _trash.retention_days(home)


def store_retention_days(store) -> float:
    """``sessions.trash_retention_days`` of the profile *store* serves (the config beside its file,
    as the delete's snapshot reads it)."""
    return _trash.retention_days(_trash.store_home(_holder(store)))


def list_trash(store, *, purge: bool = True) -> list[dict]:
    """Restorable entries, newest first. With ``purge`` (and a writable handle) expired entries are
    deleted first; either way they are left out of the list."""
    if purge and getattr(store, 'read_only', False) is False:
        try:
            purge_trash(store)
        except Exception:  # health: allow BLE001 -- listing must not fail on a purge hiccup
            pass
    return _trash.list_trash(_holder(store))


def restore_from_trash(store, trash_id: Optional[str] = None, *, session_id: Optional[str] = None) -> dict:
    """Undo a delete under new ids (see ``_store.trash.restore_from_trash``). Raises :class:`TrashNotFound`."""
    return _trash.restore_from_trash(_holder(store), trash_id, session_id=session_id)


def purge_trash(store, trash_id: Optional[str] = None, *, everything: bool = False) -> int:
    """Delete forever: one entry, every entry (``everything``), or (neither) only expired ones.
    Releases the media and archives the purged copies were keeping. Returns entries removed."""
    removed = _trash.purge_trash(_holder(store), trash_id, everything=everything)
    if removed:
        from session_retention import collect_retired_media
        # The folder the store's file is in (where the archives sit), as the delete's snapshot reads it.
        collect_retired_media(store, _trash.store_home(_holder(store)))
    return removed
