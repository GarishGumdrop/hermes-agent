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
