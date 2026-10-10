/**
 * FORK ADDITION (GarishGumdrop/hermes-agent) — agent access to desktop settings.
 *
 * Hermes Desktop keeps most of its settings inside the renderer, and the plugin
 * SDK exposes only seven of them (`host.settings`). This module lets the agent
 * read and change every simple setting from the Settings pages, and switch
 * desktop plugins on or off, by publishing `window.hermesAgentSettings`. The
 * user's desktop-settings-bridge plugin relays the agent's requests to it.
 *
 * Every change goes through the app's OWN setter for that setting, so it takes
 * effect immediately and the control on the Settings page follows. Nothing
 * writes app storage behind the app's back.
 *
 * Loaded from index.html as a second module entry, so no upstream source file
 * is edited and the fork's nightly sync rarely has to hold an update for it.
 * If an upstream release renames one of the stores imported below, the desktop
 * build fails with a type error naming it: loud, never a silent no-op.
 */

import { $pluginRecords, setPluginEnabled } from '@/contrib/plugins-store'
import { $backdrop, setBackdrop } from '@/store/backdrop'
import { $chatTextScale, CHAT_TEXT_SCALE_PRESETS, setChatTextScale } from '@/store/chat-text-scale'
import { $completionSoundVariantId, setCompletionSoundVariantId } from '@/store/completion-sound'
import { $composerPopoutGesturesEnabled, setComposerPopoutGesturesEnabled } from '@/store/composer-popout'
import {
  $dataUrlReadMaxMb,
  DATA_URL_READ_MAX_MAX_MB,
  DATA_URL_READ_MIN_MAX_MB,
  setDataUrlReadMaxMb
} from '@/store/data-url-read-max'
import { $disableF12, setDisableF12 } from '@/store/disable-f12'
import { $embedMode, setEmbedMode } from '@/store/embed-consent'
import { $alwaysExternalLinks, setAlwaysExternalLinks } from '@/store/external-links'
import { $hapticsMuted, setHapticsMuted } from '@/store/haptics'
import { $interfaceMode, setInterfaceMode } from '@/store/interface-mode'
import { $introSplash, setIntroSplash } from '@/store/intro-splash'
import { $keepAwakeMode, setKeepAwakeMode } from '@/store/keep-awake'
import { $fileBrowserOpen, setFileBrowserOpen } from '@/store/layout'
import { $showModelPricing, setShowModelPricing } from '@/store/model-pricing'
import {
  $nativeNotifyPrefs,
  NATIVE_NOTIFICATION_KINDS,
  setNativeNotifyEnabled,
  setNativeNotifyKind
} from '@/store/native-notifications'
import { $reactionsEnabled, setReactionsEnabled } from '@/store/reactions-enabled'
import { $reasoningCollapsedByDefault, setReasoningCollapsedByDefault } from '@/store/reasoning-disclosure'
import { $sessionListDensity, setSessionListDensity } from '@/store/session-list-density'
import { $tabStripDefault, setTabStripDefault } from '@/store/tabstrip-prefs'
import { $textDirection, setTextDirection } from '@/store/text-direction'
import { $hideThreadTimeline, setHideThreadTimeline } from '@/store/thread-timeline'
import { $tipsEnabled, setTipsEnabled } from '@/store/tips'
import { $titlebarAppActionsSide, setTitlebarAppActionsSide } from '@/store/titlebar-app-actions'
import { $hideCodeDiffs, $toolViewMode, setHideCodeDiffs, setToolViewMode } from '@/store/tool-view'
import { $toursEnabled, setToursEnabled } from '@/store/tours'
import { $userBubbleTransparency, setUserBubbleTransparency } from '@/store/user-bubble-transparency'
import { $vibeHeartsEnabled, setVibeHeartsEnabled } from '@/store/vibe-hearts-enabled'
import { $autoSpeakReplies, setAutoSpeakReplies } from '@/store/voice-prefs'
import { $zoomPercent, setZoomPercent } from '@/store/zoom'

type Value = boolean | number | string

interface SettingSpec {
  /** Plain-English name, as the Settings page describes it. */
  label: string
  type: 'boolean' | 'choice' | 'number'
  choices?: readonly Value[]
  min?: number
  max?: number
  get: () => Promise<Value> | Value
  set: (value: never) => Promise<unknown> | unknown
}

