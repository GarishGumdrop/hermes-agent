# FORK.md — what this fork changes and why

This is GarishGumdrop's fork of NousResearch/hermes-agent. Every night `scripts/fork_sync.py`
(change 11) merges NousResearch's latest `main` into this fork and reviews the NousResearch commits
that meet one of the changes below. This file is the list that review works from.

**When a NousResearch change meets a fork change**

- **Same change:** NousResearch's version wins. Remove the fork change and move its entry to
  "Retired", naming the NousResearch commit that replaced it.
- **Partial overlap, or the same feature with significantly different behaviour:** keep the fork's
  version, alone (never both side by side), and move the entry to "Pending review" with the
  differences. The user decides; until then the fork's version stays.
- **NousResearch changed code a fork change hooks into:** adapt the fork change to the new code.
- **Anything else:** NousResearch's version. The fork carries no other intentional differences.
- Fork changes stay at the edges: new files where possible, the smallest possible edit where core
  files must be touched.

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

### 11. Nightly merge and review of NousResearch's main

- **Files:** `scripts/fork_sync.py`, `scripts/fork_sync/triage.md`, `scripts/fork_sync/review.md`
  (all new). Task Scheduler's "Hermes Auto Update" runs the script with Hermes's venv python.
- **Purpose:** merges NousResearch's main into the fork; Sonnet reads the new commit titles against
  this file, the user's plugins and his edited built-in skills; flagged items or git conflicts go to
  one session on the user's own model, which applies the rules above. The result is pushed, then
  `hermes update --yes` installs it and the desktop app is reopened if it was open. Each model call's
  cost goes to `<hermes home>/fork-sync/spend.jsonl`. A failure writes `update-hold.json`.
- **If it breaks:** usually `hermes_cli.gateway_chat.run_gateway_chat` or `tools/skills_sync.py`
  changed; adapt the two calls in the script.

### 12. Assistant code blocks wrap long lines instead of scrolling sideways

- **Files:** `apps/desktop/src/components/chat/code-card.tsx` (wrapping
  utilities on `CodeCardBody` pre/code/line); `apps/desktop/src/components/chat/shiki-highlighter.tsx`
  (`PlainCode` wraps); `apps/desktop/src/components/chat/shiki-plain.tsx`
  (`PlainShiki` wraps); `apps/desktop/src/components/chat/shiki-block.tsx`
  (`plainTextHtml` fallback wraps); `apps/desktop/src/components/chat/expandable-block.tsx`
  (horizontal overflow hidden); `apps/desktop/src/styles.css` (code-card
  pre/code/`.shiki`/`.line` wrap rule); `apps/desktop/src/components/assistant-ui/markdown-text.overflow.test.tsx`
  (updated expectations).
- **Purpose:** a long line in an assistant code block ran off the side of the
  card behind a horizontal scroller. Assistant fences now wrap the way user
  fences already do (`whitespace-pre-wrap` + `wrap-anywhere`), so the whole
  block stays readable in the column. Tables keep their own horizontal scroll;
  copy still takes the original text.
- **If it breaks:** upstream probably reshaped the code-card render path. Keep
  the rule: every pre/code path (plain, highlighted, loading and error
  fallbacks) wraps, and the card's scroller never scrolls sideways.

### 13. The /learn prompt uses the configured skill description limit

- **Files:** `agent/learn_prompt.py` (`_AUTHORING_STANDARDS` is a
  `{desc_limit}` template; `build_learn_prompt` takes an optional
  `description_limit`, defaulting to `skill_prompt_desc_limit()`);
  `tests/agent/test_learn_prompt.py` (`TestDescriptionLimit`).
- **Purpose:** the prompt told the drafting agent every new description must
  fit 60 characters, while the user's `skills.description_limit` is 100 and
  the create gate enforces 100 — so /learn cut descriptions down for a limit
  nothing else applied. The prompt now renders the configured limit, like the
  index truncation and the create check already do.
- **If it breaks:** keep the description number in the prompt read from the
  same function as the index truncation, with an explicit override for tests
  and callers.

### 14. Old dependency environments are removed on Windows

- **Files:** `hermes_cli/runtime_state.py` (`collect_generations`,
  `_remove_generation`, `_empty_trash`).
