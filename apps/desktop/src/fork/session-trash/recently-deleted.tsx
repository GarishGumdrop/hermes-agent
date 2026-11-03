/**
 * FORK ADDITION (GarishGumdrop/hermes-agent, fork change 19) — Settings > Sessions > Recently deleted.
 *
 * Lists the sessions deleted in the last `sessions.trash_retention_days` days (default 7) with
 * Restore and Delete forever. An undo for accidental deletes, not an archive: entries expire on
 * their own. Mounted below the Archived list in src/app/settings/sessions-settings.tsx.
 */

import { useCallback, useEffect, useState } from 'react'

import { EmptyState, ListRow, SectionHeading } from '@/app/settings/primitives'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/tooltip'
import { triggerHaptic } from '@/lib/haptics'
import { Loader2, Trash2 } from '@/lib/icons'
import { confirm } from '@/store/confirm'
import { notify, notifyError } from '@/store/notifications'

import { listSessionTrash, purgeSessionTrash, type TrashEntry } from './api'
import { restoreDeletedSession } from './undo'

function ago(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))

  if (s < 3600) {
    return `${Math.max(1, Math.round(s / 60))} min ago`
  }

  if (s < 86400) {
    return `${Math.round(s / 3600)} h ago`
  }

  const days = Math.round(s / 86400)

  return `${days} day${days === 1 ? '' : 's'} ago`
}

function left(expiresAt: null | number, now: number): string {
  if (!expiresAt) {
    return ''
  }

  const days = Math.max(0, (expiresAt - now) / 86400)

  return days >= 1 ? `${Math.floor(days)} day${Math.floor(days) === 1 ? '' : 's'} left` : 'expires today'
}

export function RecentlyDeletedSessions() {
  const [entries, setEntries] = useState<TrashEntry[]>([])
  const [retentionDays, setRetentionDays] = useState(7)
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<null | string>(null)

  const load = useCallback(async () => {
    try {
      const listing = await listSessionTrash()
      setEntries(listing.entries)
      setRetentionDays(listing.retention_days)
    } catch {
      // An older backend without the trash routes: leave the section empty.
      setEntries([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const restore = useCallback(async (entry: TrashEntry) => {
    setBusyId(entry.trash_id)

    try {
      await restoreDeletedSession({ trashId: entry.trash_id })
      setEntries(prev => prev.filter(e => e.trash_id !== entry.trash_id))
      triggerHaptic('selection')
      notify({ durationMs: 2_500, kind: 'success', message: 'Session restored' })
    } catch (err) {
      notifyError(err, 'Could not restore the session')
    } finally {
      setBusyId(null)
    }
  }, [])

  const purge = useCallback(async (entry: TrashEntry) => {
    const ok = await confirm({
      confirmLabel: 'Delete forever',
      destructive: true,
      title: `Delete “${entry.title}” forever? This cannot be undone.`
    })

    if (!ok) {
      return
    }

    setBusyId(entry.trash_id)

    try {
      await purgeSessionTrash({ trashId: entry.trash_id })
      setEntries(prev => prev.filter(e => e.trash_id !== entry.trash_id))
      triggerHaptic('warning')
    } catch (err) {
      notifyError(err, 'Delete failed')
    } finally {
      setBusyId(null)
    }
  }, [])

  if (loading || retentionDays <= 0) {
    return null
  }

  const now = Date.now() / 1000

  return (
    <div className="mt-8">
      <SectionHeading icon={Trash2} meta={entries.length ? String(entries.length) : undefined} title="Recently deleted" />
      <p className="mb-2 text-[length:var(--conversation-caption-font-size)] text-(--ui-text-tertiary)">
        {`Deleted sessions can be restored for ${retentionDays} day${retentionDays === 1 ? '' : 's'}, then they are removed for good. A restored session gets a new id.`}
      </p>

      {entries.length === 0 ? (
        <EmptyState description="Sessions you delete show up here for a while." title="Nothing deleted recently" />
      ) : (
        <div className="grid gap-1">
          {entries.map(entry => {
            const busy = busyId === entry.trash_id
            const linked = entry.session_count > 1 ? ` · +${entry.session_count - 1} linked` : ''
            const remaining = left(entry.expires_at, now)

            return (
              <ListRow
                action={
                  <div className="flex items-center gap-1.5">
                    <Button
                      disabled={busy}
                      onClick={() => void restore(entry)}
                      size="sm"
                      type="button"
                      variant="textStrong"
                    >
                      {busy && <Loader2 className="size-3.5 animate-spin" />}
                      <span>Restore</span>
                    </Button>
                    <Tip label="Delete forever">
                      <Button
                        aria-label="Delete forever"
                        className="text-muted-foreground hover:text-destructive"
                        disabled={busy}
                        onClick={() => void purge(entry)}
                        size="icon"
                        type="button"
                        variant="ghost"
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </Tip>
                  </div>
                }
                hint={`Deleted ${ago(now - entry.deleted_at)} · ${entry.message_count} messages${linked}${remaining ? ` · ${remaining}` : ''}`}
                key={entry.trash_id}
                title={entry.title}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
