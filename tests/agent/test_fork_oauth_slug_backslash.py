"""Fork change 8: the OAuth slug rewrite must leave Windows backslash paths intact."""
from agent.anthropic_adapter import _OAUTH_SLUG_PATTERN


def _rewrite(text: str) -> str:
    return _OAUTH_SLUG_PATTERN.sub("claude-code", text)


def test_backslash_path_is_not_rewritten():
    path = r"C:\Users\me\AppData\Local\hermes\hermes-agent\venv"
    assert _rewrite(path) == path
    assert _rewrite(r"checkout at C:\x\hermes\hermes-agent of the fork") == r"checkout at C:\x\hermes\hermes-agent of the fork"


def test_prose_and_forward_slash_behaviour_unchanged():
    assert _rewrite("Load the hermes-agent skill.") == "Load the claude-code skill."
    assert _rewrite("~/.hermes/hermes-agent/venv") == "~/.hermes/hermes-agent/venv"
    assert _rewrite("NousResearch/hermes-agent") == "NousResearch/hermes-agent"