- **Purpose:** uv hard-links every environment's files to one shared copy, and
  Windows refuses to delete any link to a library a running Hermes has loaded.
  The cleaner hit such a file in the first old environment, raised, and gave up
  on all of them, so a ~700 MB environment piled up with every update. Files
  Windows refuses to delete are now moved to `installs/<id>/environments-trash`
  and deleted on a later sweep, and one failing environment no longer stops the
  rest.
- **If it breaks:** keep generation removal tolerant of undeletable mapped
  files on Windows, and keep one failure from aborting the sweep.

## Pending review

### 10. The slash menu updates when skills or plugins change on disk

- **Files:** `tui_gateway/change_watcher.py` (`_skills_sig` and helpers, one `skills.changed` row in
  `_CHANGE_WATCHES`); `tui_gateway/contracts/events.py` (one `event(...)` line) and the two files
  regenerated from it by `scripts/gen_gateway_contracts.py`
  (`apps/shared/src/gateway-contract.generated.ts`, `.openrpc.json`);
  `apps/desktop/src/app/session/hooks/use-message-stream/gateway-event/lifecycle.ts` (a
  `skills.changed` branch and two imports); tests in `tests/tui_gateway/test_fork_skills_changed.py`.
- **Purpose:** the desktop caches the slash-command list for an hour and refreshes it only when a
  skill changes through the app itself (Capabilities, the hub, the `skill_manage` tool). A skill
  installed any other way, e.g. by the agent with curl or git, stayed missing from the `/` menu
  until the app restarted. The backend's change watcher now fingerprints every skills folder
  (own and `skills.external_dirs`, for the active and every served profile), the plugins folder
  and config.yaml every 2 seconds, and broadcasts `skills.changed` when that moves; the desktop
  drops its cached slash list on it. The user requires the menu to follow the available commands
  without a restart.
- **If it breaks:** keep a watcher-side signal over the skill/plugin folders and config, and a
  desktop handler that calls `invalidateSlashCompletions()` on it.
- **Differences (NousResearch 20acba0376, merge a03d7d8a08 / commits 6bcf096ef4, 1f8c6134c2, 9de32e7be9):**
  NousResearch now has its own `skills.changed` broadcast with the same name, used by the terminal
  TUI to refetch its command list. Their signal (`agent.skill_commands.published_scopes_signature`)
  watches the skill folders of every profile and project folder a session has looked up commands
  in, including a project's own `.hermes/skills`. The fork's signal, kept as the only one, also
  watches the plugins folder and every change to config.yaml (quick commands, plugin switches),
  and every served profile even before a session has used it, but not project folders. Their
  version has no Desktop handler; the fork's Desktop handler (drop the cached slash menu) stays.
  Their test `test_a_skill_installed_in_another_sessions_repo_broadcasts_skills_changed` expects
  the project-folder watch the fork's signal does not have, so it carries a one-line skip marker
  naming this entry.

## Retired

### 9. One-shot chats honour `--ignore-rules` and `--safe-mode`

- **Files:** `hermes_cli/oneshot.py` (`_run_agent`: `skip_context_files` / `skip_memory` passed to
  `AIAgent` from `HERMES_IGNORE_RULES`); tests in `tests/hermes_cli/test_fork_oneshot_ignore_rules.py`.
- **Purpose:** `hermes chat --oneshot --ignore-rules` (or `--safe-mode`) still loaded SOUL.md, the
  user profile and memory, because the one-shot path builds its agent without the two switches that
  `hermes chat` and the TUI pass. The nightly update's model sessions run this way and must not
  receive the user's personal rules, which are written for conversations with him.
- **If it breaks:** keep the one-shot agent built with the same skip switches as the interactive chat.
- **Replaced by:** NousResearch 9b89e41e13 (one-shot chats now run through the gateway, which
  receives `--ignore-rules` / `--safe-mode` / `HERMES_IGNORE_RULES` and builds the agent without
  SOUL.md, AGENTS.md and memory). The fork's edit sat in `hermes_cli/oneshot.py`'s in-process path,
  which `hermes -z` no longer uses; it and its test were removed.
