/**
 * FORK ADDITION (GarishGumdrop/hermes-agent, fork change 16) — data for the sidebar's
 * Internal section.
 *
 * Hermes saves every model session, including the ones nobody started as a conversation:
 * programs such as the nightly update, one-off `hermes chat` commands, subagent runs, Bot Mode's
 * chats and empty sessions. The main session list leaves those out. The backend now sends them
 * as an `internal` slice of the batched sidebar request (rows, their count, and whether the
 * `sessions.show_internal` switch has moved them into the main list), and this store keeps that
 * slice so the section can show what the main list leaves out instead of hiding it silently.
 * hermes_cli/internal_sessions.py is the backend half.
 */

import { atom } from 'nanostores'

import { readKey, writeKey } from '@/lib/storage'
import { activeGatewayProfileKey, requestGatewayForProfile } from '@/store/gateway'
import { notifyError } from '@/store/notifications'
import type { SessionInfo } from '@/types/hermes'

/** A row of the Internal section: an ordinary sidebar row plus what started it. */
export interface InternalSessionInfo extends SessionInfo {
  /** The heading the row is listed under, e.g. "Nightly update" or "Started by “…”". */
  internal_origin?: null | string
  launched_by?: null | string
  launched_from?: null | string
  launched_from_title?: null | string
}

export interface InternalSessionsSlice {
  sessions: InternalSessionInfo[]
  /** Every internal session in scope, not just the rows sent. */
  total: number
  /** True while `sessions.show_internal` lists these sessions in the main list. */
  shown_in_main: boolean
}

/** Rows one sidebar refresh asks for; the section header counts all of them. */
export const INTERNAL_SECTION_LIMIT = 200

export const $internalSessions = atom<InternalSessionInfo[]>([])
export const $internalSessionsTotal = atom(0)
export const $internalShownInMain = atom(false)
/** False until a backend answers with the slice; an older backend never does. */
export const $internalSliceSeen = atom(false)
/** Bumped by the switch. The sidebar refreshes on it and sends it, so the backend's short
 *  response cache cannot answer with the list from before the switch. */
export const $internalRefreshToken = atom(0)

const OPEN_STORAGE_KEY = 'hermes.fork.internalSessionsOpen'

export const $internalSectionOpen = atom(readKey(OPEN_STORAGE_KEY) === 'true')

export function setInternalSectionOpen(open: boolean) {
  $internalSectionOpen.set(open)
  writeKey(OPEN_STORAGE_KEY, open ? 'true' : 'false')
}

/** Store one refresh's `internal` slice. `filter` drops rows the user has just deleted or
 *  archived, the same guard the other sidebar lists apply. */
export function applyInternalSlice(
  slice: InternalSessionsSlice | undefined,
  filter: (rows: InternalSessionInfo[]) => InternalSessionInfo[]
) {
  if (!slice) {
    return
  }

  $internalSliceSeen.set(true)
  $internalShownInMain.set(Boolean(slice.shown_in_main))
  $internalSessionsTotal.set(Math.max(0, Number(slice.total) || 0))
  $internalSessions.set(filter(slice.sessions ?? []))
}

/** Set `sessions.show_internal` on the live gateway, then refresh the sidebar. A failure
 *  restores the switch and says so; it is never silent. */
export async function setShowInternal(show: boolean): Promise<void> {
  const previous = $internalShownInMain.get()

  $internalShownInMain.set(show)

  try {
    await requestGatewayForProfile(activeGatewayProfileKey(), 'config.set', {
      key: 'sessions.show_internal',
      value: show ? 'true' : 'false'
    })
  } catch (error) {
    $internalShownInMain.set(previous)
    notifyError(error, 'Could not change where internal sessions are listed.')
  } finally {
    $internalRefreshToken.set($internalRefreshToken.get() + 1)
  }
}
