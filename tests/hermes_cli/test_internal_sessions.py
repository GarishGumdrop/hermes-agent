"""Fork change 16: internal sessions (hermes_cli/internal_sessions.py).

One rule decides which saved sessions the human lists leave out; the desktop sidebar gets them
as its own ``internal`` slice with a count, ``sessions.show_internal`` moves them into the main
list, and ``hermes chat`` records what started a session ("Started by").
"""

import json
import sqlite3

import pytest

# The desktop's recents exclusions (SIDEBAR_EXCLUDED_SOURCES, one messaging platform for brevity).
RECENTS_EXCLUDE = "acp,cron,kanban,oneshot,subagent,tool,telegram"


@pytest.fixture(autouse=True)
def _uncached_sidebar(monkeypatch):
    from hermes_cli.web_routers import profiles as profiles_routes

    monkeypatch.setattr(profiles_routes, "_SIDEBAR_CACHE_TTL_SECONDS", 0.0)


@pytest.fixture
def home(monkeypatch, _isolate_hermes_home):
    from hermes_cli import profiles
    from hermes_constants import get_hermes_home

    default_home = get_hermes_home()
    default_home.mkdir(parents=True, exist_ok=True)
    (default_home / "config.yaml").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(profiles, "_get_default_hermes_home", lambda: default_home)
    monkeypatch.setattr(profiles, "_get_profiles_root", lambda: default_home / "profiles")
    return default_home


