"""Fork change 19: a chat the gateway already owns, deleted and restored, opens again through the real
native resume (``resolve_local_target`` adopts it as local history) with its transcript.

The row starts as the gateway leaves a Desktop chat: adopted, so it has a creation receipt and a
route. The delete runs the canonical mutation the desktop's ``DELETE /api/sessions/<id>`` runs.
"""
import json

import pytest

from tests.fixtures.storage_read import session_row, transcript_rows
from tests.fixtures.storage_seed import seed_messages, seed_session

SID = '20261103_120000_abc123'


@pytest.mark.asyncio
async def test_restored_gateway_chat_is_adopted_again_on_resume(monkeypatch):
    import persistence.session_trash as trash
    from gateway import run
    from gateway.session_contract import SessionRef
    from gateway.session_local_migration import resolve_local_target
    from gateway.session_mutations import mutate_session
    from hermes_constants import get_hermes_home
    from tests.gateway.test_session_follow_profile_config import _owner

    home = get_hermes_home()
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(run, '_hermes_home', home)
    (home / 'config.yaml').write_text(json.dumps(
        {'model': {'default': 'm', 'provider': 'custom', 'base_url': 'http://127.0.0.1:9/v1'}}))
    store, runner, authority, owner = _owner(home)
    runner._peek_session_state = lambda key: None
    db = authority.persistence
    try:
        seed_session(db, SID, 'desktop', cwd=str(home), model='m', end_reason='cli_close')
        seed_messages(db, SID, {'role': 'user', 'content': 'first question'},
                      {'role': 'assistant', 'content': 'first answer'})
        authority._native_legacy_transports = {owner.actor.transport_id: owner.actor}
        resolve_local_target(authority, owner.actor, SID)  # the gateway adopts it: now a routed, owned chat
        assert db.bindings.receipt(SID) is not None
        authority.sessions.pop(SID, None)

        import dataclasses
        actor = dataclasses.replace(owner.actor, capabilities=owner.actor.capabilities | {'session:read', 'session:control'})
        authority._native_legacy_transports = {actor.transport_id: actor}
        row = session_row(db, SID)
        await mutate_session(authority, actor, SessionRef(authority.profile_id, SID), dict(
            session_id=SID, request_id='del-1', expected_revision=row['runtime_revision'],
            expected_generation=row['runtime_generation'], operation='delete', payload={}))
        assert session_row(db, SID) is None

        new_id = trash.restore_from_trash(db, session_id=SID)['session_id']
        resolve_local_target(authority, owner.actor, new_id)  # opens again: adopted under the new id
        assert db.bindings.receipt(new_id) is not None
        assert [m['content'] for m in transcript_rows(db, new_id)] == ['first question', 'first answer']
    finally:
        await owner.close()
        store.close_all_db_handles()
