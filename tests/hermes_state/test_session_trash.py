"""Fork change 19: a user delete keeps a restorable copy (``hermes_state_trash``).

Real ``SessionDB`` throughout. Each delete path the user can reach is exercised through the function
its caller uses: ``delete_session`` (gateway ``session.delete``, ``hermes sessions delete``),
``delete_sessions`` (dashboard bulk delete) and the canonical mutation (desktop and dashboard
``DELETE /api/sessions/<id>``).
"""
import json
import time

import pytest

import hermes_state_runtime as rt
import hermes_state_trash as trash
from hermes_state import SessionDB


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(trash, 'retention_days', lambda: 7.0)
    session_db = SessionDB(db_path=tmp_path / 'state.db')
    yield session_db
    session_db.close()


def _chat(db, sid, *, title=None, source='desktop', turns=2, **kwargs):
    db.create_session(sid, source=source, **kwargs)
    for n in range(turns):
        db.append_message(sid, role='user', content=f'{sid} question {n}')
        db.append_message(sid, role='assistant', content=f'{sid} answer {n}')
    if title:
        db.set_session_title(sid, title)


def _transcript(db, sid):
    return [(m['role'], m['content']) for m in db.get_messages(sid)]


def _canonical_delete(db, sid):
    epoch = rt.begin_runtime_epoch(db, instance_id='test')
    row = db.get_session(sid)
    return rt.mutate_runtime_session(
        db, epoch=epoch, principal_id='human', session_id=sid, request_id=f'delete-{sid}',
        expected_revision=row['runtime_revision'], expected_generation=row['runtime_generation'],
        operation='delete', payload={})


def test_delete_then_restore_brings_back_the_same_transcript_under_a_new_id(db):
    _chat(db, 'a', title='Planning notes')
    before = _transcript(db, 'a')
    assert db.delete_session('a')
    assert db.get_session('a') is None
    [entry] = trash.list_trash(db)
    assert entry['root_session_id'] == 'a' and entry['title'] == 'Planning notes'
    assert entry['message_count'] == 4 and entry['expires_at'] > time.time() + 6 * 86400

    restored = trash.restore_from_trash(db, session_id='a')
    new_id = restored['session_id']
    assert new_id and new_id != 'a'
    assert _transcript(db, new_id) == before
    assert db.get_session(new_id)['title'] == 'Planning notes'
    assert trash.list_trash(db) == []
    # The deleted id stays fenced: nothing can recreate it.
    from hermes_state_mutation_retirement import retired_session
    assert retired_session(db, 'a')


def test_restored_messages_keep_their_ids_and_display_order(db):
    _chat(db, 'a', turns=3)
    with db._read_ctx() as conn:
        before = [tuple(r) for r in conn.execute(
            'SELECT id, display_order, message_uid FROM messages WHERE session_id=? ORDER BY id', ('a',))]
    db.delete_session('a')
    new_id = trash.restore_from_trash(db, session_id='a')['session_id']
    with db._read_ctx() as conn:
        after = [tuple(r) for r in conn.execute(
            'SELECT id, display_order, message_uid FROM messages WHERE session_id=? ORDER BY id', (new_id,))]
    assert after == before


def test_restored_chat_drops_its_old_route_and_comes_back_as_local_history(db):
    _chat(db, 'a', source='local', user_id='sid:S-1-5-21-1')
    db._execute_write(lambda c: c.execute(
        "UPDATE sessions SET created_source='desktop', session_key='k', chat_id='a', origin_json='{}' WHERE id='a'"))
    db.delete_session('a')
    new_id = trash.restore_from_trash(db, session_id='a')['session_id']
    row = db.get_session(new_id)
    assert (row['session_key'], row['chat_id'], row['origin_json'], row['user_id']) == (None, None, None, None)
    assert row['source'] == 'desktop'
    from hermes_state_local_migration import validate_legacy_row
    validate_legacy_row(db, row)  # the native resume adopts it


def test_canonical_desktop_delete_is_restorable(db):
    _chat(db, 'desk', title='Desk chat')
    before = _transcript(db, 'desk')
    _canonical_delete(db, 'desk')
    assert db.get_session('desk') is None
    new_id = trash.restore_from_trash(db, session_id='desk')['session_id']
    assert _transcript(db, new_id) == before


def test_bulk_delete_is_one_entry_and_restores_every_session(db):
    _chat(db, 'b1')
    _chat(db, 'b2')
    assert db.delete_sessions(['b1', 'b2']) == 2
    [entry] = trash.list_trash(db)
    assert entry['session_count'] == 2
    result = trash.restore_from_trash(db, entry['trash_id'])
    assert set(result['session_ids']) == {'b1', 'b2'}
    for old, new in result['session_ids'].items():
        assert _transcript(db, new)[0] == ('user', f'{old} question 0')


def test_compression_chain_and_delegate_children_come_back_linked(db):
    _chat(db, 'root')
    db.end_session('root', 'compression')
    _chat(db, 'tip', parent_session_id='root')
    _chat(db, 'kid', source='subagent', parent_session_id='tip',
          model_config={'_delegate_from': 'tip'})
    db.delete_session('tip', include_compression_chain=True)
    for sid in ('root', 'tip', 'kid'):
        assert db.get_session(sid) is None
    mapping = trash.restore_from_trash(db, session_id='tip')['session_ids']
    assert set(mapping) == {'root', 'tip', 'kid'}
    assert db.get_session(mapping['tip'])['parent_session_id'] == mapping['root']
    kid = db.get_session(mapping['kid'])
    assert kid['parent_session_id'] == mapping['tip']
    assert json.loads(kid['model_config'])['_delegate_from'] == mapping['tip']


