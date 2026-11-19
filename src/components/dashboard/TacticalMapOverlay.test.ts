import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { TacticalMapOverlay, type TacticalMapOverlayProps } from './TacticalMapOverlay'

describe('TacticalMapOverlay & Action Toolbar Tests (Milestone M9 / R2)', () => {
  const liveReplayPath = path.resolve(process.cwd(), 'public/data/replays/naples_pr1.json')
  const replayPath = fs.existsSync(liveReplayPath)
    ? liveReplayPath
    : path.resolve(process.cwd(), 'tests/fixtures/synthetic_replay.json')
  const replay: ReplayManifest = JSON.parse(fs.readFileSync(replayPath, 'utf-8'))

  const mockFrame: ReplayFrame = {
    timestamp: 1790078820000,
    boats: {
      '42e39310-fef5-4c5d-b099-a599aad5ddbb': {
        id: '42e39310-fef5-4c5d-b099-a599aad5ddbb',
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

  // Recursive element traversal helper
  function findElementsByType(node: any, type: string): any[] {
    const matches: any[] = []
    if (!node) return matches
    if (node.type === type) {
      matches.push(node)
    }
    if (node.props?.children) {
      const children = Array.isArray(node.props.children)
        ? node.props.children
        : [node.props.children]
      for (const child of children) {
        matches.push(...findElementsByType(child, type))
      }
    }
    return matches
  }

  describe('1. Static Markup & Structure Verification', () => {
    it('renders the complete overlay without throwing', () => {
      const props = createProps()
      const html = renderToStaticMarkup(React.createElement(TacticalMapOverlay, props))
      expect(html).toContain('tactical-map-overlay')
      expect(html).toContain('map-top-left-hud')
      expect(html).toContain('map-top-right-toolbar')
      expect(html).toContain('map-bottom-scale-bar')
    })

    it('renders the compass rose and recorded wind without a permanent current placeholder', () => {
      const props = createProps()
      const html = renderToStaticMarkup(React.createElement(TacticalMapOverlay, props))
      expect(html).toContain('compass-rose-widget')
      expect(html).toContain('dual-hud-glass-card')
      expect(html).toContain('Official wind (replay)')
      expect(html).not.toContain('>Current<')
      expect(html).not.toContain('hud-card-v-divider')
      expect(html.match(/class="hud-metric-cell"/g) ?? []).toHaveLength(1)
      expect(html).toContain('kt')
    })

    it('still explains missing supported wind observations without substituting zero', () => {
      const missingWind = { ...replay, wind: { ...replay.wind, timeline: [] } }
      const html = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createProps({ replay: missingWind }))
      )
      expect(html).toContain('Official wind (replay)')
      expect(html).toContain('Unavailable')
      expect(html).toContain('No prior source sample')
      expect(html).not.toContain('0.0 kt')
      expect(html).not.toContain('>Current<')
    })

    it('renders all 6 tools in the top-right toolbar', () => {
      const props = createProps()
      const html = renderToStaticMarkup(React.createElement(TacticalMapOverlay, props))

      // 1. View Mode (MAP / GRID)
      expect(html).toContain('Map')
      expect(html).toContain('Grid')

      // 2. Follow Mode (COURSE / FLEET / BOAT)
      expect(html).toContain('Course')
      expect(html).toContain('Fleet')
      expect(html).toContain('Boat')

      // 3. Safety Borders
      expect(html).toContain('Borders')
      expect(html).toContain('tool-indicator-dot')

      // 4. Reset View
      expect(html).toContain('⟲')

      // 5. Zoom In & Zoom Out
      expect(html).toContain('+')
      expect(html).toContain('−')

      // 6. Fullscreen
      expect(html).toContain('⛶')
    })
  })

  describe('2. State and Conditional Classes', () => {
    it('highlights active viewMode correctly (MAP vs GRID)', () => {
      // viewMode = 'map'
      const htmlMap = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createProps({ viewMode: 'map' }))
      )
      expect(htmlMap).toMatch(/<button[^>]*class="active"[^>]*>Map<\/button>/)
      expect(htmlMap).not.toMatch(/<button[^>]*class="active"[^>]*>Grid<\/button>/)

      // viewMode = 'grid'
      const htmlGrid = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createProps({ viewMode: 'grid' }))
      )
      expect(htmlGrid).toMatch(/<button[^>]*class="active"[^>]*>Grid<\/button>/)
      expect(htmlGrid).not.toMatch(/<button[^>]*class="active"[^>]*>Map<\/button>/)
    })

    it('highlights active followMode correctly (COURSE, FLEET, BOAT)', () => {
      const htmlCourse = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createProps({ followMode: 'course' }))
      )
      expect(htmlCourse).toMatch(/<button[^>]*class="active"[^>]*>Course<\/button>/)

      const htmlFleet = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createProps({ followMode: 'fleet' }))
      )
      expect(htmlFleet).toMatch(/<button[^>]*class="active"[^>]*>Fleet<\/button>/)

      const htmlBoat = renderToStaticMarkup(
        React.createElement(
          TacticalMapOverlay,
          createProps({ followMode: 'boat', selectedBoatId: 'boat-1' })
        )
      )
      expect(htmlBoat).toMatch(/<button[^>]*class="active"[^>]*>Boat<\/button>/)
    })

    it('disables BOAT follow mode button when selectedBoatId is null', () => {
      const htmlNoBoat = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createProps({ selectedBoatId: null }))
      )
      expect(htmlNoBoat).toMatch(/<button[^>]*disabled=""[^>]*>Boat<\/button>/)

      const htmlWithBoat = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createProps({ selectedBoatId: 'boat-1' }))
      )
      expect(htmlWithBoat).not.toMatch(/<button[^>]*disabled=""[^>]*>Boat<\/button>/)
    })

    it('updates BORDERS button active class and aria-pressed based on showSafetyBorders', () => {
      const htmlOff = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createProps({ showSafetyBorders: false }))
      )
      expect(htmlOff).toContain('aria-pressed="false"')
      expect(htmlOff).not.toContain('map-tool-toggle-btn active')

      const htmlOn = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createProps({ showSafetyBorders: true }))
      )
      expect(htmlOn).toContain('aria-pressed="true"')
      expect(htmlOn).toContain('map-tool-toggle-btn active')
    })
  })

  describe('3. Callback Dispatch Verification', () => {
    it('dispatches onViewModeChange with "map" and "grid"', () => {
      const onViewModeChange = vi.fn()
      const tree = TacticalMapOverlay(createProps({ onViewModeChange }))
      const buttons = findElementsByType(tree, 'button')

      const mapBtn = buttons.find((b) => b.props.children === 'Map')
      const gridBtn = buttons.find((b) => b.props.children === 'Grid')

      expect(mapBtn).toBeDefined()
      expect(gridBtn).toBeDefined()

      mapBtn.props.onClick()
      expect(onViewModeChange).toHaveBeenCalledWith('map')

      gridBtn.props.onClick()
      expect(onViewModeChange).toHaveBeenCalledWith('grid')
    })

    it('dispatches onFollowModeChange with "course", "fleet", and "boat"', () => {
      const onFollowModeChange = vi.fn()
      const tree = TacticalMapOverlay(createProps({ onFollowModeChange, selectedBoatId: 'boat-1' }))
      const buttons = findElementsByType(tree, 'button')

      const courseBtn = buttons.find((b) => b.props.children === 'Course')
      const fleetBtn = buttons.find((b) => b.props.children === 'Fleet')
      const boatBtn = buttons.find((b) => b.props.children === 'Boat')

      expect(courseBtn).toBeDefined()
      expect(fleetBtn).toBeDefined()
      expect(boatBtn).toBeDefined()

      courseBtn.props.onClick()
      expect(onFollowModeChange).toHaveBeenCalledWith('course')

      fleetBtn.props.onClick()
      expect(onFollowModeChange).toHaveBeenCalledWith('fleet')

      boatBtn.props.onClick()
      expect(onFollowModeChange).toHaveBeenCalledWith('boat')
    })

    it('dispatches onToggleSafetyBorders when BORDERS button is clicked', () => {
      const onToggleSafetyBorders = vi.fn()
      const tree = TacticalMapOverlay(createProps({ onToggleSafetyBorders }))
      const buttons = findElementsByType(tree, 'button')

      const bordersBtn = buttons.find((b) => b.props['aria-label'] === 'Toggle safety borders')
      expect(bordersBtn).toBeDefined()

      bordersBtn.props.onClick()
      expect(onToggleSafetyBorders).toHaveBeenCalledTimes(1)
    })

    it('dispatches onResetView when ⟲ button is clicked', () => {
      const onResetView = vi.fn()
      const tree = TacticalMapOverlay(createProps({ onResetView }))
      const buttons = findElementsByType(tree, 'button')

      const resetBtn = buttons.find((b) => b.props['aria-label'] === 'Reset view')
      expect(resetBtn).toBeDefined()

      resetBtn.props.onClick()
      expect(onResetView).toHaveBeenCalledTimes(1)
    })

    it('dispatches onZoomIn when + button is clicked', () => {
      const onZoomIn = vi.fn()
      const tree = TacticalMapOverlay(createProps({ onZoomIn }))
      const buttons = findElementsByType(tree, 'button')

      const zoomInBtn = buttons.find((b) => b.props['aria-label'] === 'Zoom in')
      expect(zoomInBtn).toBeDefined()

      zoomInBtn.props.onClick()
      expect(onZoomIn).toHaveBeenCalledTimes(1)
    })

    it('dispatches onZoomOut when − button is clicked', () => {
      const onZoomOut = vi.fn()
      const tree = TacticalMapOverlay(createProps({ onZoomOut }))
      const buttons = findElementsByType(tree, 'button')

      const zoomOutBtn = buttons.find((b) => b.props['aria-label'] === 'Zoom out')
      expect(zoomOutBtn).toBeDefined()

      zoomOutBtn.props.onClick()
      expect(onZoomOut).toHaveBeenCalledTimes(1)
    })

    it('dispatches onToggleFullscreen when ⛶ button is clicked', () => {
      const onToggleFullscreen = vi.fn()
      const tree = TacticalMapOverlay(createProps({ onToggleFullscreen }))
      const buttons = findElementsByType(tree, 'button')

      const fsBtn = buttons.find((b) => b.props['aria-label'] === 'Toggle fullscreen')
      expect(fsBtn).toBeDefined()

      fsBtn.props.onClick()
      expect(onToggleFullscreen).toHaveBeenCalledTimes(1)
    })
  })

  describe('4. Zero-Tilde Verification Across Touched Files', () => {
    const tildeChar = String.fromCharCode(126)
    const touchedFiles = [
      'src/components/canvas/CourseCanvas.tsx',
      'src/components/dashboard/TacticalMapOverlay.tsx',
      'src/components/dashboard/TacticalDashboard.tsx',
      'src/App.tsx',
      'src/components/dashboard/dashboard.css',
      'src/components/dashboard/TacticalMapOverlay.test.ts',
    ]

    for (const relPath of touchedFiles) {
      it(`verifies zero occurrences of tilde in ${relPath}`, () => {
        const fullPath = path.resolve(process.cwd(), relPath)
        const content = fs.readFileSync(fullPath, 'utf-8')
        const regex = new RegExp(tildeChar, 'g')
        const tildeCount = (content.match(regex) || []).length
        expect(tildeCount).toBe(0)
      })
    }
  })
})
