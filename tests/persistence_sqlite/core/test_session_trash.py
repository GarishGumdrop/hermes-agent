"""Fork change 19: a user delete keeps a restorable copy (``persistence/sqlite/conversation/_store/trash.py``).

A real backend store throughout. Each delete path the user can reach is exercised through the function
its caller uses: ``delete_session`` (``SessionRepository.delete``: gateway ``session.delete``, ``hermes
sessions delete``), ``delete_sessions`` (``delete_many``: dashboard bulk delete) and the canonical
mutation (desktop and dashboard ``DELETE /api/sessions/<id>``). Surfaces go through the
``persistence.session_trash`` door with the store handle.
"""
import json
import time

import pytest

import persistence.session_trash as door
from persistence.sqlite.authority._mutation import mutate_runtime_session
from persistence.sqlite.authority._runtime_ends import begin_runtime_epoch
from persistence.sqlite.conversation._store import trash
from persistence.sqlite.conversation._store.messages import append_message, get_messages
from persistence.sqlite.conversation._store.sessions import (
    _own_profile_name, create_session, delete_empty_sessions, delete_session, delete_session_if_empty,
    delete_sessions, end_session, get_session,
)
from persistence.sqlite.conversation._store.titles import set_session_title
from tests.contracts._scopes import MEDIA_ROOT

_REAL_RETENTION = trash.retention_days


@pytest.fixture()
def store(backend, scope_a, monkeypatch):
    monkeypatch.setattr(trash, 'retention_days', lambda *_: 7.0)
    return backend.open(scope_a)


@pytest.fixture()
def db(store):
    """The store's StoreHolder, shared with its repositories."""
    return store.holder()


def _chat(db, sid, *, title=None, source='desktop', turns=2, **kwargs):
    create_session(db, sid, source=source, **kwargs)
    for n in range(turns):
        append_message(db, sid, role='user', content=f'{sid} question {n}')
        append_message(db, sid, role='assistant', content=f'{sid} answer {n}')
    if title:
        set_session_title(db, sid, title)


def _transcript(db, sid):
    return [(m['role'], m['content']) for m in get_messages(db, sid)]


def _delete(db, sid, **kwargs):
    return delete_session(db, sid, media_root=MEDIA_ROOT, **kwargs)


def _canonical_delete(db, sid):
    epoch = begin_runtime_epoch(db, instance_id='test')
    row = get_session(db, sid)
    return mutate_runtime_session(
        db, epoch=epoch, principal_id='human', session_id=sid, request_id=f'delete-{sid}',
        expected_revision=row['runtime_revision'], expected_generation=row['runtime_generation'],
        operation='delete', payload={})


def test_delete_then_restore_brings_back_the_same_transcript_under_a_new_id(db, store):
    _chat(db, 'a', title='Planning notes')
    before = _transcript(db, 'a')
    assert _delete(db, 'a')
    assert get_session(db, 'a') is None
    [entry] = door.list_trash(store)
    assert entry['root_session_id'] == 'a' and entry['title'] == 'Planning notes'
    assert entry['message_count'] == 4 and entry['expires_at'] > time.time() + 6 * 86400

    restored = door.restore_from_trash(store, session_id='a')
    new_id = restored['session_id']
    assert new_id and new_id != 'a'
    assert _transcript(db, new_id) == before
    assert get_session(db, new_id)['title'] == 'Planning notes'
    assert door.list_trash(store) == []
    # The deleted id stays fenced: nothing can recreate it.
    from persistence.sqlite.authority._runtime_retirement import retired_session
    assert retired_session(db, 'a')


def test_restored_messages_keep_their_ids_and_display_order(db):
    _chat(db, 'a', turns=3)
    with db._read_ctx() as conn:
        before = [tuple(r) for r in conn.execute(
            'SELECT id, display_order, message_uid FROM messages WHERE session_id=? ORDER BY id', ('a',))]
    _delete(db, 'a')
    new_id = trash.restore_from_trash(db, session_id='a')['session_id']
    with db._read_ctx() as conn:
        after = [tuple(r) for r in conn.execute(
            'SELECT id, display_order, message_uid FROM messages WHERE session_id=? ORDER BY id', (new_id,))]
    assert after == before