interface ReadableAtomLike<T> {
  get: () => T
}

const bool = (label: string, $atom: ReadableAtomLike<boolean>, set: (on: boolean) => unknown): SettingSpec => ({
  label,
  type: 'boolean',
  get: () => $atom.get(),
  set
})

const choice = <T extends Value>(
  label: string,
  choices: readonly T[],
  $atom: ReadableAtomLike<T>,
  set: (value: T) => unknown
): SettingSpec => ({ label, type: 'choice', choices, get: () => $atom.get(), set })

const num = (
  label: string,
  min: number,
  max: number,
  $atom: ReadableAtomLike<number>,
  set: (value: number) => unknown
): SettingSpec => ({ label, type: 'number', min, max, get: () => $atom.get(), set })

const tray = () => window.hermesDesktop?.minimizeToTray

const SETTINGS: Record<string, SettingSpec> = {
  // Appearance > Typography
  chatTextScale: choice('Chat text size (percent)', CHAT_TEXT_SCALE_PRESETS, $chatTextScale, setChatTextScale),
  uiScale: num('Interface zoom (percent)', 50, 300, $zoomPercent, setZoomPercent),
  // Appearance > General
  introSplash: bool('Intro splash on an empty chat', $introSplash, setIntroSplash),
  modelPricing: bool('Show model prices in the model picker', $showModelPricing, setShowModelPricing),
  tips: bool('Tips', $tipsEnabled, setTipsEnabled),
  tours: bool('Guided tours', $toursEnabled, setToursEnabled),
  // Appearance > Window & layout
  interfaceMode: choice('Interface mode', ['simple', 'advanced'] as const, $interfaceMode, setInterfaceMode),
  sessionListDensity: choice(
    'Session list density',
    ['compact', 'comfortable', 'detailed'] as const,
    $sessionListDensity,
    setSessionListDensity
  ),
  tabStrip: choice('Tab strip', ['auto', 'always', 'never'] as const, $tabStripDefault, setTabStripDefault),
  appActionsSide: choice(
    'Titlebar buttons side',
    ['left', 'right'] as const,
    $titlebarAppActionsSide,
    setTitlebarAppActionsSide
  ),
  backdrop: bool('Chat backdrop image', $backdrop, setBackdrop),
  fileBrowser: bool('File browser open', $fileBrowserOpen, setFileBrowserOpen),
  composerPopout: bool(
    'Floating composer (drag to pop out)',
    $composerPopoutGesturesEnabled,
    setComposerPopoutGesturesEnabled
  ),
  minimizeToTray: {
    label: 'Minimize to the system tray',
    type: 'boolean',
    get: async () => Boolean((await tray()?.get())?.enabled),
    set: async (on: boolean) => {
      const api = tray()

      if (!api) {
        throw new Error('the tray switch is not available on this system')
      }

      await api.set(on)
    }
  },
  // Appearance > Chat display
  userBubbleTransparency: num('Your message bubble transparency', 0, 100, $userBubbleTransparency, setUserBubbleTransparency),
  textDirection: choice('Text direction', ['auto', 'ltr', 'rtl'] as const, $textDirection, setTextDirection),
  hideThreadTimeline: bool('Hide the conversation timeline rail', $hideThreadTimeline, setHideThreadTimeline),
  reactions: bool('Emoji reactions', $reactionsEnabled, setReactionsEnabled),
  vibeHearts: bool('Vibe hearts', $vibeHeartsEnabled, setVibeHeartsEnabled),
  toolView: choice('Tool display', ['product', 'technical'] as const, $toolViewMode, setToolViewMode),
  hideCodeDiffs: bool('Hide code diffs', $hideCodeDiffs, setHideCodeDiffs),
  reasoningCollapsed: bool('Collapse reasoning by default', $reasoningCollapsedByDefault, setReasoningCollapsedByDefault),
  embeds: choice('External embeds (videos, posts)', ['always', 'ask', 'off'] as const, $embedMode, setEmbedMode),
  alwaysExternalLinks: bool('Open links in the system browser', $alwaysExternalLinks, setAlwaysExternalLinks),
  // Chat
  attachmentSizeMb: num(
    'Largest attachment preview (MB)',
    DATA_URL_READ_MIN_MAX_MB,
    DATA_URL_READ_MAX_MAX_MB,
    $dataUrlReadMaxMb,
    setDataUrlReadMaxMb
  ),
  autoSpeakReplies: bool('Read replies aloud', $autoSpeakReplies, setAutoSpeakReplies),
  // Advanced > Desktop
  keepAwake: choice(
    'Keep the computer awake',
    ['off', 'while-working', 'always'] as const,
    $keepAwakeMode,
    setKeepAwakeMode
  ),
  disableF12: bool('Disable F12 developer tools', $disableF12, setDisableF12),
  haptics: bool('Haptics muted', $hapticsMuted, setHapticsMuted),
  // Notifications
  notifications: {
    label: 'Desktop notifications',
    type: 'boolean',
    get: () => $nativeNotifyPrefs.get().enabled,
    set: setNativeNotifyEnabled
  },
  ...Object.fromEntries(
    NATIVE_NOTIFICATION_KINDS.map(kind => [
      `notifications.${kind}`,
      {
        label: `Notify: ${kind}`,
        type: 'boolean',
        get: () => $nativeNotifyPrefs.get().kinds[kind],
        set: (on: boolean) => setNativeNotifyKind(kind, on)
      } satisfies SettingSpec
    ])
  ),
  completionSound: num('Completion sound (variant 1-14)', 1, 14, $completionSoundVariantId, setCompletionSoundVariantId)
}

