/**
 * FORK ADDITION (GarishGumdrop/hermes-agent, fork change 16) — the Internal section's headings.
 *
 * The section lists its rows under one heading per origin ("Nightly update", "Started by “…”",
 * "Bot chats (Bots tab)"), using the flat list's labelled dividers, so every row says what
 * started it whatever row density the user has chosen.
 */

import type { SidebarSessionEntry } from '@/lib/session-branch-tree'
import type { SidebarListRow } from '@/lib/session-date-groups'
import type { SessionInfo } from '@/types/hermes'

import type { InternalSessionInfo } from './store'

export const INTERNAL_ORIGIN_FALLBACK = 'Other'

export function internalOriginOf(session: SessionInfo): string {
  return (session as InternalSessionInfo).internal_origin?.trim() || INTERNAL_ORIGIN_FALLBACK
}

/** One labelled divider per origin, then its rows. Entries arrive newest first, so headings are
 *  ordered by their newest row, and rows keep their order under each heading. Branch rows stay
 *  with the row they hang from. */
export function groupEntriesByOrigin(
  entries: readonly SidebarSessionEntry[],
  originOf: (session: SessionInfo) => string
): SidebarListRow[] {
  const groups = new Map<string, SidebarSessionEntry[]>()
  let current: SidebarSessionEntry[] | undefined

  for (const entry of entries) {
    if (!entry.branchStem || !current) {
      const origin = originOf(entry.session)

      current = groups.get(origin)

      if (!current) {
        current = []
        groups.set(origin, current)
      }
    }

    current.push(entry)
  }

  return [...groups].flatMap(([origin, members]) => [
    { key: `internal-origin:${origin}`, kind: 'divider' as const, label: `${origin} (${members.length})` },
    ...members.map(entry => ({ entry, kind: 'session' as const }))
  ])
}
