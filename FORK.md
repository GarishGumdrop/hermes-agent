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
- **Decided by the user:** a Pending review entry he has settled goes back to "Changes" with a
  **Decided** line naming the NousResearch commits it was compared with. That difference with those
  commits never sends it back; a later NousResearch change in the same area is reviewed as usual.
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
  (all new). Task Scheduler's "Hermes Auto Update" runs the script through Hermes's launcher
  (`.hermes\bin\hermes.exe --run-module scripts.fork_sync --from-task`, falling back to
  `hermes.CMD` where that is what the install published) inside
  `powershell.exe -NoExit`, so its progress window stays open until the user closes it. The task's
  multiple-instances policy is Parallel, so an open window never blocks the next night's run; an OS
  lock (`fork-sync/run.lock`) stops a second run while one is in progress.
- **Purpose:** merges NousResearch's main into the fork; Sonnet reads the new commit titles against
  this file, the user's plugins and his edited built-in skills; flagged items or git conflicts go to
  one session on the user's own model, which applies the rules above. The result is pushed, then
  `hermes update --yes` installs it and the desktop app is reopened if it was open. Each model call's
  cost goes to `<hermes home>/fork-sync/spend.jsonl`. A failure writes `update-hold.json`.
- **Reliability rules (each fixes a failure seen on 2026-10-22):** the launcher builds the Python
  environment for changed lock files before any session starts (a session process gets only 60
  seconds to start, too little for a build). Model calls retry both models for about 10 minutes.
  Child steps use Hermes's own environment Python (`hermes_python()`), never `sys.executable`.
  Install problems (`hermes update` exits 0 even when the desktop build fails) and a report that
  could not be written become notes in `update-notes.json`; nothing fails silently.
- **If it breaks:** usually `hermes_cli.gateway_chat.run_gateway_chat`, `pm.environments.committed_venv`
  or `tools/skills_sync.py` changed; adapt the calls in the script.
- **Its sessions (change 16):** every model session is titled "Nightly update <day> <month> <HH:MM>:
  <step>" (", attempt N" from the second attempt) and records `launched_by` "Nightly update"; the
  run ends with `cleanup()`, which deletes `tool` and `oneshot` sessions inactive for longer than
  `sessions.internal_retention_days` (default 30, 0 = keep; pinned and archived ones are kept) one
  by one with `hermes sessions delete` (prune cannot: it deletes only ended sessions, and gateway
  sessions started by `run_gateway_chat` never end), and puts every outcome in the report.

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
- **Decided (26 Oct 2026):** the user keeps the fork's wrapping over NousResearch's sideways
  scrolling (7ac4cf552c, cce9f40c67, 394793b4d8). That difference is settled and does not send
  this entry back to Pending review; a later NousResearch change to code-block layout is reviewed
  as usual.
- **Differences (NousResearch 7ac4cf552c, cce9f40c67, 394793b4d8):** upstream
  keeps sideways scrolling for code: native Desktop sizes the fence to its own
  width and scrolls long lines inside it, and browser-hosted Desktop sizes the
  fence to its longest line (`min-w-max`) so the card scrolls sideways in place
  with a fade at the cut edge. The fork, kept as the only version, wraps every
  fence instead and hides the card's horizontal scroller, so no code scrolls
  sideways anywhere. Their scroll expectations and browser-host test were
  removed; only the fork's wrap test stays.

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

### 16. Internal sessions are listed, labelled and cleaned up instead of silently hidden

