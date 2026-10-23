/**
 * FORK ADDITION (GarishGumdrop/hermes-agent, fork change 16): the Internal section's headings and
 * the slice store.
 */

import { beforeEach, describe, expect, it } from 'vitest'

import type { SidebarSessionEntry } from '@/lib/session-branch-tree'
import type { SessionInfo } from '@/types/hermes'

import { groupEntriesByOrigin, internalOriginOf } from './group'
import {
  $internalSessions,
  $internalSessionsTotal,
  $internalShownInMain,
  $internalSliceSeen,
  applyInternalSlice,
  type InternalSessionInfo
} from './store'

const row = (id: string, origin?: string): InternalSessionInfo =>
  ({ id, internal_origin: origin, message_count: 1, source: 'oneshot', started_at: 1 }) as unknown as InternalSessionInfo

const entry = (session: SessionInfo, branchStem?: string): SidebarSessionEntry => ({ branchStem, session })

describe('groupEntriesByOrigin', () => {
  it('lists each origin once, ordered by its newest row, with its count', () => {
    const rows = groupEntriesByOrigin(
      [entry(row('a', 'Nightly update')), entry(row('b', 'Started by “Fix”')), entry(row('c', 'Nightly update'))],
      internalOriginOf
    )

    expect(rows.map(r => (r.kind === 'divider' ? `# ${'label' in r ? r.label : ''}` : r.entry.session.id))).toEqual([
      '# Nightly update (2)',
      'a',
      'c',
      '# Started by “Fix” (1)',
      'b'
    ])
  })

  it('keeps branch rows under the row they hang from', () => {
    const rows = groupEntriesByOrigin(
      [entry(row('parent', 'Programs')), entry(row('branch', 'Other origin'), '└'), entry(row('next', 'Other origin'))],
      internalOriginOf
    )

    expect(rows.map(r => (r.kind === 'divider' ? `# ${'label' in r ? r.label : ''}` : r.entry.session.id))).toEqual([
      '# Programs (2)',
      'parent',
      'branch',
      '# Other origin (1)',
      'next'
    ])
  })

  it('names rows without an origin "Other"', () => {
    expect(internalOriginOf(row('x'))).toBe('Other')
    expect(internalOriginOf(row('y', '  '))).toBe('Other')
  })
})

describe('applyInternalSlice', () => {
  beforeEach(() => {
    $internalSliceSeen.set(false)
    $internalSessions.set([])
    $internalSessionsTotal.set(0)
    $internalShownInMain.set(false)
  })

  it('ignores a response without the slice (an older backend)', () => {
    applyInternalSlice(undefined, rows => rows)
    expect($internalSliceSeen.get()).toBe(false)
  })

  it('stores rows through the removal filter, the full count and the switch state', () => {
    applyInternalSlice({ sessions: [row('keep'), row('gone')], shown_in_main: false, total: 7 }, rows =>
      rows.filter(r => r.id !== 'gone')
    )
    expect($internalSliceSeen.get()).toBe(true)
    expect($internalSessions.get().map(r => r.id)).toEqual(['keep'])
    expect($internalSessionsTotal.get()).toBe(7)
    expect($internalShownInMain.get()).toBe(false)
  })
})
