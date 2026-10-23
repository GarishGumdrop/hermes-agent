/**
 * FORK ADDITION (GarishGumdrop/hermes-agent, fork change 16) — the sidebar's Internal section.
 *
 * Lists the saved sessions the main list leaves out (programs such as the nightly update,
 * one-off commands, subagent runs, Bot Mode's chats, empty sessions) under a heading per origin,
 * with their count in the section header, so nothing is left out without saying so. The header's
 * switch sets `sessions.show_internal`, which lists them in the main list instead (and in the
 * project view and the terminal's session lists). Rows open, pin, archive and delete like any
 * other row.
 */

import { useStore } from '@nanostores/react'
import { useMemo } from 'react'

import { filterSessionsByProfileScope } from '@/app/chat/sidebar/profile-scope'
import { SidebarSessionsSection } from '@/app/chat/sidebar/sessions-section'
import { cn } from '@/lib/utils'
import type { SessionInfo } from '@/types/hermes'

import { internalOriginOf } from './group'
import {
  $internalSectionOpen,
  $internalSessions,
  $internalSessionsTotal,
  $internalShownInMain,
  $internalSliceSeen,
  setInternalSectionOpen,
  setShowInternal
} from './store'

interface InternalSessionsSectionProps {
  activeSessionId: null | string
  onArchiveSession: (sessionId: string) => void
  onDeleteSession: (sessionId: string) => void
  onResumeSession: (sessionId: string, session?: SessionInfo) => void
  onTogglePin: (sessionId: string) => void
  onToggleUnread: (sessionId: string) => void
  /** The sidebar's profile scope; rows from other profiles are left to their own view. */
  profileScope: string
  /** Tag each row with its profile (the All-profiles view). */
  showProfileTags: boolean
}

const NOTE = 'px-2 py-1 text-[0.8125rem] leading-snug text-(--ui-text-secondary)'

export function InternalSessionsSection({
  activeSessionId,
  onArchiveSession,
  onDeleteSession,
  onResumeSession,
  onTogglePin,
  onToggleUnread,
  profileScope,
  showProfileTags
}: InternalSessionsSectionProps) {
  const allSessions = useStore($internalSessions)
  const sessions = useMemo(() => filterSessionsByProfileScope(allSessions, profileScope), [allSessions, profileScope])
  const total = useStore($internalSessionsTotal)
  const shownInMain = useStore($internalShownInMain)
  const seen = useStore($internalSliceSeen)
  const open = useStore($internalSectionOpen)

  // An older backend sends no internal slice; then there is nothing true to show.
  if (!seen) {
    return null
  }

  const switchLabel = shownInMain ? 'Also in main list: on' : 'Also in main list: off'

  const switchTip = shownInMain
    ? 'Internal sessions are listed in the main session list. Click to list them only here.'
    : 'Click to list internal sessions in the main session list as well.'

  const headerAction = (
    <button
      aria-label={switchTip}
      aria-pressed={shownInMain}
      className={cn(
        'shrink-0 rounded-md border px-1.5 py-0.5 text-[0.75rem] font-medium leading-none transition-colors',
        shownInMain
          ? 'border-(--ui-text-secondary) bg-(--ui-control-hover-background) text-(--ui-text-primary)'
          : 'border-(--ui-text-tertiary) text-(--ui-text-secondary) hover:text-(--ui-text-primary)'
      )}
      onClick={event => {
        event.stopPropagation()
        void setShowInternal(!shownInMain)
      }}
      title={switchTip}
      type="button"
    >
      {switchLabel}
    </button>
  )

  const emptyState = shownInMain ? (
    <p className={NOTE}>These sessions are listed in the main session list while the switch is on.</p>
  ) : (
    <p className={NOTE}>No internal sessions.</p>
  )

  const footer =
    !shownInMain && total > sessions.length ? (
      <p className={NOTE}>
        Showing the newest {sessions.length} of {total}.
      </p>
    ) : null

  return (
    <SidebarSessionsSection
      activeSessionId={activeSessionId}
      contentClassName="flex max-h-80 flex-col gap-px pb-1.75"
      emptyState={emptyState}
      footer={footer}
      forceEmptyState={shownInMain}
      grouping="origin"
      headerAction={headerAction}
      label="Internal sessions"
      labelMeta={shownInMain ? 'in main list' : String(total)}
      onArchiveSession={onArchiveSession}
      onDeleteSession={onDeleteSession}
      onResumeSession={onResumeSession}
      onToggle={() => setInternalSectionOpen(!open)}
      onTogglePin={onTogglePin}
      onToggleUnread={onToggleUnread}
      open={open}
      originOf={internalOriginOf}
      pinned={false}
      rootClassName="shrink-0 p-0"
      sessions={shownInMain ? [] : sessions}
      showProfileTags={showProfileTags}
    />
  )
}