- **Files:**
  - Rule and lists: `hermes_cli/internal_sessions.py` (new: what counts as internal, the Internal
    section's rows and count, the `sessions.show_internal` switch, "Started by" recording);
    `hermes_cli/web_routers/profiles.py` (sidebar endpoint: `internal_limit` / `internal_token`, the
    `internal` slice, recents scope from `main_list_scope`); `tui_gateway/methods_projects.py`
    (project view, `project_tree_scope`); `hermes_cli/sessions_cmd.py` (`hermes sessions list`,
    `terminal_list_scope`, and a line saying how many it left out); `hermes_cli/cli_session_mixin.py`
    and `hermes_cli/console_engine.py` (`/resume` and console lists, `internal_exclusions`);
    `hermes_cli/config_defaults.py` (`sessions.show_internal`, `sessions.internal_retention_days`);
    `tui_gateway/methods_config_set.py` (config.set accepts `sessions.show_internal`).
  - Started by: `tui_gateway/contracts/canonical_sessions.py` (`launched_from`, `launched_by` on
    `CanonicalCreateParams`, regenerated into `apps/shared/src/gateway-contract.generated.ts` and
    `.openrpc.json` by `scripts/gen_gateway_contracts.py`); `gateway/session_controls.py` (`_create`
    takes them out of the launch request and writes them to the new session's model_config as
    `_launched_from` / `_launched_by`; `describe` advertises them); `hermes_cli/gateway_chat.py` and
    `hermes_cli/gateway_session_store.py` (both client routes send them, only when advertised).
  - Desktop: `apps/desktop/src/fork/internal-sessions/` (new: `store.ts`, `group.ts`,
    `section.tsx`); hooks in `src/api/sessions.ts` (request and response fields),
    `src/app/session/hooks/use-session-list-actions.ts` (asks for and stores the slice; refreshes when
    the switch flips), `src/app/chat/sidebar/sessions-section.tsx` (`grouping: 'origin'`) and
    `src/app/chat/sidebar/index.tsx` (mounts the section after Cron jobs).
  - Nightly update: `scripts/fork_sync.py` (see change 11).
  - Tests: `tests/hermes_cli/test_internal_sessions.py`, `tests/gateway/fixtures/launch_provenance_probe.py`
    (a real daemon and both client routes).
- **Purpose:** Hermes saves every model session, and each list (sidebar, project view, terminal
  lists, session search) hid a different set of them without saying so, while nothing recorded what
  started a session. Now one rule decides what is internal: sources `tool`, `oneshot`, `subagent`,
  `kanban`, `acp`; hidden rows (Bot Mode); empty rows; subagent runs. Cron keeps its own section. The
  sidebar shows internal sessions in an "Internal sessions" section with their count, grouped under
  what started them; the section's switch (`sessions.show_internal`) lists them in the main lists
  instead; `hermes sessions list` says how many it left out. `hermes chat` records the conversation
  whose agent ran the command (`HERMES_SESSION_ID`) and a program's own name (`HERMES_LAUNCHED_BY`, or
  `launched_by` on the arguments).
- **If it breaks:** usually NousResearch changed the sidebar endpoint's slices, the arguments of
  `list_sessions_rich`, the `session.create` contract or a client's creation path. Keep: one rule in
  `internal_sessions.py` used by every list; the `internal` slice and its count; both provenance
  fields in the closed create contract (a client that sends a field the contract lacks is refused);
  both client routes sending them only when the gateway advertises them.

### 17. Windows updates refresh the computer-use driver unless a logon task needs UAC

- **Files:** `hermes_cli/update_cmd_maint.py` (`_refresh_cua_driver_after_update`, its `win32`
  branch); tests in `tests/hermes_cli/test_update_cua_pm.py` (the three Windows tests).