def test_restored_chat_drops_its_old_route_and_comes_back_as_local_history(db):
    _chat(db, 'a', source='local', user_id='sid:S-1-5-21-1')
    db._execute_write(lambda c: c.execute(
        "UPDATE sessions SET created_source='desktop', session_key='k', chat_id='a', origin_json='{}' WHERE id='a'"))
    _delete(db, 'a')
    new_id = trash.restore_from_trash(db, session_id='a')['session_id']
    row = get_session(db, new_id)
    assert (row['session_key'], row['chat_id'], row['origin_json'], row['user_id']) == (None, None, None, None)
    assert row['source'] == 'desktop'
    from session_rules.legacy_local import validate_legacy_row
    validate_legacy_row(_own_profile_name(db), row)  # the native resume adopts it


def test_restored_desktop_chat_keeps_its_nous_account_label(db):
    _chat(db, 'a', source='desktop', user_id='nous:42')
    _delete(db, 'a')
    row = get_session(db, trash.restore_from_trash(db, session_id='a')['session_id'])
    assert row['user_id'] == 'nous:42'
    from session_rules.legacy_local import validate_legacy_row
    validate_legacy_row(_own_profile_name(db), row)


def test_canonical_desktop_delete_is_restorable(db):
    _chat(db, 'desk', title='Desk chat')
    before = _transcript(db, 'desk')
    _canonical_delete(db, 'desk')
    assert get_session(db, 'desk') is None
    new_id = trash.restore_from_trash(db, session_id='desk')['session_id']
    assert _transcript(db, new_id) == before


def test_repository_delete_and_delete_many_are_trashed(db, store):
    _chat(db, 'r1')
    _chat(db, 'r2')
    _chat(db, 'r3')
    store.sessions.delete('r1', media_root=MEDIA_ROOT)
    store.sessions.delete_many(['r2', 'r3'], media_root=MEDIA_ROOT)
    assert sorted(e['session_count'] for e in door.list_trash(store)) == [1, 2]


def test_bulk_delete_is_one_entry_and_restores_every_session(db):
    _chat(db, 'b1')
    _chat(db, 'b2')
    assert delete_sessions(db, ['b1', 'b2'], media_root=MEDIA_ROOT)[0] == 2
    [entry] = trash.list_trash(db)
    assert entry['session_count'] == 2
    result = trash.restore_from_trash(db, entry['trash_id'])
    assert set(result['session_ids']) == {'b1', 'b2'}
    for old, new in result['session_ids'].items():
        assert _transcript(db, new)[0] == ('user', f'{old} question 0')


def test_compression_chain_and_delegate_children_come_back_linked(db):
    _chat(db, 'root')
    end_session(db, 'root', 'compression')
    _chat(db, 'tip', parent_session_id='root')
    _chat(db, 'kid', source='subagent', parent_session_id='tip',
          model_config={'_delegate_from': 'tip'})
    _delete(db, 'tip', include_compression_chain=True)
    for sid in ('root', 'tip', 'kid'):
        assert get_session(db, sid) is None
    mapping = trash.restore_from_trash(db, session_id='tip')['session_ids']
    assert set(mapping) == {'root', 'tip', 'kid'}
    assert get_session(db, mapping['tip'])['parent_session_id'] == mapping['root']
    kid = get_session(db, mapping['kid'])
    assert kid['parent_session_id'] == mapping['tip']
    assert json.loads(kid['model_config'])['_delegate_from'] == mapping['tip']


def test_title_taken_meanwhile_gets_a_restored_suffix(db):
    _chat(db, 'a', title='Same name')
    _delete(db, 'a')
    _chat(db, 'b', title='Same name')
    new_id = trash.restore_from_trash(db, session_id='a')['session_id']
    assert get_session(db, new_id)['title'] == 'Same name (restored)'


def test_housekeeping_deletes_are_not_trashed(db):
    create_session(db, 'empty', source='desktop')
    end_session(db, 'empty', 'done')
    assert delete_session_if_empty(db, 'empty', media_root=MEDIA_ROOT)
    create_session(db, 'empty2', source='desktop')
    end_session(db, 'empty2', 'done')
    delete_empty_sessions(db, media_root=MEDIA_ROOT)
    assert trash.list_trash(db) == []


def test_an_aborted_delete_leaves_no_trash_entry(db, monkeypatch):
    _chat(db, 'a')
    from persistence.sqlite.conversation._store import retirement

    def boom(*_a, **_k):
        raise RuntimeError('delete aborted')
    monkeypatch.setattr(retirement, 'retire_sessions', boom)
    with pytest.raises(RuntimeError):
        _delete(db, 'a')
    assert get_session(db, 'a') is not None
    assert trash.list_trash(db) == []


