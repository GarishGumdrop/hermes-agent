"""Fork change 7: a create that would fail on approval is refused before it is staged.

The limit itself is NousResearch's ``skills.index_desc_limit`` (tests/tools/test_skill_manager_tool.py).
"""

import json
import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

SK = "---\nname: {n}\ndescription: {d}\n---\n# Probe\nStep 1.\n"


@pytest.fixture()
def home(monkeypatch):
    h = tempfile.mkdtemp(prefix="desclimit_")
    os.makedirs(os.path.join(h, "skills"))
    with open(os.path.join(h, "config.yaml"), "w", encoding="utf-8") as f:
        f.write("skills:\n  index_desc_limit: 100\n")
    monkeypatch.setenv("HERMES_HOME", h)
    import importlib

    import tools.skill_manager_tool as smt
    importlib.reload(smt)
    yield smt
    shutil.rmtree(h, ignore_errors=True)


def _gate_on():
    return patch("hermes_cli.config.load_config", return_value={"skills": {"write_approval": True}})


def test_too_long_create_is_refused_before_staging(home):
    import tools.write_approval as wa
    desc = "Use when " + "y" * 120 + "."
    with _gate_on(), patch.object(wa, "stage_write") as stage:
        out = json.loads(home.skill_manage(action="", name="", operations=[
            {"action": "create", "name": "probe", "content": SK.format(n="probe", d=desc)}]))
    assert not out["success"] and "Not staged" in out["error"] and "100-char" in out["error"]
    stage.assert_not_called()


def test_bad_name_create_is_refused_before_staging(home):
    import tools.write_approval as wa
    with _gate_on(), patch.object(wa, "stage_write") as stage:
        out = json.loads(home.skill_manage(action="", name="", operations=[
            {"action": "create", "name": "Bad Name", "content": SK.format(n="x", d="Use when probing.")}]))
    assert not out["success"] and "Not staged" in out["error"]
    stage.assert_not_called()


def test_valid_create_still_stages(home):
    import tools.write_approval as wa
    with _gate_on(), patch.object(wa, "stage_write", return_value={"id": "p1"}) as stage:
        out = json.loads(home.skill_manage(action="", name="", operations=[
            {"action": "create", "name": "probe", "content": SK.format(n="probe", d="Use when probing.")}]))
    assert out.get("staged"), out
    stage.assert_called_once()
