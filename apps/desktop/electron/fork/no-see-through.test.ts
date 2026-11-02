import { describe, expect, it } from 'vitest'

import {
  backgroundMaterialFor,
  defaultTranslucencyState,
  glassActive,
  glassSupportedOn,
  hudFrostFor,
  normalizeBook,
  normalizeState,
  resolveTranslucency,
  translucencySupportedOn,
  windowOpacityFor
} from '../../../shared/src/translucency'
import { windowBackgroundMaterialOptions, windowBackingOptions, windowOpacityOptions } from "../translucency"

// FORK change 18 (FORK.md): nothing may make the window see-through.
describe('no see-through lock', () => {
  const hostile = [
    { intensity: 100, fade: 100, mode: 'clear', material: 'under-window', scope: 'window' },
    { intensity: 100, fade: 100, mode: 'glass', material: 'popover', scope: 'window' },
    { intensity: 29, fade: 0, mode: 'clear' },
    { intensity: 29 }
  ]

  it('never offers translucency or glass on any OS', () => {
    for (const platform of ['win32', 'darwin', 'linux']) {
      expect(translucencySupportedOn(platform)).toBe(false)
      expect(glassSupportedOn(platform, '10.0.26100')).toBe(false)
    }
  })

  it('resolves any saved file or IPC payload to an opaque window', () => {
    for (const payload of hostile) {
      for (const glass of [true, false]) {
        const state = normalizeState(payload, glass)

        expect(state.intensity).toBe(0)
        expect(windowOpacityFor(state)).toBe(1)
        expect(glassActive(state)).toBe(false)
        expect(backgroundMaterialFor(state)).toBe('none')
        expect(windowOpacityOptions(state)).toEqual({})
        expect(windowBackgroundMaterialOptions(state, true, true)).toEqual({})
        expect(windowBackingOptions(state, '#ffffff')).toEqual({ backgroundColor: '#ffffff' })
        expect(hudFrostFor(state, true)).toEqual({ backgroundMaterial: 'none', vibrancy: null })
      }
    }
  })

  it('ignores a saved book and the shipped defaults in both appearances', () => {
    const book = normalizeBook({ mode: 'clear', base: { intensity: 80 }, light: { intensity: 50, fade: 40 } }, true)

    for (const appearance of ['light', 'dark'] as const) {
      for (const isWindows of [true, false]) {
        const resolved = resolveTranslucency(book, appearance, isWindows)

        expect(resolved.intensity).toBe(0)
        expect(windowOpacityFor(resolved)).toBe(1)
        expect(defaultTranslucencyState(appearance, true, isWindows).intensity).toBe(0)
      }
    }
  })

  it('keeps the opacity a bare hostile state would ask for at 1', () => {
    expect(windowOpacityFor({ intensity: 100, fade: 100, mode: 'clear', material: 'under-window', scope: 'window' })).toBe(1)
    expect(glassActive({ intensity: 100, fade: 0, mode: 'glass', material: 'under-window', scope: 'window' })).toBe(false)
  })
})
