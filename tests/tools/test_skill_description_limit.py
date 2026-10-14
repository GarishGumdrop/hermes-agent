"""skills.description_limit: configurable index budget, enforced on creates before staging."""

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
    monkeypatch.setenv("HERMES_HOME", h)
    import importlib

    import tools.skill_manager_tool as smt
    importlib.reload(smt)
    yield smt
    shutil.rmtree(h, ignore_errors=True)


def _cfg(skills):
    return patch("hermes_cli.config.load_config", return_value={"skills": skills})


def test_default_limit_is_60():
    from agent.skill_utils import extract_skill_description, skill_prompt_desc_limit
    with _cfg({}):
        assert skill_prompt_desc_limit() == 60
        assert extract_skill_description({"description": "x" * 80}) == "x" * 57 + "..."


def test_configured_limit_widens_index_and_create(home):
    from agent.skill_utils import extract_skill_description
    desc = "Use when asked to play, queue or choose music; not for podcasts or audiobooks."
    assert 60 < len(desc) <= 100
    with _cfg({"description_limit": 100}):
        assert extract_skill_description({"description": desc}) == desc
        out = json.loads(home.skill_manage(action="", name="", operations=[
            {"action": "create", "name": "probe", "content": SK.format(n="probe", d=desc)}]))
    assert out["success"], out


def test_too_long_create_is_refused_before_staging(home):
    import tools.write_approval as wa
    desc = "Use when " + "y" * 120 + "."
    with _cfg({"write_approval": True, "description_limit": 100}), \
         patch.object(wa, "stage_write") as stage:
        out = json.loads(home.skill_manage(action="", name="", operations=[
            {"action": "create", "name": "probe", "content": SK.format(n="probe", d=desc)}]))
    assert not out["success"] and "Not staged" in out["error"] and "100-char" in out["error"]
    stage.assert_not_called()


def test_valid_create_still_stages(home):
    import tools.write_approval as wa
    with _cfg({"write_approval": True}), \
         patch.object(wa, "stage_write", return_value={"id": "p1"}) as stage:
        out = json.loads(home.skill_manage(action="", name="", operations=[
            {"action": "create", "name": "probe", "content": SK.format(n="probe", d="Use when probing.")}]))
    assert out.get("staged"), out
    stage.assert_called_once()
