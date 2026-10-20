"""Tests for /learn — open-ended skill distillation.

Covers the shared prompt builder (agent.learn_prompt.build_learn_prompt) and
the slash-command registry wiring. /learn has no engine and no model tool: it
builds a standards-guided prompt that the live agent runs as a normal turn, so
these are the load-bearing behavior contracts.
"""

from agent.learn_prompt import build_learn_prompt


class TestBuildLearnPrompt:
    def test_embeds_the_user_request_verbatim(self):
        req = "the REST client in ~/projects/acme-sdk, focus on auth"
        prompt = build_learn_prompt(req)
        assert req in prompt


class TestDescriptionLimit:
    def test_default_limit_is_60(self, monkeypatch):
        import hermes_cli.config

        monkeypatch.setattr(hermes_cli.config, "load_config", lambda: {})
        assert "<=60 characters" in build_learn_prompt("a test skill")

    def test_configured_limit_reaches_prompt(self, monkeypatch):
        import hermes_cli.config

        monkeypatch.setattr(
            hermes_cli.config, "load_config", lambda: {"skills": {"description_limit": 100}}
        )
        prompt = build_learn_prompt("a test skill")
        assert "<=100 characters" in prompt
        assert "<=60 characters" not in prompt

    def test_explicit_override(self):
        assert "<=80 characters" in build_learn_prompt("a test skill", description_limit=80)


class TestLearnRegistryWiring:
    def test_learn_is_not_cli_only(self):
        from hermes_cli.commands import resolve_command

        cmd = resolve_command("learn")
        assert cmd is not None and cmd.name == "learn"
        assert not cmd.cli_only
