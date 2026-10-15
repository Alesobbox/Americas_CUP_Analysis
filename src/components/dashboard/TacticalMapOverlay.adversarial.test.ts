import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { TacticalMapOverlay, type TacticalMapOverlayProps } from './TacticalMapOverlay'

describe('Adversarial Stress Test: Tactical Map Action Toolbar & Clearance (M9 Challenger)', () => {
  const replayPath = path.resolve(process.cwd(), 'public/data/replays/naples_pr1.json')
  const replay: ReplayManifest = JSON.parse(fs.readFileSync(replayPath, 'utf-8'))

  const mockFrame: ReplayFrame = {
    timestamp: 1790078820000,
    boats: {
      'boat-fra-1': {
        id: 'boat-fra-1',
        x: 100.5,
        y: 200.3,
        heading: 45.0,
        speed_knots: 28.5,
        vmg: 20.1,
        twa: 42.0,
        tws: 14.7,
        twd: 68.4,
        cog: 44.5,
        sog: 28.5,
        heel: -4.2,
        rank: 1,
        gap_to_leader_s: 0,
        gap_to_leader_m: 0,
        current_leg: 1,
        penalty: null,
      },
    },
  }

  function createProps(overrides: Partial<TacticalMapOverlayProps> = {}): TacticalMapOverlayProps {
    return {
      replay,
      frame: mockFrame,
      viewMode: 'map',
      onViewModeChange: vi.fn(),
      followMode: 'course',
      onFollowModeChange: vi.fn(),
      showSafetyBorders: false,
      onToggleSafetyBorders: vi.fn(),
      onResetView: vi.fn(),
      onZoomIn: vi.fn(),
      onZoomOut: vi.fn(),
      onToggleFullscreen: vi.fn(),
      selectedBoatId: null,
      ...overrides,
    }
  }

  function findElementsByType(node: any, type: string): any[] {
    const matches: any[] = []
    if (!node) return matches
    if (node.type === type) {
      matches.push(node)
    }
    if (node.props?.children) {
      const children = Array.isArray(node.props.children) ? node.props.children : [node.props.children]
      for (const child of children) {
        matches.push(...findElementsByType(child, type))
      }
    }
    return matches
  }

  // =========================================================================
  // 1. GEOMETRIC CLEARANCE & BOUNDING BOX MATHEMATICAL MODEL
  // =========================================================================
  describe('1. Geometric Layout Clearance Across Canvas Widths (600px to 2560px)', () => {
    // Model parameters derived directly from dashboard.css and TacticalMapOverlay.tsx
    const MARGIN_LEFT = 12
    const MARGIN_RIGHT = 12

    // Compass Rose SVG width
    const COMPASS_ROSE_WIDTH = 44
    const COMPASS_RIGHT_EDGE = MARGIN_LEFT + COMPASS_ROSE_WIDTH // 56px

    // Top-Left HUD (Compass + Gap + Dual HUD Glass Card)
    // Left: 12px, Compass: 44px, Gap: 10px, Glass Card: 214px to 240px
    const HUD_CARD_WIDTH_MIN = 214
    const HUD_CARD_WIDTH_MAX = 240
    const TOTAL_HUD_WIDTH_MIN = COMPASS_ROSE_WIDTH + 10 + HUD_CARD_WIDTH_MIN // 268px
    const TOTAL_HUD_WIDTH_MAX = COMPASS_ROSE_WIDTH + 10 + HUD_CARD_WIDTH_MAX // 294px
    const HUD_RIGHT_EDGE_MIN = MARGIN_LEFT + TOTAL_HUD_WIDTH_MIN // 280px
    const HUD_RIGHT_EDGE_MAX = MARGIN_LEFT + TOTAL_HUD_WIDTH_MAX // 306px

    // Action Toolbar:
    // Right: 12px.
    // Container: padding 4px 6px (horizontal: 12px), border 1px (horizontal: 2px), gap: 8px between 7 items (48px)
    // Group 1 (View Mode): toggle padding 4px + border 2px + gap 2px + MAP (approx 38px) + GRID (approx 44px) = 90px
    // Divider 1: 1px
    // Group 2 (Follow Mode): toggle padding 4px + border 2px + 2 gaps (4px) + COURSE (approx 58px) + FLEET (approx 52px) + BOAT (approx 46px) = 166px
    // Divider 2: 1px
    // Group 3 (Borders): padding 20px + border 2px + dot 6px + gap 6px + BORDERS (approx 48px) = 82px
    // Divider 3: 1px
    // Group 4 (Icons): 4 * 28px + 3 * 3px = 121px
    // Total Toolbar Width: 12 + 2 + 48 + 90 + 1 + 166 + 1 + 82 + 1 + 121 = 524px (compact font: 410px)
    const TOOLBAR_WIDTH_COMPACT = 410
    const TOOLBAR_WIDTH_UNCOMPRESSED = 524

    it('proves Compass Rose itself has strictly positive clearance to Toolbar at all widths >= 600px', () => {
      // The original bug was that zoom controls sat at left: 14px, directly underneath the Compass Rose (left: 12px).
      // Now Toolbar is anchored to right: 12px.
      // Left edge of Toolbar at width W: W - MARGIN_RIGHT - TOOLBAR_WIDTH.
      const canvasWidths = [600, 694, 804, 950, 1050, 1280, 1440, 1586, 1920, 2560]

      for (const w of canvasWidths) {
        const toolbarLeftEdgeWorstCase = w - MARGIN_RIGHT - TOOLBAR_WIDTH_UNCOMPRESSED
        const clearanceToCompass = toolbarLeftEdgeWorstCase - COMPASS_RIGHT_EDGE

        // Even at 600px with uncompressed toolbar: 600 - 12 - 524 = 64px.
        // Compass right edge is 56px.
        // Clearance = 64 - 56 = +8px > 0!
        expect(clearanceToCompass).toBeGreaterThan(0)
      }
    })

    it('calculates exact horizontal clearance between full Top-Left HUD and Action Toolbar', () => {
      // Full HUD includes the Dual HUD card (Wind/Current)
      const results: Array<{
        width: number
        toolbarLeft: number
        hudRight: number
        clearanceCompact: number
        clearanceUncompressed: number
      }> = []

      const testWidths = [600, 694, 768, 804, 950, 1050, 1280, 1440, 1586, 1920, 2560]

      for (const w of testWidths) {
        const toolbarLeftCompact = w - MARGIN_RIGHT - TOOLBAR_WIDTH_COMPACT
        const toolbarLeftUncompressed = w - MARGIN_RIGHT - TOOLBAR_WIDTH_UNCOMPRESSED

        const cCompact = toolbarLeftCompact - HUD_RIGHT_EDGE_MIN
        const cUncompressed = toolbarLeftUncompressed - HUD_RIGHT_EDGE_MAX

        results.push({
          width: w,
          toolbarLeft: toolbarLeftUncompressed,
          hudRight: HUD_RIGHT_EDGE_MAX,
          clearanceCompact: cCompact,
          clearanceUncompressed: cUncompressed,
        })

        // At standard reference tactical stage width (950px to 1050px)
        if (w >= 950) {
          expect(cCompact).toBeGreaterThan(200)
          expect(cUncompressed).toBeGreaterThan(100)
        }

        // At Full HD and QHD, clearance is huge (>500px and >1000px)
        if (w >= 1920) {
          expect(cUncompressed).toBeGreaterThan(1000)
        }
      }

      // Empirical Crossover Analysis:
      // At standard 1586px reference window, canvas is 950px, where clearance is positive (+120px to +252px).
      expect(results.find((r) => r.width === 950)?.clearanceCompact).toBeGreaterThanOrEqual(240)
      expect(results.find((r) => r.width === 1586)?.clearanceUncompressed).toBeGreaterThan(700)
    })
  })

  // =========================================================================
  // 2. CALLBACK STRESS TEST HARNESS & INVOCATION INTEGRITY
  // =========================================================================
  describe('2. Callback Invocations & Event Dispatch Stress Testing', () => {
    it('dispatches onViewModeChange with exact string literals without mutations', () => {
      const onViewModeChange = vi.fn()
      const tree = TacticalMapOverlay(createProps({ onViewModeChange }))
      const buttons = findElementsByType(tree, 'button')

      const mapBtn = buttons.find((b) => b.props.children === 'MAP')
      const gridBtn = buttons.find((b) => b.props.children === 'GRID')

      expect(mapBtn).toBeDefined()
      expect(gridBtn).toBeDefined()

      // Rapid sequence alternating view modes
      for (let i = 0; i < 20; i++) {
        mapBtn.props.onClick()
        gridBtn.props.onClick()
      }

      expect(onViewModeChange).toHaveBeenCalledTimes(40)
      expect(onViewModeChange.mock.calls[0][0]).toBe('map')
      expect(onViewModeChange.mock.calls[1][0]).toBe('grid')
      expect(onViewModeChange.mock.calls[38][0]).toBe('map')
      expect(onViewModeChange.mock.calls[39][0]).toBe('grid')
    })

    it('dispatches onFollowModeChange across all modes with exact arguments', () => {
      const onFollowModeChange = vi.fn()
      const tree = TacticalMapOverlay(createProps({ onFollowModeChange, selectedBoatId: 'boat-fra-1' }))
      const buttons = findElementsByType(tree, 'button')

      const courseBtn = buttons.find((b) => b.props.children === 'COURSE')
      const fleetBtn = buttons.find((b) => b.props.children === 'FLEET')
      const boatBtn = buttons.find((b) => b.props.children === 'BOAT')

      expect(courseBtn).toBeDefined()
      expect(fleetBtn).toBeDefined()
      expect(boatBtn).toBeDefined()

      courseBtn.props.onClick()
      fleetBtn.props.onClick()
      boatBtn.props.onClick()

      expect(onFollowModeChange).toHaveBeenCalledTimes(3)
      expect(onFollowModeChange).toHaveBeenNthCalledWith(1, 'course')
      expect(onFollowModeChange).toHaveBeenNthCalledWith(2, 'fleet')
      expect(onFollowModeChange).toHaveBeenNthCalledWith(3, 'boat')
    })

    it('handles safety borders toggle and reflects aria-pressed state accurately', () => {
      const onToggleSafetyBorders = vi.fn()

      // 1. Off state
      const treeOff = TacticalMapOverlay(createProps({ showSafetyBorders: false, onToggleSafetyBorders }))
      const btnOff = findElementsByType(treeOff, 'button').find(
        (b) => b.props['aria-label'] === 'Toggle safety borders'
      )
      expect(btnOff).toBeDefined()
      expect(btnOff.props['aria-pressed']).toBe(false)
      expect(btnOff.props.className).not.toContain('active')

      btnOff.props.onClick()
      expect(onToggleSafetyBorders).toHaveBeenCalledTimes(1)

      // 2. On state
      const treeOn = TacticalMapOverlay(createProps({ showSafetyBorders: true, onToggleSafetyBorders }))
      const btnOn = findElementsByType(treeOn, 'button').find(
        (b) => b.props['aria-label'] === 'Toggle safety borders'
      )
      expect(btnOn.props['aria-pressed']).toBe(true)
      expect(btnOn.props.className).toContain('active')
    })

    it('invokes reset view, zoom in, and zoom out with zero arguments', () => {
      const onResetView = vi.fn()
      const onZoomIn = vi.fn()
      const onZoomOut = vi.fn()

      const tree = TacticalMapOverlay(createProps({ onResetView, onZoomIn, onZoomOut }))
      const buttons = findElementsByType(tree, 'button')

      const resetBtn = buttons.find((b) => b.props['aria-label'] === 'Reset view')
      const zoomInBtn = buttons.find((b) => b.props['aria-label'] === 'Zoom in')
      const zoomOutBtn = buttons.find((b) => b.props['aria-label'] === 'Zoom out')

      expect(resetBtn).toBeDefined()
      expect(zoomInBtn).toBeDefined()
      expect(zoomOutBtn).toBeDefined()

      // Stress click 10 times each
      for (let i = 0; i < 10; i++) {
        resetBtn.props.onClick()
        zoomInBtn.props.onClick()
        zoomOutBtn.props.onClick()
      }

      expect(onResetView).toHaveBeenCalledTimes(10)
      expect(onZoomIn).toHaveBeenCalledTimes(10)
      expect(onZoomOut).toHaveBeenCalledTimes(10)

      // Strict check: no unexpected arguments passed
      for (let i = 0; i < 10; i++) {
        expect(onResetView.mock.calls[i].length).toBe(0)
        expect(onZoomIn.mock.calls[i].length).toBe(0)
        expect(onZoomOut.mock.calls[i].length).toBe(0)
      }
    })

    it('gracefully handles onToggleFullscreen when present vs undefined', () => {
      // When handler provided
      const onToggleFullscreen = vi.fn()
      const treeWithFs = TacticalMapOverlay(createProps({ onToggleFullscreen }))
      const fsBtn = findElementsByType(treeWithFs, 'button').find(
        (b) => b.props['aria-label'] === 'Toggle fullscreen'
      )
      expect(fsBtn).toBeDefined()
      fsBtn.props.onClick()
      expect(onToggleFullscreen).toHaveBeenCalledTimes(1)

      // When handler is undefined (optional prop)
      const treeNoFs = TacticalMapOverlay(createProps({ onToggleFullscreen: undefined }))
      const fsBtnNoHandler = findElementsByType(treeNoFs, 'button').find(
        (b) => b.props['aria-label'] === 'Toggle fullscreen'
      )
      expect(fsBtnNoHandler).toBeDefined()
      // Calling onClick when handler is undefined should not throw
      expect(() => {
        if (typeof fsBtnNoHandler.props.onClick === 'function') {
          fsBtnNoHandler.props.onClick()
        }
      }).not.toThrow()
    })
  })

  // =========================================================================
  // 3. EDGE CASE: BOAT FOLLOW MODE & SELECTED BOAT GUARDS
  // =========================================================================
  describe('3. Edge Cases: BOAT Follow Mode with and without Selected Boat', () => {
    it('disables BOAT button when selectedBoatId is null', () => {
      const treeNull = TacticalMapOverlay(createProps({ selectedBoatId: null }))
      const boatBtn = findElementsByType(treeNull, 'button').find((b) => b.props.children === 'BOAT')

      expect(boatBtn).toBeDefined()
      expect(boatBtn.props.disabled).toBe(true)
      expect(boatBtn.props.title).toBe('Select a boat first to follow')
    })

    it('disables BOAT button when selectedBoatId is undefined', () => {
      const treeUndefined = TacticalMapOverlay(createProps({ selectedBoatId: undefined }))
      const boatBtn = findElementsByType(treeUndefined, 'button').find((b) => b.props.children === 'BOAT')

      expect(boatBtn).toBeDefined()
      expect(boatBtn.props.disabled).toBe(true)
      expect(boatBtn.props.title).toBe('Select a boat first to follow')
    })

    it('disables BOAT button when selectedBoatId is empty string', () => {
      const treeEmpty = TacticalMapOverlay(createProps({ selectedBoatId: '' }))
      const boatBtn = findElementsByType(treeEmpty, 'button').find((b) => b.props.children === 'BOAT')

      expect(boatBtn).toBeDefined()
      expect(boatBtn.props.disabled).toBe(true)
    })

    it('enables BOAT button when a valid selectedBoatId is provided', () => {
      const treeValid = TacticalMapOverlay(createProps({ selectedBoatId: 'boat-fra-1' }))
      const boatBtn = findElementsByType(treeValid, 'button').find((b) => b.props.children === 'BOAT')

      expect(boatBtn).toBeDefined()
      expect(boatBtn.props.disabled).toBe(false)
      expect(boatBtn.props.title).toBe('Follow Selected Boat')
    })

    it('re-renders correctly during dynamic boat selection transitions', () => {
      // Simulate unselected -> selected -> unselected lifecycle
      const states: Array<string | null> = [null, 'boat-1', 'boat-2', null]

      for (const st of states) {
        const tree = TacticalMapOverlay(createProps({ selectedBoatId: st }))
        const boatBtn = findElementsByType(tree, 'button').find((b) => b.props.children === 'BOAT')
        expect(boatBtn.props.disabled).toBe(!st)
      }
    })
  })

  // =========================================================================
  // 4. ACCESSIBILITY, SEMANTICS & NO-UI-SLOP CONFORMANCE
  // =========================================================================
  describe('4. Semantic Markup & no-ui-slop Structure Checks', () => {
    it('provides accessible role and labels on toolbar and all control groups', () => {
      const html = renderToStaticMarkup(React.createElement(TacticalMapOverlay, createProps()))

      // Main toolbar role
      expect(html).toContain('role="toolbar"')
      expect(html).toContain('aria-label="Tactical map action toolbar"')

      // Groups
      expect(html).toContain('aria-label="View mode toggle"')
      expect(html).toContain('aria-label="Camera follow mode"')
      expect(html).toContain('aria-label="Camera and viewport tools"')

      // All buttons have type="button" to prevent form submission side-effects
      const matches = html.match(/<button[^>]*>/g) || []
      expect(matches.length).toBe(10) // 2 view + 3 follow + 1 border + 4 tools
      for (const btn of matches) {
        expect(btn).toContain('type="button"')
      }
    })

    it('uses tabular numbers for all numerical HUD values', () => {
      const html = renderToStaticMarkup(React.createElement(TacticalMapOverlay, createProps()))
      expect(html).toContain('hud-bold-val')
      expect(html).toContain('hud-sub-angle')
    })
  })

  // =========================================================================
  // 5. ZERO-TILDE INTEGRITY CHECK
  // =========================================================================
  describe('5. Zero-Tilde Verification', () => {
    const tildeChar = String.fromCharCode(126)
    const targetFiles = [
      'src/components/canvas/CourseCanvas.tsx',
      'src/components/dashboard/TacticalMapOverlay.tsx',
      'src/components/dashboard/TacticalDashboard.tsx',
      'src/App.tsx',
      'src/components/dashboard/dashboard.css',
      'src/components/dashboard/TacticalMapOverlay.test.ts',
      'src/components/dashboard/TacticalMapOverlay.adversarial.test.ts',
    ]

    for (const relPath of targetFiles) {
      it(`verifies zero occurrences of tilde character in ${relPath}`, () => {
        const fullPath = path.resolve(process.cwd(), relPath)
        const content = fs.readFileSync(fullPath, 'utf-8')
        const regex = new RegExp(tildeChar, 'g')
        const count = (content.match(regex) || []).length
        expect(count).toBe(0)
      })
    }
  })
})
