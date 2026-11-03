/**
 * FORK ADDITION (GarishGumdrop/hermes-agent, fork change 19): the delete Undo toast.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const restoreSessionTrash = vi.fn()
const getSession = vi.fn()
const restoreListedSession = vi.fn()
const notifySessionsChanged = vi.fn()

vi.mock('./api', () => ({ restoreSessionTrash: (...a: unknown[]) => restoreSessionTrash(...a) }))
vi.mock('@/api/sessions', () => ({ getSession: (...a: unknown[]) => getSession(...a) }))
vi.mock('@/app/session/hooks/use-session-actions/utils', () => ({
  restoreListedSession: (...a: unknown[]) => restoreListedSession(...a)
}))
vi.mock('@/store/live-sync', () => ({ notifySessionsChanged: () => notifySessionsChanged() }))

import { $notifications, clearNotifications } from '@/store/notifications'

import { offerDeleteUndo, UNDO_WINDOW_MS } from './undo'

const undoToast = () => $notifications.get().find(n => n.id.startsWith('session-delete-undo-'))

describe('offerDeleteUndo', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    clearNotifications()
    restoreSessionTrash.mockResolvedValue({ ok: true, session_id: 'new-1', session_ids: { old: 'new-1' }, trash_id: 't' })
    getSession.mockResolvedValue({ id: 'new-1' })
  })

  afterEach(() => clearNotifications())

  it('shows a 10 s Undo toast that restores the deleted session and opens it', async () => {
    const opened = vi.fn()
    offerDeleteUndo('old', 'default', opened)
    const toast = undoToast()
    expect(toast?.message).toBe('Session deleted')
    expect(toast?.action?.label).toBe('Undo')
    expect(UNDO_WINDOW_MS).toBe(10_000)

    toast!.action!.onClick()
    await vi.waitFor(() => expect(opened).toHaveBeenCalledWith('new-1'))
    expect(restoreSessionTrash).toHaveBeenCalledWith({ sessionId: 'old' }, 'default')
    expect(restoreListedSession).toHaveBeenCalledWith({ id: 'new-1' })
    expect(notifySessionsChanged).toHaveBeenCalled()
  })

  it('restores once even when Undo is clicked twice', async () => {
    offerDeleteUndo('old', undefined)
    const toast = undoToast()!
    toast.action!.onClick()
    toast.action!.onClick()
    await vi.waitFor(() => expect(notifySessionsChanged).toHaveBeenCalled())
    expect(restoreSessionTrash).toHaveBeenCalledTimes(1)
  })
})
