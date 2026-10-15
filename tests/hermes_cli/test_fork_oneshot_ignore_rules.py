"""Fork: ``hermes chat --oneshot --ignore-rules`` (and ``--safe-mode``) must skip SOUL.md, AGENTS.md
and memory, as ``hermes chat`` and the TUI already do. The oneshot path builds its AIAgent directly,
so the flag has to be forwarded there too."""

import pytest


def _run(monkeypatch, ignore_rules: bool) -> dict:
    import hermes_cli.oneshot as oneshot_mod

    captured = {}

    class _FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def __setattr__(self, name, _value):
            pass

        def run_conversation(self, _prompt, conversation_history=None):
            return {"final_response": "pong", "session_id": "s"}

        def close(self):
            pass

    if ignore_rules:
        monkeypatch.setenv("HERMES_IGNORE_RULES", "1")
    else:
        monkeypatch.delenv("HERMES_IGNORE_RULES", raising=False)
    cfg = {"model": {"default": "claude-x", "provider": "anthropic"}}
    monkeypatch.setattr(oneshot_mod, "_create_session_db_for_oneshot", lambda: None)
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: cfg)
    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        lambda **kw: {
            "api_key": "k",
            "base_url": None,
            "provider": "anthropic",
            "api_mode": "anthropic_messages",
            "credential_pool": None,
        },
    )
    monkeypatch.setattr(
        "hermes_cli.tools_config._get_platform_tools", lambda _cfg, _p: []
    )
    monkeypatch.setattr(
        "hermes_cli.mcp_startup.ensure_mcp_discovery_before_agent_build",
        lambda **_kw: None,
    )
    monkeypatch.setattr("run_agent.AIAgent", _FakeAgent)

    text, _ = oneshot_mod._run_agent("Health check: reply pong.")
    assert text == "pong"
    return captured


@pytest.mark.parametrize("ignore_rules", [True, False])
def test_oneshot_forwards_ignore_rules(monkeypatch, ignore_rules):
    captured = _run(monkeypatch, ignore_rules)
    assert captured["skip_context_files"] is ignore_rules
    assert captured["skip_memory"] is ignore_rules
