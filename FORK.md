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

### 2. High-contrast override for the light theme

- **Files:** `apps/desktop/public/high-contrast-override.css` (new file); one
  `<link rel="stylesheet">` line in `apps/desktop/index.html`.
- **Purpose:** the user has weak eyesight. The stylesheet raises text contrast
  and removes faint grey text in the light theme. It must load after the app's
  own styles so it wins.
