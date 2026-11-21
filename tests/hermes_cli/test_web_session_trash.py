"""Fork change 19: the desktop's delete -> Undo round trip over the real REST routes.

``DELETE /api/sessions/<id>`` is what the desktop sends (canonical mutation through the session
authority); ``/api/sessions/trash*`` are the Undo / Recently deleted routes.
"""
from types import SimpleNamespace

import pytest

from tests.fixtures.storage_read import session_row, transcript_rows
from tests.fixtures.storage_seed import seed_messages, seed_session
from tests.gateway.fixtures.storage_handles import storage_handle


@pytest.fixture
def client(monkeypatch, _isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")
    from gateway.session_authority import SessionAuthority
    from hermes_constants import get_hermes_home
    from hermes_cli.web_server import _SESSION_HEADER_NAME, _SESSION_TOKEN, app

    home = get_hermes_home()
    store = storage_handle(home)
    authority = SessionAuthority(SimpleNamespace(_draining=False), profile_id=str(home), instance_id="test-owner",
                                 epoch=store.runtime.begin_epoch(instance_id="test-owner"), persistence=store)
    monkeypatch.setattr(app.state, "session_authority", authority, raising=False)
    http = TestClient(app)
    http.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    yield SimpleNamespace(http=http, owner=authority, store=store, home=home)


def _seed(store, sid, title):
    seed_session(store, sid, "desktop", title=title)
    seed_messages(store, sid, {"role": "user", "content": "what is the plan?"},
                  {"role": "assistant", "content": "here is the plan"})


def _desktop_delete(c, sid):
    from gateway.session_authority import LiveSession
    c.owner.sessions[sid] = LiveSession(None, "route")
    row = session_row(c.store, sid)
    return c.http.delete(f"/api/sessions/{sid}", params=dict(
        request_id=f"del-{sid}", expected_revision=row["runtime_revision"],
        expected_generation=row["runtime_generation"]))


def test_desktop_delete_then_undo_round_trip(client):
    _seed(client.store, "s1", "Trip plan")
    resp = _desktop_delete(client, "s1")
    assert resp.status_code == 200, resp.text
    assert session_row(client.store, "s1") is None

    listing = client.http.get("/api/sessions/trash")
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["retention_days"] == 7
    [entry] = body["entries"]
    assert entry["title"] == "Trip plan" and "s1" in entry["session_ids"]

    undo = client.http.post("/api/sessions/trash/restore", json={"session_id": "s1"})
    assert undo.status_code == 200, undo.text
    new_id = undo.json()["session_id"]
    assert new_id and new_id != "s1"
    assert [m["content"] for m in transcript_rows(client.store, new_id)] == ["what is the plan?", "here is the plan"]
    assert client.http.get("/api/sessions/trash").json()["entries"] == []


def test_undo_twice_is_a_clean_404(client):
    _seed(client.store, "s2", "Once")
    assert _desktop_delete(client, "s2").status_code == 200
    assert client.http.post("/api/sessions/trash/restore", json={"session_id": "s2"}).status_code == 200
    again = client.http.post("/api/sessions/trash/restore", json={"session_id": "s2"})
    assert again.status_code == 404 and again.json()["detail"] == "not_in_trash"


def test_delete_forever(client):
    _seed(client.store, "s3", "Gone")
    assert _desktop_delete(client, "s3").status_code == 200
    [entry] = client.http.get("/api/sessions/trash").json()["entries"]
    resp = client.http.post("/api/sessions/trash/purge", json={"trash_id": entry["trash_id"]})
    assert resp.status_code == 200 and resp.json()["removed"] == 1
    assert client.http.get("/api/sessions/trash").json()["entries"] == []


def test_trash_routes_work_while_the_gateway_owns_the_store(client, monkeypatch):
    """The desktop's backend is ``hermes gateway run``: the web routes run inside the gateway, which
    holds the profile's owner lock, so they must use the gateway's own store handle (a second writer
    is refused there with 409 and the list came back empty)."""
    from gateway.runtime_ownership import ProfileOwnership
    from hermes_cli.web_server import app

    monkeypatch.setattr(app.state, "gateway_runner", SimpleNamespace(session_authority=client.owner), raising=False)
    lock = ProfileOwnership()
    lock.reserve([client.home])  # what the running gateway holds
    try:
        _seed(client.store, "g1", "Owned chat")
        _seed(client.store, "g2", "Owned chat 2")
        assert _desktop_delete(client, "g1").status_code == 200
        assert _desktop_delete(client, "g2").status_code == 200

        listing = client.http.get("/api/sessions/trash")
        assert listing.status_code == 200, listing.text
        titles = {e["title"]: e["trash_id"] for e in listing.json()["entries"]}
        assert set(titles) == {"Owned chat", "Owned chat 2"}

        undo = client.http.post("/api/sessions/trash/restore", json={"session_id": "g1"})
        assert undo.status_code == 200, undo.text
        assert session_row(client.store, undo.json()["session_id"])["title"] == "Owned chat"

        purge = client.http.post("/api/sessions/trash/purge", json={"trash_id": titles["Owned chat 2"]})
        assert purge.status_code == 200, purge.text
        assert client.http.get("/api/sessions/trash").json()["entries"] == []
    finally:
        lock.release(client.home)