def test_title_taken_meanwhile_gets_a_restored_suffix(db):
    _chat(db, 'a', title='Same name')
    db.delete_session('a')
    _chat(db, 'b', title='Same name')
    new_id = trash.restore_from_trash(db, session_id='a')['session_id']
    assert db.get_session(new_id)['title'] == 'Same name (restored)'


def test_housekeeping_deletes_are_not_trashed(db):
    db.create_session('empty', source='desktop')
    db.end_session('empty', 'done')
    assert db.delete_session_if_empty('empty')
    db.create_session('empty2', source='desktop')
    db.end_session('empty2', 'done')
    db.delete_empty_sessions()
    assert trash.list_trash(db) == []


def test_an_aborted_delete_leaves_no_trash_entry(db, monkeypatch):
    _chat(db, 'a')
    import hermes_state_mutation_retirement as retirement

    def boom(*_a, **_k):
        raise RuntimeError('delete aborted')
    monkeypatch.setattr(retirement, 'retire_sessions', boom)
    with pytest.raises(RuntimeError):
        db.delete_session('a')
    assert db.get_session('a') is not None
    assert trash.list_trash(db) == []


def test_entries_expire_after_the_retention_window(db, monkeypatch):
    _chat(db, 'old')
    db.delete_session('old')
    db._execute_write(lambda c: c.execute(
        f'UPDATE {trash.TRASH_TABLE} SET deleted_at = deleted_at - 8 * 86400'))
    _chat(db, 'new')
    db.delete_session('new')  # the next delete purges what has expired
    assert [e['root_session_id'] for e in trash.list_trash(db)] == ['new']
    with pytest.raises(trash.TrashNotFound):
        trash.restore_from_trash(db, session_id='old')


def test_retention_zero_turns_the_trash_off(db, monkeypatch):
    monkeypatch.setattr(trash, 'retention_days', lambda: 0.0)
    _chat(db, 'a')
    db.delete_session('a')
    assert trash.list_trash(db) == []


def test_delete_forever_one_and_all(db):
    for sid in ('x', 'y', 'z'):
        _chat(db, sid)
        db.delete_session(sid)
    entries = {e['root_session_id']: e['trash_id'] for e in trash.list_trash(db)}
    assert trash.purge_trash(db, entries['x']) == 1
    assert {e['root_session_id'] for e in trash.list_trash(db)} == {'y', 'z'}
    assert trash.purge_trash(db, everything=True) == 2
    assert trash.list_trash(db) == []


def test_trashed_copies_keep_spillover_archives_until_purged(db, tmp_path):
    from tools.tool_result_storage import referenced_spillover_names
    spill_dir = tmp_path / 'cache' / 'spillover'
    spill_dir.mkdir(parents=True)
    name = 'abc123.txt'
    (spill_dir / name).write_text('big tool output')
    db.create_session('s', source='desktop')
    db.append_message('s', role='user', content='run it')
    db.append_message('s', role='tool', content=f'<persisted-output path="{spill_dir / name}">',
                      tool_call_id='t1')
    if name not in (referenced_spillover_names(spill_dir) or set()):
        pytest.skip('spillover pointer format differs from this fixture')
    db.delete_session('s')
    assert (spill_dir / name).exists()
    assert name in referenced_spillover_names(spill_dir)
    trash.purge_trash(db, everything=True)
    assert not (spill_dir / name).exists()


def test_trashed_copies_keep_media_the_transcript_mentions(db):
    sha = 'ab' * 32
    ref = {'path': f'C:/media/{sha}/photo.png', 'sha256': sha}
    db.create_session('m', source='desktop')
    db.append_message('m', role='user', content=f'look at {sha}/photo.png')
    db.delete_session('m')
    with db._read_ctx() as conn:
        assert trash.trash_media_mentions(conn, [ref]) == {ref['path']}
    trash.purge_trash(db, everything=True)
    with db._read_ctx() as conn:
        assert trash.trash_media_mentions(conn, [ref]) == set()


def test_cli_trash_list_restore_purge(db, capsys):
    from types import SimpleNamespace
    from hermes_cli.sessions_trash_cmd import cmd_trash
    _chat(db, 'c1', title='CLI chat')
    db.delete_session('c1')
    assert cmd_trash(db, SimpleNamespace(trash_action='list')) is None
    assert 'CLI chat' in capsys.readouterr().out
    assert cmd_trash(db, SimpleNamespace(trash_action='restore', id='c1')) is None
    assert 'Restored as session' in capsys.readouterr().out
    assert cmd_trash(db, SimpleNamespace(trash_action='restore', id='c1')) == 1
    _chat(db, 'c2')
    db.delete_session('c2')
    assert cmd_trash(db, SimpleNamespace(trash_action='purge', id=None, purge_all=True)) is None
    assert 'Deleted 1 trashed session forever' in capsys.readouterr().out
