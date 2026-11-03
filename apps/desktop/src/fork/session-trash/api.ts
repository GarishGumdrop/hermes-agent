/**
 * FORK ADDITION (GarishGumdrop/hermes-agent, fork change 19) — REST calls for the session trash.
 *
 * A user delete keeps a restorable copy for `sessions.trash_retention_days` days (default 7):
 * hermes_state_trash.py is the backend half, hermes_cli/web_routers/sessions.py the routes.
 * Requests are scoped like the delete they undo (mutateSessionHttp in src/api/sessions.ts): the
 * active connection plus the owning profile, named in the body for POSTs.
 */

import { capabilityScoped, getApiRequestConnection, getApiRequestProfile, hermesApi, type ProfileScope } from '@/api/client'

export interface TrashEntry {
  deleted_at: number
  expires_at: null | number
  message_count: number
  root_session_id: string
  session_count: number
  session_ids: string[]
  title: string
  trash_id: string
}

export interface TrashListing {
  entries: TrashEntry[]
  retention_days: number
}

export interface TrashRestoreResult {
  ok: boolean
  session_id: string
  session_ids: Record<string, string>
  trash_id: string
}

function scoped(profile?: ProfileScope): { connectionId?: null | string; profile?: string } {
  const { priority: _priority, ...rest } = capabilityScoped(profile ?? undefined)

  return { connectionId: getApiRequestConnection(), ...rest }
}

function bodyProfile(profile?: ProfileScope): string | undefined {
  const named = typeof profile === 'string' ? profile : profile?.profile

  return String(named ?? '').trim() || getApiRequestProfile() || undefined
}

export function listSessionTrash(profile?: ProfileScope): Promise<TrashListing> {
  const scope = scoped(profile)
  const query = scope.profile ? `?profile=${encodeURIComponent(scope.profile)}` : ''

  return hermesApi<TrashListing>({ ...scope, path: `/api/sessions/trash${query}` })
}

export function restoreSessionTrash(
  target: { sessionId?: string; trashId?: string },
  profile?: ProfileScope
): Promise<TrashRestoreResult> {
  return hermesApi<TrashRestoreResult>({
    ...scoped(profile),
    body: { profile: bodyProfile(profile), session_id: target.sessionId, trash_id: target.trashId },
    method: 'POST',
    path: '/api/sessions/trash/restore'
  })
}

export function purgeSessionTrash(
  target: { all?: boolean; trashId?: string },
  profile?: ProfileScope
): Promise<{ ok: boolean; removed: number }> {
  return hermesApi({
    ...scoped(profile),
    body: { all: Boolean(target.all), profile: bodyProfile(profile), trash_id: target.trashId },
    method: 'POST',
    path: '/api/sessions/trash/purge'
  })
}
