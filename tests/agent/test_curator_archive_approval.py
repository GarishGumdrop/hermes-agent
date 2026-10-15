"""curator.archive_approval: the inactivity archive becomes a proposal the user approves or rejects."""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    (home / "skills").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    import tools.skill_usage as usage
    importlib.reload(usage)
    from agent import curator
    importlib.reload(curator)
    from tools import write_approval as wa
    monkeypatch.setattr(usage, "_prune_builtins_enabled", lambda: False)
    monkeypatch.setattr(curator, "_load_config", lambda: {"archive_approval": True})
    return {"home": home, "c": curator, "u": usage, "wa": wa}


def _skill(env, name: str, days_idle: int):
    d = env["home"] / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n", encoding="utf-8")
    u = env["u"]
    ts = (datetime.now(UTC) - timedelta(days=days_idle)).isoformat()
    data = u.load_usage()
    data[name] = u._empty_record()
    data[name].update(created_by="agent", created_at=ts, last_used_at=ts, last_activity_at=ts, use_count=1)
    u.save_usage(data)
    return d


def _pending(env):
    wa = env["wa"]
    return [r for r in wa.list_pending(wa.SKILLS) if r["payload"].get("action") == "archive"]


def test_proposes_instead_of_archiving_and_does_not_repeat(env):
    d = _skill(env, "old-thing", 200)
    counts = env["c"].apply_automatic_transitions()
    assert d.exists(), "nothing is archived without approval"
    assert counts["proposed"] == 1 and counts["archived"] == 0
    [rec] = _pending(env)
    assert rec["payload"] == {"action": "archive", "name": "old-thing"}
    assert "200 days" in rec["plain_summary"] and "restore" in rec["plain_summary"]
    env["c"].apply_automatic_transitions()
    assert len(_pending(env)) == 1, "a waiting proposal is not staged twice"


def test_approval_archives_recoverably(env):
    d = _skill(env, "old-thing", 200)
    env["c"].apply_automatic_transitions()
    [rec] = _pending(env)
    from tools.skill_manager_tool import apply_skill_pending
    out = json.loads(apply_skill_pending(rec["payload"]))
    assert out["success"], out
    assert not d.exists()
    assert env["u"].load_usage()["old-thing"]["state"] == env["u"].STATE_ARCHIVED
    env["wa"].discard_pending(env["wa"].SKILLS, rec["id"])
    counts = env["c"].apply_automatic_transitions()
    assert counts["kept"] == 0, "an approved archive is not mistaken for a rejection"


def test_rejection_keeps_the_skill_and_stops_asking(env):
    d = _skill(env, "old-thing", 200)
    env["c"].apply_automatic_transitions()
    [rec] = _pending(env)
    env["wa"].discard_pending(env["wa"].SKILLS, rec["id"])  # what "reject" does
    counts = env["c"].apply_automatic_transitions()
    assert counts["kept"] == 1
    assert env["u"].load_usage()["old-thing"]["pinned"] is True
    assert d.exists() and not _pending(env)
    env["c"].apply_automatic_transitions()
    assert not _pending(env), "never proposed again"


def test_off_by_default_archives_as_before(env, monkeypatch):
    monkeypatch.setattr(env["c"], "_load_config", dict)
    d = _skill(env, "old-thing", 200)
    counts = env["c"].apply_automatic_transitions()
    assert counts["archived"] == 1 and not d.exists() and not _pending(env)