def test_entries_expire_after_the_retention_window(db):
    _chat(db, 'old')
    _delete(db, 'old')
    db._execute_write(lambda c: c.execute(
        f'UPDATE {trash.TRASH_TABLE} SET deleted_at = deleted_at - 8 * 86400'))
    _chat(db, 'new')
    _delete(db, 'new')  # the next delete purges what has expired
    assert [e['root_session_id'] for e in trash.list_trash(db)] == ['new']
    with pytest.raises(door.TrashNotFound):
        trash.restore_from_trash(db, session_id='old')


def test_retention_zero_turns_the_trash_off(db, monkeypatch):
    monkeypatch.setattr(trash, 'retention_days', lambda *_: 0.0)
    _chat(db, 'a')
    _delete(db, 'a')
    assert trash.list_trash(db) == []


def test_retention_is_read_from_the_stores_own_profile_config(db, monkeypatch, tmp_path):
    monkeypatch.setattr(trash, 'retention_days', _REAL_RETENTION)
    home = trash.store_home(db)
    assert trash.retention_days(home) == trash.DEFAULT_RETENTION_DAYS
    (home / 'config.yaml').write_text('sessions:\n  trash_retention_days: 0\n', encoding='utf-8')
    assert trash.retention_days(home) == 0
    _chat(db, 'a')
    _delete(db, 'a')
    assert trash.list_trash(db) == []
    assert trash.retention_days(tmp_path / 'elsewhere') == trash.DEFAULT_RETENTION_DAYS


def test_delete_forever_one_and_all(db, store):
    for sid in ('x', 'y', 'z'):
        _chat(db, sid)
        _delete(db, sid)
    entries = {e['root_session_id']: e['trash_id'] for e in door.list_trash(store)}
    assert door.purge_trash(store, entries['x']) == 1
    assert {e['root_session_id'] for e in door.list_trash(store)} == {'y', 'z'}
    assert door.purge_trash(store, everything=True) == 2
    assert door.list_trash(store) == []


def test_trashed_copies_keep_spillover_archives_until_purged(db, store):
    from session_retention import collect_retired_media
    from tools.tool_result_storage import referenced_spillover_names
    home = trash.store_home(db)
    spill_dir = home / 'cache' / 'spillover'
    spill_dir.mkdir(parents=True)
    name = 'abc123.txt'
    (spill_dir / name).write_text('big tool output')
    create_session(db, 's', source='desktop')
    append_message(db, 's', role='user', content='run it')
    append_message(db, 's', role='tool', content=f'<persisted-output path="{(spill_dir / name).as_posix()}">',
                   tool_call_id='t1')
    if name not in (referenced_spillover_names(spill_dir) or set()):
        pytest.skip('spillover pointer format differs from this fixture')
    store.sessions.delete('s', media_root=MEDIA_ROOT)
    collect_retired_media(store, home)  # the delete's post-commit collection
    assert (spill_dir / name).exists()
    assert name in referenced_spillover_names(spill_dir)
    door.purge_trash(store, everything=True)
    collect_retired_media(store, home)
    assert not (spill_dir / name).exists()


def test_trashed_copies_keep_media_the_transcript_mentions(db):
    sha = 'ab' * 32
    ref = {'path': f'C:/media/{sha}/photo.png', 'sha256': sha}
    create_session(db, 'm', source='desktop')
    append_message(db, 'm', role='user', content=f'look at {sha}/photo.png')
    _delete(db, 'm')
    with db._read_ctx() as conn:
        assert trash.trash_media_mentions(conn, [ref]) == {ref['path']}
    from persistence.sqlite.authority._admission_media import unheld_media
    candidates, held = unheld_media(db, [ref], after_id=0, retain_history=True, media_root=MEDIA_ROOT)
    assert candidates == [] and ref['path'] in held
    trash.purge_trash(db, everything=True)
    with db._read_ctx() as conn:
        assert trash.trash_media_mentions(conn, [ref]) == set()


def test_cli_trash_list_restore_purge(db, store, capsys):
    from types import SimpleNamespace
    from hermes_cli.sessions_trash_cmd import cmd_trash
    _chat(db, 'c1', title='CLI chat')
    _delete(db, 'c1')
    assert cmd_trash(store, SimpleNamespace(trash_action='list')) is None
    assert 'CLI chat' in capsys.readouterr().out
    assert cmd_trash(store, SimpleNamespace(trash_action='restore', id='c1')) is None
    assert 'Restored as session' in capsys.readouterr().out
    assert cmd_trash(store, SimpleNamespace(trash_action='restore', id='c1')) == 1
    _chat(db, 'c2')
    _delete(db, 'c2')
    assert cmd_trash(store, SimpleNamespace(trash_action='purge', id=None, purge_all=True)) is None
    assert 'Deleted 1 trashed session forever' in capsys.readouterr().out
