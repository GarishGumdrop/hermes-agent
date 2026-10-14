"""computer_use.capture_approval: every screen capture asks the user, even with approvals off."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _state(monkeypatch):
    from tools.computer_use import tool as cu

    cu.reset_backend_for_tests()
    backend = cu._NoopBackend()
    monkeypatch.setattr(cu, "_new_backend", lambda permission_mode: backend)
    monkeypatch.setenv("HERMES_INTERACTIVE", "1")
    yield backend
    cu.set_approval_callback(None)
    cu.reset_backend_for_tests()


def _run(cfg, args, answer="deny", approval_mode="off"):
    from tools.computer_use import tool as cu

    asked = []

    def prompt(command, description, **kw):
        asked.append(description)
        return answer

    cu.set_approval_callback(prompt)
    with patch("hermes_cli.config.load_config", return_value={"computer_use": cfg}), \
         patch("tools.approval_context._get_approval_mode", return_value=approval_mode):
        out = cu.handle_computer_use(args, session_id="cap-approval")
    return asked, out


def test_capture_is_free_by_default(_state):
    asked, _ = _run({}, {"action": "capture"})
    assert asked == []
    assert [c[0] for c in _state.calls] == ["capture"]


def test_capture_asks_even_with_approvals_off(_state):
    asked, out = _run({"capture_approval": True}, {"action": "capture", "app": "Spotify"})
    assert asked == ["Allow computer_use to capture the screen?"]
    assert "error" in json.loads(out)
    assert _state.calls == []  # denied: the screen was never captured


def test_approved_capture_runs(_state):
    asked, _ = _run({"capture_approval": True}, {"action": "capture"}, answer="once")
    assert len(asked) == 1
    assert [c[0] for c in _state.calls] == ["capture"]


def test_capture_after_on_input_is_gated(_state):
    asked, _ = _run({"capture_approval": True}, {"action": "click", "element": 1, "capture_after": True})
    # approvals off: the click itself is not asked about, its screenshot is
    assert asked == ["Allow computer_use to capture the screen?"]
    assert _state.calls == []


def test_listing_windows_is_not_a_capture(_state):
    asked, _ = _run({"capture_approval": True}, {"action": "list_windows"})
    assert asked == []


def test_schema_description_follows_the_setting():
    import model_tools
    from tools.computer_use.schema import COMPUTER_USE_SCHEMA

    td = {"type": "function", "function": {**COMPUTER_USE_SCHEMA, "name": "computer_use"}}
    with patch("hermes_cli.config.load_config", return_value={"computer_use": {"capture_approval": True}}):
        desc = model_tools._rewrite_computer_use(td, set())["function"]["parameters"]["properties"]["action"]["description"]
    assert "approval prompt every time" in desc and "is free" not in desc
    with patch("hermes_cli.config.load_config", return_value={}):
        assert model_tools._rewrite_computer_use(td, set()) is td