- **Purpose:** on Windows, `hermes update` printed "cua-driver refresh deferred (autostart
  registration requires UAC)" on every run where the driver was installed, without checking
  anything, so the nightly report carried it every night. NousResearch wrote it (5e4a2a3d24) when
  every install registered the `cua-driver-serve` logon task. Since 959c7649fd (#97389) that task is
  opt-in (`computer_use.autostart`) and the default registers nothing. Now, with the task off, the
  update installs a new pinned driver unelevated, as on Linux, and says nothing when the pin is
  already installed. With the task on, it defers, and says so, only when the pin is new or the task
  does not target it.
- **If it breaks:** keep three outcomes on Windows. Task off: `pm.ensure` when the pin is outdated,
  silence when it is installed. Task on and registered for the installed pin: silence. Task on
  otherwise: the deferral notice, never an unattended UAC prompt.

## Pending review

### 7. Configurable skill description length, checked before a new skill is staged

- **Files:** `agent/skill_utils.py` (`skill_prompt_desc_limit()`, `clip_skill_description()`
  with a limit parameter, used by the index truncation); `tools/skill_manager_tool.py`
  (`_description_budget_error` in `_guarded_write`, `_staged_create_error` in `_run_write_gate`,
  limit in the create check and the tool description); `tools/skill_linter.py`;
  `hermes_cli/config_defaults.py` (`skills.description_limit`); docs in
  `website/docs/user-guide/features/skills.md`; tests in
  `tests/tools/test_skill_description_limit.py`.
- **Purpose:** the user's limit is 100 characters (default 60), so each skill's line can say when
  not to use it. A new skill that would fail on approval (too-long description, bad name, bad
  frontmatter) is refused when proposed, so the author fixes it and the user never approves
  something that then fails. The tool description states the real limit.
- **If it breaks:** keep the limit read from config in one function; the budget check must run on
  every write that reaches the root SKILL.md (that is where NousResearch put it); and the create
  checks must keep running before a skill write is staged.
- **Differences (NousResearch 3a3bf5648e, df92e33081, b66ab2bb7b):** upstream enforces a fixed
  60 characters — the write-time budget check, the index clip width, the tool description and the
  authoring-standards test all hard-code 60, and over-long index descriptions are clipped at a word
  boundary (any whitespace counts). The fork keeps one configurable limit instead
  (`skills.description_limit`, default 60, the user's is 100): the budget check, the clip width,
  the linter, the tool description and /learn all read it, so at 100 the fork accepts and shows
  descriptions upstream would refuse or clip. The fork's code follows upstream's new structure
  (one budget check in `_guarded_write`, so it also covers explicit `SKILL.md` file paths; word
  boundary clipping), with the fixed 60 swapped for the configured limit.

### 10. The slash menu updates when skills or plugins change on disk

- **Files:** `tui_gateway/change_watcher.py` (`_skills_sig` and helpers, one `skills.changed` row in
  `_CHANGE_WATCHES`); `tui_gateway/contracts/events.py` (one `event(...)` line) and the two files
  regenerated from it by `scripts/gen_gateway_contracts.py`
  (`apps/shared/src/gateway-contract.generated.ts`, `.openrpc.json`);
  `apps/desktop/src/app/session/hooks/use-message-stream/gateway-event/lifecycle.ts` (a
  `skills.changed` branch and one import, `invalidateSlashCompletions`; the second call,
  `invalidateSkillSuggestionIndex`, was removed after NousResearch deleted
  `apps/desktop/src/store/suggestion-providers/` in 833cfc607a, which broke every desktop
  build from 2026-10-22); tests in `tests/tui_gateway/test_fork_skills_changed.py`.
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

### 15. Security update for the eMudhra CA key compromise

- **Files:** `pm/lock.json` (node, uv, python pins; the Termux node row stays on
  26.4.0 and the Termux python row on 3.14.6 until Termux publishes newer builds).
- **Purpose:** the private keys of eight eMudhra intermediate CAs were compromised
  (emudhra.we-have-a-problem.com, 2026-10-20). The fork pinned node 26.12.1, uv
  0.13.4 and python 3.14.9 ahead of NousResearch; the certifi part already matched
  NousResearch's #142679 and was theirs.
- **Replaced by:** NousResearch e09f04499a (node 26.12.1), e31fa4cab9 (python
  3.14.9) and 75a8d6fcf4 (uv 0.13.5, plus regenerated bootstrap pins in
  `scripts/install.sh` / `scripts/install.ps1`). One row is still the fork's:
  the Termux uv row stays at 0.13.4, because NousResearch's bump left the Termux
  row on 0.12.23 and the Termux pool prunes old builds. Never move any of these
  pins, or certifi, back below node 26.12.1, uv 0.13.4, python 3.14.9.

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
