/**
 * GarishGumdrop fork: lets the agent take a screenshot of the Hermes Desktop window.
 *
 * The renderer asks over IPC ('hermes:fork:captureWindow', exposed in preload.ts as
 * window.hermesFork.captureWindow); the main process captures the window that asked, saves a
 * PNG under <userData>/agent-screenshots, and returns its path. The desktop-settings-bridge
 * plugin relays the agent's request and hands the path back. See FORK.md.
 *
 * No focus changes, no restoring a minimised window: if the window cannot be captured as it is,
 * this fails with a plain reason instead of producing a blank image.
 */

import fs from 'node:fs'
import path from 'node:path'

import { app, BrowserWindow, ipcMain } from 'electron'

const KEEP = 30

export interface ForkWindowCapture {
  height: number
  path: string
  width: number
}

function stamp(): string {
  return new Date().toISOString().replace(/[:.]/g, '-')
}

async function pruneOld(dir: string): Promise<void> {
  try {
    const names = (await fs.promises.readdir(dir)).filter(n => n.startsWith('hermes-') && n.endsWith('.png')).sort()

    for (const name of names.slice(0, Math.max(0, names.length - KEEP))) {
      await fs.promises.unlink(path.join(dir, name)).catch(() => undefined)
    }
  } catch {
    // folder missing or unreadable: nothing to prune
  }
}

export function registerForkWindowCapture(): void {
  ipcMain.handle('hermes:fork:captureWindow', async (event): Promise<ForkWindowCapture> => {
    const contents = event.sender

    if (contents.isDestroyed()) {
      throw new Error('the window that asked for the screenshot has closed')
    }

    const win = BrowserWindow.fromWebContents(contents)

    if (win?.isMinimized()) {
      throw new Error('the Hermes window is minimised, so there is nothing on screen to capture')
    }

    const image = await contents.capturePage()

    if (image.isEmpty()) {
      throw new Error('the capture came back empty (the window may be hidden)')
    }

    const dir = path.join(app.getPath('userData'), 'agent-screenshots')
    await fs.promises.mkdir(dir, { recursive: true })
    const file = path.join(dir, `hermes-${stamp()}.png`)
    await fs.promises.writeFile(file, image.toPNG())
    await pruneOld(dir)
    const size = image.getSize()

    return { height: size.height, path: file, width: size.width }
  })
}
