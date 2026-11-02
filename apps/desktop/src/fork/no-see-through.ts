/**
 * FORK (no see-through, FORK.md): no part of the Hermes interface may be
 * see-through, whatever theme, skin CSS or setting is active.
 *
 * The native window half is locked in `apps/shared/src/translucency.ts`
 * (NO_SEE_THROUGH). This file is the in-page half: frosted blur, surfaces
 * painted at a fraction of their colour, dialog scrims that let the app show
 * through, the message-bubble transparency lever and the unfocused-chat fade.
 *
 * The rules live here, not in a skin, so switching themes cannot drop them.
 *
 * They also cannot be overridden by any other stylesheet, however specific its
 * selector. The rules sit in a cascade layer with a random per-load name, in a
 * style element kept as the FIRST child of <head>. For !important
 * declarations the earliest-declared layer wins over every later layer and
 * over all unlayered CSS, regardless of specificity, and the random name means
 * no other sheet can add rules to this layer.
 */

const STYLE_ID = 'hermes-fork-no-see-through'

const LAYER = `hermes-no-see-through-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`

const RULES = `
:root, :root:root {
  --chat-unfocused-opacity: 1 !important;
  --user-bubble-keep: 100% !important;
  --popover-surface: var(--ui-bg-elevated, var(--popover)) !important;
}
html, body, #root {
  opacity: 1 !important;
}
*, *::before, *::after {
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}
[class*='var(--ui-bg-elevated)_'] { background-color: var(--ui-bg-elevated) !important; }
[class*='bg-background/'] { background-color: var(--background) !important; }
[class*='bg-card/'] { background-color: var(--card) !important; }
[class*='bg-popover/'] { background-color: var(--popover) !important; }
[class*='bg-muted/'] { background-color: var(--muted) !important; }
[class*='bg-sidebar/'] { background-color: var(--sidebar, var(--background)) !important; }
[data-slot='dialog-overlay'],
[data-slot='sheet-overlay'],
[data-slot='alert-dialog-overlay'],
.fixed.inset-0[class*='bg-black/'],
[data-overlay-surface],
:root[data-hermes-clear] [data-overlay-surface] {
  background-color: color-mix(in srgb, var(--foreground) 20%, var(--background)) !important;
}
[data-overlay-surface],
:root[data-hermes-translucency-peek] [data-overlay-surface],
:root[data-hermes-translucency-peek] [data-overlay-surface] * {
  opacity: 1 !important;
}
`

const CSS = `@layer ${LAYER} {${RULES}}`

function ensureFirst(): void {
  const head = document.head

  if (!head) {
    return
  }

  let style = document.getElementById(STYLE_ID)

  if (!style) {
    style = document.createElement('style')
    style.id = STYLE_ID
  }

  if (style.textContent !== CSS) {
    style.textContent = CSS
  }

  if (head.firstChild !== style) {
    head.insertBefore(style, head.firstChild)
  }
}

if (typeof document !== 'undefined') {
  ensureFirst()
  // Put it back if anything removes, edits or moves ahead of it.
  new MutationObserver(ensureFirst).observe(document.head, { characterData: true, childList: true, subtree: true })
}

export {}
