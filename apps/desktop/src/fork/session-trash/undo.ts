/**
 * FORK ADDITION (GarishGumdrop/hermes-agent, fork change 19) — the "Session deleted · Undo" toast.
 *
 * Shown for 10 seconds after a sidebar delete lands. Undo asks the backend to restore the newest
 * trash entry holding the deleted id (the conversation comes back under a new id: Hermes never
 * reuses a deleted id), puts the row back in the sidebar and, when the deleted chat was open,
 * opens the restored one. After the toast is gone, Settings > Sessions > Recently deleted does the
 * same for 7 days.
 */

import type { ProfileScope } from '@/api/client'
import { getSession } from '@/api/sessions'
import { restoreListedSession } from '@/app/session/hooks/use-session-actions/utils'
import { notifySessionsChanged } from '@/store/live-sync'
import { notify, notifyError } from '@/store/notifications'

import { restoreSessionTrash } from './api'

export const UNDO_WINDOW_MS = 10_000

/** Restore the trashed conversation; returns its new stored id. Refreshes the session list. */
export async function restoreDeletedSession(
  target: { sessionId?: string; trashId?: string },
  owner?: ProfileScope
): Promise<string> {
  const result = await restoreSessionTrash(target, owner)

  try {
    restoreListedSession(await getSession(result.session_id, owner))
  } catch {
    // The list refresh below picks it up; an immediate row is only a nicety.
  }

  notifySessionsChanged()

  return result.session_id
}

export function offerDeleteUndo(
  storedSessionId: string,
  owner: ProfileScope,
  onRestored?: (newSessionId: string) => void
): void {
  let used = false

  notify({
    action: {
      label: 'Undo',
      onClick: () => {
        if (used) {
          return
        }

        used = true
        void restoreDeletedSession({ sessionId: storedSessionId }, owner)
          .then(newId => {
            notify({ durationMs: 2_500, kind: 'success', message: 'Session restored' })
            onRestored?.(newId)
          })
          .catch(err => notifyError(err, 'Could not restore the session'))
      }
    },
    durationMs: UNDO_WINDOW_MS,
    id: `session-delete-undo-${storedSessionId}`,
    kind: 'info',
    message: 'Session deleted'
  })
}
