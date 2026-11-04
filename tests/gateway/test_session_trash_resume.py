"""Fork change 19: a chat the gateway already owns, deleted and restored, opens again through the real
native resume (``resolve_local_target`` adopts it as local history) with its transcript.

The row starts as the gateway leaves a Desktop chat: adopted, so it has a local policy receipt, a
route (``chat_id`` / ``session_key`` / ``origin_json``) and an owner stamp. The delete runs the
canonical mutation the desktop's ``DELETE /api/sessions/<id>`` runs.
"""
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace

from gateway.session_contract import SessionActor

SID = '20261103_120000_abc123'


def test_restored_gateway_chat_is_adopted_again_on_resume(monkeypatch):
    import hermes_state_runtime as rt
    import hermes_state_trash as trash
    from gateway.config import GatewayConfig
    from gateway.session import SessionStore
    from gateway.session_authority import initialize_session_authority
    from gateway.session_local_migration import bind_native_transport, resolve_local_target
    from hermes_state_local import local_receipt

    home = Path(os.environ['HERMES_HOME'])
    home.mkdir(parents=True, exist_ok=True)
    (home / 'config.yaml').write_text('model:\n  default: m\n  provider: custom\n  base_url: http://127.0.0.1:9/v1\n')
    monkeypatch.setattr('gateway.run._hermes_home', home)
    store = SessionStore(home / 'sessions', GatewayConfig())
    runner = SimpleNamespace(session_store=store, _session_db=store._db, adapters={}, _draining=False,
                             _cached_agent_for=lambda route: None, _adapter_for_source=lambda source: None)
    authority = asyncio.run(initialize_session_authority(runner, profile_id=str(home), instance_id='fixture'))
    actor = SessionActor('uid:1000', str(home), frozenset({'session:read', 'session:create'}), 'native')
    bind_native_transport(authority, actor, {'provider': 'local', 'profile_id': str(home), 'instance_id': 'fixture'})
    db = authority.db
    try:
        db.create_session(SID, source='desktop', model='m')
        db.append_message(SID, role='user', content='first question')
        db.append_message(SID, role='assistant', content='first answer')
        db.end_session(SID, 'cli_close')
        resolve_local_target(authority, actor, SID)  # the gateway adopts it: now a routed, owned chat
        assert local_receipt(db, SID) is not None
        authority.sessions.pop(SID, None)

        row = db.get_session(SID)
        rt.mutate_runtime_session(db, epoch=authority.epoch, principal_id='uid:1000', session_id=SID,
                                  request_id='del-1', expected_revision=row['runtime_revision'],
                                  expected_generation=row['runtime_generation'], operation='delete', payload={})
        assert db.get_session(SID) is None

        new_id = trash.restore_from_trash(db, session_id=SID)['session_id']
        resolve_local_target(authority, actor, new_id)  # opens again: adopted under the new id
        assert local_receipt(db, new_id) is not None
        assert [m['content'] for m in db.get_messages(new_id)] == ['first question', 'first answer']
    finally:
        store._db.close()
