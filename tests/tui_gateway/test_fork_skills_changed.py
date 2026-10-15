"""Fork change 10: ``skills.changed`` fires when the slash menu's inputs move on disk.

A skill installed from a terminal (curl, git clone, a copy) never goes through the
desktop's own install paths, so the desktop only learns of it from this signal.
"""

import os
import time

import pytest

from tui_gateway import server


@pytest.fixture()
def watcher_home(tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text("display: {}\n")
    (tmp_path / "skills").mkdir()

    monkeypatch.setattr(server, "_hermes_home", str(tmp_path))
    monkeypatch.setattr(server, "_cfg_cache", None)
    monkeypatch.setattr(server, "_change_sigs", {})
    monkeypatch.setattr(server, "_change_checked_at", {})
    monkeypatch.setattr(server, "_change_broadcast_at", {})
    monkeypatch.setattr(server, "_bot_relay_outbox_seen", 0)
    monkeypatch.setattr(server, "_pairing_roots_cache", None, raising=False)
    monkeypatch.setattr(server, "_sessions_db_sig_cache", {})
    monkeypatch.setattr(server, "_skills_ext_cache", {})
    monkeypatch.setattr(server, "_served_profile_homes", set())

    events = []
    monkeypatch.setattr(
        server, "_broadcast_global_event", lambda ev, payload=None: events.append((ev, payload))
    )
    return tmp_path, events


def _bump(path):
    """Push mtime forward so coarse filesystem clocks still register a move."""
    t = time.time() + 5
    os.utime(path, (t, t))


def _skill(base, name):
    d = base / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n")
    _bump(base)
    return d


def _skills_events(events):
    return [e for e in events if e[0] == "skills.changed"]


def test_new_skill_broadcasts_skills_changed(watcher_home):
    home, events = watcher_home
    server._broadcast_watched_changes(now=0.0)
    assert _skills_events(events) == []

    _skill(home / "skills", "bro")
    server._broadcast_watched_changes(now=10.0)

    assert _skills_events(events) == [("skills.changed", {})]


def test_skill_in_category_and_edit_broadcast(watcher_home):
    home, events = watcher_home
    (home / "skills" / "media").mkdir()
    server._broadcast_watched_changes(now=0.0)

    d = _skill(home / "skills" / "media", "gif")
    server._broadcast_watched_changes(now=10.0)
    assert len(_skills_events(events)) == 1

    os.utime(d / "SKILL.md", (time.time() + 60, time.time() + 60))  # an edit
    server._broadcast_watched_changes(now=20.0)
    assert len(_skills_events(events)) == 2


def test_external_dir_is_watched(watcher_home, tmp_path_factory):
    home, events = watcher_home
    ext = tmp_path_factory.mktemp("shared-skills")
    (home / "config.yaml").write_text(f"skills:\n  external_dirs:\n    - {ext.as_posix()}\n")
    server._broadcast_watched_changes(now=0.0)

    _skill(ext, "shared")
    server._broadcast_watched_changes(now=10.0)

    assert _skills_events(events) == [("skills.changed", {})]


def test_served_profile_skills_are_watched(watcher_home, monkeypatch):
    home, events = watcher_home
    prof = home / "profiles" / "ike"
    (prof / "skills").mkdir(parents=True)
    (prof / "config.yaml").write_text("{}\n")
    monkeypatch.setattr(server, "_served_profile_homes", {prof})
    server._broadcast_watched_changes(now=0.0)

    _skill(prof / "skills", "bro")
    server._broadcast_watched_changes(now=10.0)

    assert _skills_events(events) == [("skills.changed", {})]


def test_unrelated_files_do_not_broadcast(watcher_home):
    home, events = watcher_home
    server._broadcast_watched_changes(now=0.0)

    (home / "notes.txt").write_text("x")
    (home / "logs").mkdir()
    server._broadcast_watched_changes(now=10.0)

    assert _skills_events(events) == []
