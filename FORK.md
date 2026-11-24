# FORK.md — what this fork changes and why

This is GarishGumdrop's fork of NousResearch/hermes-agent. When the user asks for an update, the
agent in that conversation merges NousResearch's latest `main` into this fork and reviews the
NousResearch commits that meet one of the changes below (procedure: skill `hermes-local-install`).
This file is the list that review works from.

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
- Window translucency (`windowTranslucency`, `windowFade`,
  `windowTranslucencyMode`) is included and sets light and dark together. Since
  change 18 they cannot make anything see-through; they stay so the keys still
  resolve.
- Desktop theme (`theme`, any installed theme name, read live from
  `listAllThemes`) and `themeMode` (light/dark/system) go through
  `requestTheme`/`requestMode` in `apps/desktop/src/themes/request.ts`, read back
  with `committedTheme` and `modePref` from `themes/context.tsx`. If those are
  renamed, re-point the two table entries to the new imperative theme setters.

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

### 3. The curator asks before archiving an unused skill

- **Files:** `agent/curator.py` (`archive_approval_enabled`, `_load_proposals` / `_save_proposals`,
  `_settle_proposals`, `_propose_archive`, the `approval` branch of the inactivity archive);
  `tools/skill_manager_tool.py` (the `archive` handler `_archive_approved`, not in the tool schema);
  `tools/write_approval.py` (`plain_summary` on `stage_write`, the `archive` gist);
  `hermes_cli/config_defaults.py` (`curator.archive_approval`); tests in
  `tests/agent/test_curator_archive_approval.py`. Added 15 Oct 2026 (6506fd9934); this entry was
  missing from this file until 14 Nov 2026.
- **Purpose:** with `curator.archive_approval: true` (the user's setting), the curator no longer
  archives a skill on its own after a period of disuse: it stages the archive as a pending skill
  write with a plain reason, and the user approves or rejects it. A rejected proposal pins the
  skill so it is kept and never proposed again. Off by default: standard behaviour unchanged.
- **If it breaks:** usually NousResearch moved the curator's inactivity pass (since d4c073d9ab its
  interval gate lives in `agent/idle_schedule.py`) or reshaped `stage_write` / the skill pending
  replay. Keep: the automatic inactivity archive goes through the pending queue when the switch is
  on; an approved proposal replays as the `archive` action; a vanished proposal for a skill that
  still exists pins it.

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

### 16. Internal sessions are listed and labelled instead of silently hidden

