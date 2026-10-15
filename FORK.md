# FORK.md — what this fork changes and why

This is GarishGumdrop's fork of NousResearch/hermes-agent. The nightly update
(`X:\Projects\hermes-fork-sync\nightly.ps1`) combines NousResearch's latest
`main` with this fork every night. When the two clash, a model resolves the
clash using this file as the statement of what each fork change is for.

**Rules for resolving a clash**

- Each change below must keep doing what its "Purpose" says after the merge.
  If NousResearch moved or renamed the code it hooks into, adapt the fork
  change to the new code; do not drop it.
- For everything else, prefer NousResearch's version. The fork carries no other
  intentional differences; anything else that differs is a mistake.
- Keep fork changes at the edges: new files where possible, the smallest
  possible edit where core files must be touched.

## Changes

### 1. Agent access to desktop settings and plugin switches

- **Files:** `apps/desktop/src/fork/agent-settings.ts` (new file);
  two lines in `apps/desktop/index.html` that load it as a second module entry.
- **Purpose:** publishes `window.hermesAgentSettings`, which lets the agent
  read and change every simple setting on the desktop Settings pages, and switch
  desktop plugins on or off, through the app's own setter for each. The user's
  desktop-settings-bridge plugin
  (github.com/GarishGumdrop/hermes-desktop-settings-bridge) relays the agent's
  requests to it. The user requires that Hermes can change its own settings
  when told to in plain English.
- **If it breaks:** usually a store in `apps/desktop/src/store/` was renamed or
  its setter changed. Update the import and the table entry; keep the setting.

### 2. Agent screenshots of the app window

- **Files:** `apps/desktop/electron/fork/window-capture.ts` (new file); in
  `apps/desktop/electron/main.ts`, one import line and the one line
  `registerForkWindowCapture()` next to the `hermes:capturePreview` handler; in
  `apps/desktop/electron/preload.ts`, the `exposeInMainWorld('hermesFork', ...)`
  block at the end of the file.