function validate(key: string, spec: SettingSpec, value: unknown): Value {
  if (spec.type === 'boolean') {
    if (typeof value !== 'boolean') {
      throw new Error(`${key} expects true or false`)
    }

    return value
  }

  if (spec.type === 'number') {
    const n = typeof value === 'string' ? Number(value) : value

    if (typeof n !== 'number' || !Number.isFinite(n)) {
      throw new Error(`${key} expects a number`)
    }

    if ((spec.min !== undefined && n < spec.min) || (spec.max !== undefined && n > spec.max)) {
      throw new Error(`${key} must be between ${spec.min} and ${spec.max}`)
    }

    return n
  }

  const match = spec.choices?.find(c => c === value || String(c) === String(value))

  if (match === undefined) {
    throw new Error(`${key} must be one of: ${(spec.choices ?? []).join(', ')}`)
  }

  return match
}

function spec(key: string): SettingSpec {
  if (!Object.hasOwn(SETTINGS, key)) {
    throw new Error(`Unknown setting: ${key}`)
  }

  return SETTINGS[key]
}

export const agentSettings = {
  version: 1,

  /** Every setting: key, plain-English label, allowed values, current value. */
  async list() {
    return Promise.all(
      Object.entries(SETTINGS).map(async ([key, s]) => {
        let value: null | Value = null

        try {
          value = await s.get()
        } catch {
          value = null
        }

        return { key, label: s.label, type: s.type, choices: s.choices, min: s.min, max: s.max, value }
      })
    )
  },

  async get(key: string): Promise<Value> {
    return spec(key).get()
  },

  /** Change one setting through the app's own setter; resolves to the value the app now reports. */
  async set(key: string, value: unknown): Promise<Value> {
    const s = spec(key)
    const checked = validate(key, s, value)
    await (s.set as (v: Value) => unknown)(checked)
    // Some setters (zoom, tray) round-trip through the native layer; give them a beat.
    await new Promise(resolve => setTimeout(resolve, 150))

    return s.get()
  },

  plugins: {
    list() {
      return Object.values($pluginRecords.get()).map(r => ({
        id: r.id,
        name: r.name,
        kind: r.kind,
        status: r.status,
        package: r.packageName ?? null,
        origin: r.packageOrigin?.repo ?? r.packageOrigin?.catalogName ?? null,
        error: r.error ?? null
      }))
    },

    /** Switch a desktop plugin on or off, live (the same call the Plugins page makes). */
    async setEnabled(id: string, enabled: boolean) {
      const record = $pluginRecords.get()[id]

      if (!record) {
        throw new Error(`Unknown desktop plugin: ${id}`)
      }

      if (typeof enabled !== 'boolean') {
        throw new Error('expects true or false')
      }

      await setPluginEnabled(id, enabled)

      return $pluginRecords.get()[id]?.status ?? 'unknown'
    }
  }
}

declare global {
  interface Window {
    hermesAgentSettings?: typeof agentSettings
  }
}

window.hermesAgentSettings = agentSettings