- **Files:**
  - Rule and lists: `hermes_cli/internal_sessions.py` (what counts as internal, the Internal
    section's rows and count, the `sessions.show_internal` switch, "Started by" recording); the
    query behind it in the storage layer: `persistence/sqlite/conversation/_store/internal_sessions.py`
    (new), exposed as `SessionRepository.list_internal` / `count_internal`
    (`persistence/conversation/sessions.py` protocol, `persistence/sqlite/conversation/sessions.py`);
    `hermes_cli/web_routers/profiles.py` (sidebar endpoint: `internal_limit` / `internal_token`, the
    `internal` slice, recents scope from `main_list_scope`); `tui_gateway/methods_projects.py`
    (project view, `project_tree_scope`); `hermes_cli/sessions_cmd.py` (`hermes sessions list`,
    `terminal_list_scope`, and a line saying how many it left out); `hermes_cli/cli_session_mixin.py`
    and `hermes_cli/console_engine.py` (`/resume` and console lists, `internal_exclusions`, in place
    of NousResearch's `INTERNAL_LISTING_SOURCES` there); `hermes_cli/config_defaults.py`
    (`sessions.show_internal`); `tools/session_search_tool.py` (`_hidden_session_sources`);
    `tui_gateway/methods_config_set.py` (config.set accepts `sessions.show_internal`).
  - Started by: `tui_gateway/contracts/canonical_sessions.py` (`launched_from`, `launched_by` on
    `CanonicalCreateParams`, regenerated into `apps/shared/src/gateway-contract.generated.ts` and
    `.openrpc.json` by `scripts/gen_gateway_contracts.py`); `gateway/session_controls.py` (`_create`
    takes them out of the launch request and writes them to the new session's model_config as
    `_launched_from` / `_launched_by`; `describe` advertises them); `hermes_cli/gateway_chat.py` and
    `hermes_cli/gateway_session_store.py` (both client routes send them, only when advertised; in the
    store's `session.create` params builder).
  - Desktop: `apps/desktop/src/fork/internal-sessions/` (new: `store.ts`, `group.ts`,
    `section.tsx`); hooks in `src/api/sessions.ts` (request and response fields),
    `src/app/session/hooks/use-session-list-actions.ts` (asks for and stores the slice; refreshes when
    the switch flips), `src/app/chat/sidebar/sessions-section.tsx` (`grouping: 'origin'`) and
    `src/app/chat/sidebar/index.tsx` (mounts the section after Cron jobs).
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
- **If it breaks:** usually NousResearch changed the sidebar endpoint's slices, the session query
  types (`SessionQuery`, `SessionCountQuery`, `list_sessions`), the `session.create` contract or a
  client's creation path. Keep: one rule in `internal_sessions.py` used by every list; the Internal
  query inside the storage layer (the backend-import guard, `scripts/ci/check_backend_imports.py`,
  refuses SQLite access outside `persistence/`); the `internal` slice and its count; both provenance
  fields in the closed create contract (a client that sends a field the contract lacks is refused);
  both client routes sending them only when the gateway advertises them.
- **Ported 21 Nov 2026** onto NousResearch's storage interface after be3d6affc8 removed the old
  session store (`hermes_state_*`).
- **Reviewed 14 Nov 2026 against NousResearch d0b49116ec** (`client {name, version}` on
  `session.create`): their label is a client's self-declared identity for plugins and
  `session.info`, kept only inside the frozen launch request and never shown in a list. The fork's
  `launched_from` / `launched_by` are a stored record shown as "Started by". Different features;
  both fields sit side by side in `CanonicalCreateParams`.

### 17. Windows updates refresh the computer-use driver unless a logon task needs UAC

- **Files:** `hermes_cli/update_cmd_maint.py` (`_refresh_cua_driver_after_update`, its `win32`
  branch); tests in `tests/hermes_cli/test_update_cua_pm.py` (the three Windows tests).
- **Purpose:** on Windows, `hermes update` printed "cua-driver refresh deferred (autostart
  registration requires UAC)" on every run where the driver was installed, without checking
  anything, so every update's output carried it. NousResearch wrote it (5e4a2a3d24) when
  every install registered the `cua-driver-serve` logon task. Since 959c7649fd (#97389) that task is
  opt-in (`computer_use.autostart`) and the default registers nothing. Now, with the task off, the
  update installs a new pinned driver unelevated, as on Linux, and says nothing when the pin is
  already installed. With the task on, it defers, and says so, only when the pin is new or the task
  does not target it.
- **If it breaks:** keep three outcomes on Windows. Task off: `pm.ensure` when the pin is outdated,
  silence when it is installed. Task on and registered for the installed pin: silence. Task on
  otherwise: the deferral notice, never an unattended UAC prompt.

### 18. Nothing in Hermes is ever see-through

- **Files:** `apps/shared/src/translucency.ts` (the `NO_SEE_THROUGH` constant
  and the lines marked `FORK (no see-through)` in `translucencySupportedOn`,
  `glassSupportedOn`, `normalizeState`, `defaultTranslucencyState`,
  `resolveTranslucency`, `windowOpacityFor`, `glassActive`);
  `apps/desktop/src/fork/no-see-through.ts` (new file); two lines in
  `apps/desktop/index.html` that load it.
- **Purpose:** the user requires that no part of the Hermes interface can be
  see-through, by any setting, theme, skin, default or person. Upstream ships
  translucency ON by default (intensity 29, per light/dark appearance), so
  switching theme flipped the window to a different, still-translucent
  appearance slot, and the skin CSS that hid blur/scrims only applied while
  that one skin was active. Now the shared module answers "opaque" to every
  caller (main-process window opacity, Windows/macOS backdrop, renderer glass
  surfaces, HUD frost), the Window Translucency setting is hidden on every OS,
  and the in-page sheet removes blur, semi-transparent panels/menus/scrims,
  message-bubble transparency and the unfocused-chat fade under every theme.
  It also covers fills mixed from a surface colour towards transparent
  (`bg-[color-mix(in_srgb,var(--dt-card)_72%,transparent)]` on the `/`, `@`
  and `+` menus, `composerPanelCard` in `components/chat/composer-dock.ts`)
  and the message box's `--composer-fill` (80-88% in `styles.css`).
  That sheet sits in a randomly named cascade layer kept first in `<head>`, so
  no theme, skin or plugin CSS can override it, however specific.
- **If it breaks:** never resolve a clash by dropping a `NO_SEE_THROUGH`
  guard. If upstream renames or splits these functions, put the guard on
  whatever now decides native window opacity, the window backdrop/material and
  the resolved intensity. If upstream adds a new translucency path (a new
  setting, material or CSS surface), lock it the same way. Keep the
  no-see-through script loaded from `index.html`.

### 7. A new skill that would fail on approval is refused before it is staged

- **Files:** `tools/skill_manager_tool.py` (`_staged_create_error`, called in `_run_write_gate` before
  `stage_write`); tests in `tests/tools/test_skill_description_limit.py`.
- **Purpose:** with `skills.write_approval` on, a new skill whose name, category, frontmatter,
  description length or size would fail when the user approves it is refused when proposed, so the
  author fixes it and the user never approves something that then fails. The check runs the same
  validators the create runs, including NousResearch's `_description_budget_error`.
- **If it breaks:** keep the create checks running on every create in a staged write before
  `stage_write`.
- **Limit part replaced (21 Nov 2026 merge):** the configurable description limit this entry used to
  carry (`skills.description_limit`, `skill_prompt_desc_limit()`, the clip width, linter and tool
  description) is now NousResearch's own: `skills.index_desc_limit` / `get_skill_desc_limit()`
  (1bcad483e1, ee57e22d18), which reads one configured limit everywhere. The fork's limit code was
  removed. The user's 100 was moved to `skills.index_desc_limit`. (Earlier: **Decided 3 Nov 2026**
  to keep a configurable limit over NousResearch's then-fixed 60; that difference no longer exists.)

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
- **Decided (3 Nov 2026):** the user keeps the fork's signal and Desktop handler over NousResearch's
  (20acba0376, a03d7d8a08, 6bcf096ef4, 1f8c6134c2, 9de32e7be9). That difference is settled and does
  not send this entry back to Pending review; a later NousResearch change to the slash menu or the
  change watcher is reviewed as usual.
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

### 19. Deleted sessions can be undone for 7 days

- **Files:**
  - Core (inside the storage layer): `persistence/sqlite/conversation/_store/trash.py` (new: the
    trash tables `session_trash` / `session_trash_messages`, created on first use; snapshot, list,
    restore, purge; retention read from the store's own profile config); one hook line each, right
    before `retire_sessions`, in the three user delete paths: `persistence/sqlite/conversation/_store/sessions.py`
    (`delete_session`, `delete_sessions`) and `persistence/sqlite/authority/_runtime_retirement.py`
    (`delete_in_transaction`, the canonical delete the desktop's `DELETE /api/sessions/<id>` runs);
    `persistence/sqlite/authority/_admission_media.py` (`_history_mentions` takes a `table`;
    `unheld_media` keeps media a trashed message mentions); `persistence/sqlite/conversation/messages.py`
    (`spillover_reference_rows` also yields trashed messages, so `referenced_archive_refs` keeps their
    archives); `hermes_cli/config_defaults.py` (`sessions.trash_retention_days`, default 7).
  - Entry for surfaces: `persistence/session_trash.py` (new): what the web routes and the CLI call
    with the storage handle they hold; after a purge it runs `collect_retired_media` on the folder the
    store's file is in.
  - Surfaces: `hermes_cli/web_routers/sessions.py` (`GET /api/sessions/trash`,
    `POST /api/sessions/trash/restore`, `POST /api/sessions/trash/purge`, literal routes above the
    `{session_id}` family; they use the gateway's own store via `_owner_store_for` when the web server
    runs inside the gateway, as the desktop's backend does); `hermes_cli/sessions_trash_cmd.py` (new:
    `hermes sessions trash list|restore|purge`), registered in `hermes_cli/subcommands/sessions.py` and
    `hermes_cli/sessions_cmd.py` (also prints the undo command after `hermes sessions delete`).
  - Desktop: `apps/desktop/src/fork/session-trash/` (new: `api.ts`, `undo.ts` (the 10 s toast),
    `recently-deleted.tsx`); hooks in `src/app/session/hooks/use-session-actions/index.ts` (after
    `await deleteSession(...)`) and `src/app/settings/sessions-settings.tsx` (mounts Recently
    deleted below Archived).
  - Docs and tests: `website/docs/user-guide/sessions.md` ("Undo a Delete");
    `tests/persistence_sqlite/core/test_session_trash.py`, `tests/hermes_cli/test_web_session_trash.py`,
    `tests/gateway/test_session_trash_resume.py`, `apps/desktop/src/fork/session-trash/session-trash.test.ts`.
    Two upstream tests that check what a delete frees at once
    (`tests/gateway/test_api_retired_media.py::test_rejected_api_images_are_collected_and_history_owns_accepted_images`
    and the freelist check in `tests/persistence_sqlite/housekeeping/test_auto_prune_and_vacuum.py`) turn
    the trash off with one monkeypatch line naming this entry.
- **Purpose:** a delete was immediate and permanent, so an accidental click lost the
  conversation. Now a user delete (desktop, dashboard, CLI, TUI) copies the rows into the trash in
  the delete's own transaction. The desktop shows "Session deleted · Undo" for 10 s, and Settings >
  Sessions > Recently deleted restores or deletes forever for `sessions.trash_retention_days` days
  (default 7; 0 = off). It is an undo for accidental deletes, not an archive. Housekeeping deletes
  (empty-session sweeps, prunes) are not kept. A restore puts the conversation back (messages
  with their original ids, title, compression segments, subagent runs, usage) under new session ids
  (the retirement fence keeps a deleted id dead), without its old gateway route, so the next native
  resume adopts it as local history and it continues normally.
- **If it breaks:** the code points it depends on: the three delete paths calling `retire_sessions`
  inside their write transaction (a new user-facing delete path needs the same one-line
  `snapshot_for_trash` call before its `retire_sessions`); the `sessions` / `messages` columns
  (snapshots are stored per column name and restored onto whatever columns exist); the adoption of a
  routeless local row on native resume (`gateway.session_local_migration.resolve_local_target`); the
  retirement candidates for archives (`_store/media.retire_spillover`, collected by
  `session_retention.collect_retired_spillover`: a purge hands its archives back as candidates); the
  two reference collectors (`unheld_media`, `spillover_reference_rows`); the backend-import guard
  (trash SQL stays under `persistence/`); the toast API (`notify` with `action`) and
  `restoreListedSession` on the desktop.
- **Ported 21 Nov 2026** onto NousResearch's storage interface after be3d6affc8 removed the old
  session store (`hermes_state_*`).

### 20. Minimize goes to the taskbar; only Close hides to the tray

- **Files:** `apps/desktop/electron/minimize-to-tray.ts` (option `minimizeHidesToTray`, default
  false, checked in the `minimize` handler of `registerWindow`); its test.
- **Purpose:** the user wants Minimize to behave normally (taskbar) while Close still hides to
  the tray when the tray setting is on. Upstream hides on both.
- **If it breaks:** keep the `minimize` handler inert unless `options.minimizeHidesToTray` is
  true, and `main.ts` must not pass it. The `close` handler is untouched.

### 21. Deleting a profile stops that profile's plugin host

- **Files:** `hermes_cli/plugins.py` (`release_plugin_manager_for_home`), one call in
  `hermes_cli/profiles.py` `delete_profile` next to the MCP / memory-store / log-handler releases;
  test `tests/hermes_cli/test_fork_profile_delete_plugin_host.py`.
- **Purpose:** each profile's plugin host process (`hermes_cli.plugin_host_child`, child of the
  backend) runs with the profile directory as its working directory (`PluginHost.ensure_started`,
  `cwd=str(self._home)`). `delete_profile` never stopped it, so on Windows the final rmdir of the
  emptied directory failed with WinError 32 and the host outlived desktop app restarts. Reported
  upstream as NousResearch #159497.
- **If it breaks:** `delete_profile` must stop the deleted profile's host before the rmtree. Hook
  points: `_plugin_managers_by_home` (keyed by resolved home), `PluginManager._plugin_host_instance`,
  `PluginHost.shutdown`. Retire this entry if NousResearch stops the host on delete itself.

## Pending review

None.

## Retired

### 13. The /learn prompt uses the configured skill description limit

- **Files:** `agent/learn_prompt.py`, `tests/agent/test_learn_prompt.py` (`TestDescriptionLimit`).
- **Purpose:** /learn told the drafting agent to keep descriptions to 60 characters while the user's
  configured limit was 100.
- **Replaced by:** NousResearch 1bcad483e1 and ee57e22d18 (21 Nov 2026 merge): `/learn` renders
  `get_skill_desc_limit()`, the configurable `skills.index_desc_limit`. The fork's edit and its tests
  were removed; NousResearch's versions of both files are used unchanged.

### 11. Nightly merge and review of NousResearch's main

- **Removed 3 Nov 2026 by the user's decision:** Hermes is no longer updated on a schedule. The
  nightly script (`scripts/fork_sync.py` and its triage/review prompts), its cheap-model sessions,
  report threads, run files and the automatic cleanup of old internal sessions
  (`sessions.internal_retention_days`) are gone. Updates happen only when the user asks; the agent
  in that conversation does the merge and review itself (skill `hermes-local-install`). Never bring
  back a schedule or a separate model for it.

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