- **Purpose:** lets the agent take a screenshot of the Hermes Desktop window
  (`window.hermesFork.captureWindow()` saves a PNG and returns its path). The
  desktop-settings-bridge plugin relays the agent's request (`bridge.py
  screenshot`). It never moves focus or restores a minimised window.
- **If it breaks:** keep the registration call anywhere in main.ts that runs at
  startup before windows open, and keep the preload block after the app's own
  `exposeInMainWorld('hermesDesktop', ...)` call.

### 3. High-contrast override for the light theme

- **Files:** `apps/desktop/public/high-contrast-override.css` (new file); one
  `<link rel="stylesheet">` line in `apps/desktop/index.html`.
- **Purpose:** the user has weak eyesight. The stylesheet raises text contrast
  and removes faint grey text in the light theme. It must load after the app's
  own styles so it wins.


### 4. Separate approval switch for edits to existing skills

- **Files:** `tools/write_approval.py` (`EDITS_CONFIG_KEY`, `skill_edit_approval_enabled`,
  `skill_review_enabled`, `skill_gate_key`, the `skill_actions` branch of
  `evaluate_gate`); `tools/skill_manager_tool.py` (`_run_write_gate` takes the
  write's actions); one argument in `tools/skill_manager_batch.py`; the
  `/skills` state line in `hermes_cli/write_approval_commands.py`; the gate-off
  checks in `gateway/slash_commands.py` and `tui_gateway/methods_tools.py`;
  docs in `website/docs/user-guide/features/skills.md` and `configuration.md`;
  tests in `tests/tools/test_skill_manage_batch.py`.
- **Purpose:** `skills.write_approval` holds writes that create or delete a
  skill; the new `skills.write_approval_edits` holds edits to existing skills.
  Unset, the edits switch follows `write_approval`, so standard behaviour is
  unchanged. The user runs `write_approval: true`, `write_approval_edits:
  false`: he reviews only new skills, which show what Hermes thinks is worth a
  skill, and is not shown technical revisions.
- **If it breaks:** upstream probably changed how the skill gate is called.
  Keep the rule: a skill write is held only if one of its actions falls under a
  switch that is on (create/delete → `write_approval`, everything else →
  `write_approval_edits`).

### 5. Approval prompt for every computer-use screen capture

- **Files:** `tools/computer_use/tool.py` (`capture_approval_enabled`, `_capture_needs_approval`, the
  `capture` scope in `handle_computer_use`, capture wording in `_request_approval`); `tools/approval.py`
  (`ignore_bypass` on `_run_approval_gate`); `model_tools.py` (`_rewrite_computer_use`);
  `hermes_cli/config_defaults.py` (`computer_use.capture_approval`, and `skills.write_approval_edits`
  from change 4); docs in `website/docs/user-guide/features/computer-use.md`; tests in
  `tests/tools/test_computer_use_capture_approval.py`.
- **Purpose:** with `computer_use.capture_approval: true`, a screen-control capture always shows
  the approve/deny prompt, even though the user runs with approvals off. A capture sends his desktop
  to the model; he wants that only with his say-so, enforced by Hermes rather than by rules in text.
  The tool description tells the model so. In-app screenshots (browser tool, Hermes window capture)
  do not go through computer_use and are unaffected. Off by default: standard behaviour unchanged.
- **If it breaks:** upstream probably reshaped the approval gate or the computer_use dispatcher. Keep
  the rule: captures (and `capture_after`) are gated when the setting is on, and that gate is not
  skipped by yolo or approvals-off.

### 6. Background reviewer: do not record searches, unscoped check rules, or standing rules

- **Files:** `agent/background_review.py` (three bullets in `_DO_NOT_CAPTURE_BLOCK`, shared by the
  skill and combined review prompts).
- **Purpose:** the reviewer turned the agent's wide searches and "verify everything" reactions into
  standing procedure, which made later sessions sweep logs, other conversations and whole test
  suites. It now records findings, not searches; check rules only with a named target; and nothing
  that SOUL.md, the profile or memory already say.
- **If it breaks:** keep the three bullets in whatever block lists what the reviewer must not capture.

### 7. Configurable skill description length, checked before a new skill is staged

- **Files:** `agent/skill_utils.py` (`skill_prompt_desc_limit()`, used by the index truncation);
  `tools/skill_manager_tool.py` (`_staged_create_error` in `_run_write_gate`, limit in the create
  check and the tool description); `tools/skill_linter.py`; `hermes_cli/config_defaults.py`
  (`skills.description_limit`); docs in `website/docs/user-guide/features/skills.md`; tests in
  `tests/tools/test_skill_description_limit.py`.
- **Purpose:** the user's limit is 100 characters (default 60), so each skill's line can say when
  not to use it. A new skill that would fail on approval (too-long description, bad name, bad
  frontmatter) is refused when proposed, so the author fixes it and the user never approves
  something that then fails. The tool description states the real limit.
- **If it breaks:** keep the limit read from config in one function, and the create checks running
  before a skill write is staged.

### 8. Subscription-login name rewrite leaves Windows paths alone

- **Files:** `agent/anthropic_adapter.py` (`_OAUTH_SLUG_PATTERN`: a backslash added to both
  character classes, plus one comment line); tests in `tests/agent/test_fork_oauth_slug_backslash.py`.
- **Purpose:** on a Claude subscription login, Hermes rewrites the word "hermes-agent" to
  "claude-code" in the model's instructions. Upstream skips paths written with `/` but not Windows
  paths written with `\`, so the model read `...\hermes\hermes-agent` as `...\hermes\claude-code`,
  a folder that does not exist, and repeated the wrong path to the user.
- **If it breaks:** keep a backslash in whatever set of characters marks "this is part of a path,
  do not rewrite".