@pytest.fixture
def client(monkeypatch, home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")
    import hermes_state
    from hermes_cli.web_server import _SESSION_HEADER_NAME, _SESSION_TOKEN, app

    monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", home / "state.db")
    c = TestClient(app)
    c.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    return c


def _seed(home, session_id, *, source="cli", messages=1, title=None, hidden=False, archived=False,
          model_config=None, parent=None):
    from hermes_state import SessionDB

    db = SessionDB(db_path=home / "state.db")
    try:
        db.create_session(session_id, source=source, model_config=model_config, parent_session_id=parent)
        for _ in range(messages):
            db.append_message(session_id=session_id, role="user", content="hi")
        if title:
            assert db.set_session_title(session_id, title)
        if hidden:
            db.set_session_hidden(session_id, True)
        if archived:
            db.set_session_archived(session_id, True)
    finally:
        db.close()


def _seed_every_kind(home):
    _seed(home, "chat", title="A conversation")
    _seed(home, "program", source="tool")
    _seed(home, "command", source="oneshot")
    _seed(home, "bot", source="desktop", title="Bot Chat", hidden=True)
    _seed(home, "empty", source="desktop", messages=0)
    _seed(home, "child", source="subagent", parent="chat", model_config={"_delegate_from": "chat"})
    _seed(home, "cron-run", source="cron")
    _seed(home, "old-program", source="tool", archived=True)


def _sidebar(client, **params):
    query = {"recents_profile": "default", "recents_exclude": RECENTS_EXCLUDE,
             "messaging_exclude": "cli,cron", "internal_limit": 50, **params}
    return client.get("/api/profiles/sessions/sidebar", params=query).json()


def _ids(payload, key):
    return {row["id"] for row in payload[key]["sessions"]}


class TestSidebarInternalSlice:

    def test_lists_and_counts_what_the_main_list_leaves_out(self, client, home):
        _seed_every_kind(home)
        payload = _sidebar(client)
        assert _ids(payload, "recents") == {"chat"}
        assert _ids(payload, "internal") == {"program", "command", "bot", "empty", "child"}
        assert payload["internal"]["total"] == 5
        assert payload["internal"]["shown_in_main"] is False
        # Cron keeps its own section; an archived session is in the archive, not here.
        assert _ids(payload, "cron") == {"cron-run"}
        origins = {row["id"]: row["internal_origin"] for row in payload["internal"]["sessions"]}
        assert origins == {
            "program": "Programs, origin not recorded",
            "command": "One-off commands, origin not recorded",
            "bot": "Bot chats (Bots tab)",
            "empty": "Empty sessions",
            "child": "Subagent runs of \u201cA conversation\u201d",
        }

    def test_switch_moves_internal_sessions_into_the_main_list(self, client, home):
        _seed_every_kind(home)
        (home / "config.yaml").write_text("sessions:\n  show_internal: true\n", encoding="utf-8")
        payload = _sidebar(client)
        assert {"chat", "program", "command", "bot", "empty"} <= _ids(payload, "recents")
        assert not {"cron-run", "old-program"} & _ids(payload, "recents")
        assert payload["internal"] == {"sessions": [], "total": 0, "shown_in_main": True}

    def test_no_internal_slice_unless_asked(self, client, home):
        _seed_every_kind(home)
        assert "internal" not in _sidebar(client, internal_limit=0)


class TestStartedBy:

    def test_headings_name_what_started_each_session(self, home):
        from hermes_cli.internal_sessions import list_internal_sessions
        from hermes_state import SessionDB

        _seed(home, "chat", title="Fix the update")
        _seed(home, "probe", source="oneshot", model_config={"_launched_from": "chat"})
        _seed(home, "orphan", source="oneshot", model_config={"_launched_from": "gone"})
        _seed(home, "nightly", source="tool", model_config={"_launched_by": "Nightly update"})
        _seed(home, "test", source="tool",
              model_config={"_launched_from": "chat", "_launched_by": "Nightly update"})
        db = SessionDB(db_path=home / "state.db")
        try:
            rows = {row["id"]: row for row in list_internal_sessions(db, 50)}
        finally:
            db.close()
        assert rows["probe"]["internal_origin"] == "Started by \u201cFix the update\u201d"
        assert rows["probe"]["launched_from"] == "chat"
        assert rows["probe"]["launched_from_title"] == "Fix the update"
        assert rows["orphan"]["internal_origin"] == "Started by a conversation that was deleted"
        assert rows["nightly"]["internal_origin"] == "Nightly update"
        assert rows["test"]["internal_origin"] == "Started by \u201cFix the update\u201d (Nightly update)"

    def test_recorded_provenance_merges_into_model_config(self, home):
        from hermes_cli.internal_sessions import pop_provenance, record_provenance
        from hermes_state import SessionDB

        _seed(home, "run", source="oneshot", model_config={"_usage_anchor": {"x": 1}})
        params = {"source": "oneshot", "launched_from": "chat-1", "launched_by": "Nightly update"}
        provenance = pop_provenance(params)
        assert params == {"source": "oneshot"}
        db = SessionDB(db_path=home / "state.db")
        try:
            record_provenance(db, "run", provenance)
        finally:
            db.close()
        conn = sqlite3.connect(home / "state.db")
        try:
            stored = json.loads(conn.execute("SELECT model_config FROM sessions WHERE id='run'").fetchone()[0])
        finally:
            conn.close()
        assert stored == {"_usage_anchor": {"x": 1}, "_launched_from": "chat-1", "_launched_by": "Nightly update"}

    def test_invalid_provenance_is_refused(self):
        from hermes_cli.internal_sessions import pop_provenance
        from hermes_state_runtime import RuntimeStoreError

        with pytest.raises(RuntimeStoreError):
            pop_provenance({"launched_by": ""})
        with pytest.raises(RuntimeStoreError):
            pop_provenance({"launched_from": 7})

    def test_client_sends_only_what_the_gateway_advertises(self, monkeypatch):
        from types import SimpleNamespace

        from hermes_cli.internal_sessions import launch_provenance

        monkeypatch.setenv("HERMES_SESSION_ID", "local-abc")
        monkeypatch.delenv("HERMES_LAUNCHED_BY", raising=False)
        args = SimpleNamespace(launched_by="Nightly update")
        assert launch_provenance(args, ["launched_from", "launched_by"]) == {
            "launched_from": "local-abc", "launched_by": "Nightly update"}
        # An older gateway that does not advertise the options is never sent them.
        assert launch_provenance(args, ["title"]) == {}
        monkeypatch.delenv("HERMES_SESSION_ID")
        assert launch_provenance(None, ["launched_from", "launched_by"]) == {}

    def test_real_daemon_records_who_started_each_session(self, tmp_path):
        """Both terminal routes, through a real daemon: the classic CLI (agents' ``hermes chat -q``)
        and the nightly update's titled ``run_gateway_chat`` create."""
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, '-c',
            'import json,sys; from pathlib import Path; '
            'from tests.gateway.fixtures.launch_provenance_probe import probe; '
            'print(json.dumps(probe(Path(sys.argv[1]))))', str(tmp_path)], cwd=root,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=300, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        rows = json.loads(result.stdout.splitlines()[-1])
        assert rows["started"] == {"source": "oneshot", "title": None, "launched_from": "parent-session-1",
                                   "launched_by": "Probe program"}
        assert rows["plain"]["source"] == "oneshot"
        assert rows["plain"]["launched_from"] is None and rows["plain"]["launched_by"] is None
        assert rows["nightly"] == {"source": "tool", "title": "Nightly update 1 Jan 01:00: triage",
                                   "launched_from": None, "launched_by": "Nightly update"}


class TestOtherLists:

    def test_project_view_and_terminal_follow_the_same_rule(self, home):
        from hermes_cli.internal_sessions import (
            INTERNAL_SESSION_SOURCES,
            project_tree_scope,
            terminal_list_scope,
        )

        assert set(project_tree_scope(home)["exclude_sources"]) == {"cron", *INTERNAL_SESSION_SOURCES}
        assert set(terminal_list_scope(None)["exclude_sources"]) == set(INTERNAL_SESSION_SOURCES)
        assert terminal_list_scope("tool") == {"exclude_sources": None}
        (home / "config.yaml").write_text("sessions:\n  show_internal: true\n", encoding="utf-8")
        assert project_tree_scope(home)["exclude_sources"] == ["cron"]
        assert terminal_list_scope(None)["include_hidden"] is True

    def test_terminal_note_counts_what_was_left_out(self, home):
        from hermes_cli.internal_sessions import terminal_list_note
        from hermes_state import SessionDB

        _seed_every_kind(home)
        db = SessionDB(db_path=home / "state.db")
        try:
            note = terminal_list_note(db, None)
            assert note and note.startswith("5 internal sessions not listed")
            assert terminal_list_note(db, "tool") is None
        finally:
            db.close()
