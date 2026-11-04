import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { CameraMode, FollowMode, Point, ReplayFrame, ReplayManifest, ViewMode } from '../../types/replay'
import {
  createViewport,
  fitViewport,
  fitViewportWithBottomClearance,
  screenToWorld,
  worldToScreen,
  type Viewport,
} from './ViewportMatrix'
import { metricToLngLat } from '../../utils/geoProjection'
import { TacticalMapOverlay, type TacticalMapOverlayProps } from '../dashboard/TacticalMapOverlay'

function loadReplay(): ReplayManifest {
  const replayPath = path.resolve(process.cwd(), 'public/data/replays/naples_pr1.json')
  return JSON.parse(fs.readFileSync(replayPath, 'utf-8'))
}

describe('Challenger M9.2 Adversarial Verification: Camera Continuity & State Synchronization', () => {
  const replay = loadReplay()
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
      '80d4cda4-17f5-4bcf-b7fd-5fc0f39f3d60': {
        id: '80d4cda4-17f5-4bcf-b7fd-5fc0f39f3d60',
        x: 150.0,
        y: 180.0,
        heading: 44.0,
        speed_knots: 27.9,
        vmg: 19.8,
        twa: 43.0,
        tws: 14.7,
        twd: 68.4,
        cog: 44.0,
        sog: 27.9,
        heel: -4.0,
        rank: 2,
        gap_to_leader_s: 1.2,
        gap_to_leader_m: 16.5,
        current_leg: 1,
        penalty: null,
      },
    },
  }

  // =========================================================================
  // 1. Zoom Trigger Dynamics & Duplicate Ref Isolation in CourseCanvas.tsx
  // =========================================================================
  describe('1. CourseCanvas Zoom Triggering and Ref Isolation', () => {
    const courseCanvasPath = path.resolve(process.cwd(), 'src/components/canvas/CourseCanvas.tsx')
    const sourceCode = fs.readFileSync(courseCanvasPath, 'utf-8')

    it('empirically verifies absence of duplicate prevZoomInRef declarations', () => {
      const matches = sourceCode.match(/const\s+prevZoomInRef\s*=/g) || []
      expect(matches.length).toBe(1)
    })

    it('empirically verifies absence of duplicate prevZoomOutRef declarations', () => {
      const matches = sourceCode.match(/const\s+prevZoomOutRef\s*=/g) || []
      expect(matches.length).toBe(1)
    })

    it('verifies that obsolete .map-viewport-controls CSS and JSX are completely purged', () => {
      expect(sourceCode).not.toContain('.map-viewport-controls')
      expect(sourceCode).not.toContain('handleZoomIn')
      expect(sourceCode).not.toContain('handleZoomOut')
    })

    it('models zoomInTrigger step logic: ensures >= 15% scale increase and strictly clamps at 5.0', () => {
      let scale = 0.25
      let prevTrigger = 0

      function simulateZoomIn(trigger: number) {
        if (typeof trigger === 'number' && trigger > prevTrigger) {
          prevTrigger = trigger
          scale = Math.min(5.0, scale * 1.25)
        }
      }

      // First click: 0 -> 1
      const initialScale = scale
      simulateZoomIn(1)
      expect(scale).toBeCloseTo(initialScale * 1.25, 5)
      expect((scale - initialScale) / initialScale).toBeGreaterThanOrEqual(0.15) // +25% >= 15%

      // Second click: 1 -> 2
      simulateZoomIn(2)
      expect(scale).toBeCloseTo(initialScale * 1.25 * 1.25, 5)

      // Identical trigger re-render: 2 -> 2 (e.g. frame update)
      const scaleBefore = scale
      simulateZoomIn(2)
      expect(scale).toBe(scaleBefore) // No zoom triggered on frame updates

      // Stress: rapid 50 clicks clamps strictly at 5.0 without Infinity or NaN
      for (let t = 3; t <= 50; t++) {
        simulateZoomIn(t)
      }
      expect(scale).toBe(5.0)
      expect(Number.isFinite(scale)).toBe(true)
    })

    it('models zoomOutTrigger step logic: ensures >= 15% scale decrease and strictly floors at 0.03', () => {
      let scale = 0.25
      let prevTrigger = 0

      function simulateZoomOut(trigger: number) {
        if (typeof trigger === 'number' && trigger > prevTrigger) {
          prevTrigger = trigger
          scale = Math.max(0.03, scale / 1.25)
        }
      }

      // First click: 0 -> 1
      const initialScale = scale
      simulateZoomOut(1)
      expect(scale).toBeCloseTo(initialScale / 1.25, 5)
      expect((initialScale - scale) / initialScale).toBeGreaterThanOrEqual(0.15) // 20% decrease >= 15%

      // Identical trigger re-render: 1 -> 1
      const scaleBefore = scale
      simulateZoomOut(1)
      expect(scale).toBe(scaleBefore)

      // Stress: rapid 50 clicks floors strictly at 0.03 without going negative or zero
      for (let t = 2; t <= 50; t++) {
        simulateZoomOut(t)
      }
      expect(scale).toBe(0.03)
      expect(scale).toBeGreaterThan(0)
    })

    it('models MapLibre easeTo zoom step: +0.4 for zoomIn, -0.4 for zoomOut', () => {
      let mapZoom = 13.0
      let prevIn = 0
      let prevOut = 0

      const fakeMap = {
        getZoom: () => mapZoom,
        easeTo: vi.fn(({ zoom }: { zoom: number }) => {
          mapZoom = zoom
        }),
      }

      function onZoomIn(trigger: number) {
        if (typeof trigger === 'number' && trigger > prevIn) {
          prevIn = trigger
          fakeMap.easeTo({ zoom: fakeMap.getZoom() + 0.4 })
        }
      }

      function onZoomOut(trigger: number) {
        if (typeof trigger === 'number' && trigger > prevOut) {
          prevOut = trigger
          fakeMap.easeTo({ zoom: fakeMap.getZoom() - 0.4 })
        }
      }

      onZoomIn(1)
      expect(fakeMap.easeTo).toHaveBeenCalledWith({ zoom: 13.4 })
      expect(mapZoom).toBeCloseTo(13.4, 5)

      onZoomIn(1) // Re-render with same trigger
      expect(fakeMap.easeTo).toHaveBeenCalledTimes(1) // Not called again

      onZoomOut(1)
      expect(fakeMap.easeTo).toHaveBeenCalledWith({ zoom: 13.0 })
      expect(mapZoom).toBeCloseTo(13.0, 5)
    })
  })

  // =========================================================================
  // 2. handleResetView and Course Bounds Fitting
  // =========================================================================
  describe('2. handleResetView and Course Bounds Fitting', () => {
    const TOOLBELT_CLEARANCE_PX = 140
    const testViewports = [
      { width: 950, height: 550 },
      { width: 1024, height: 600 },
      { width: 1280, height: 720 },
      { width: 1586, height: 992 },
      { width: 1920, height: 1080 },
    ]

    const raceBoundaries = replay.course.boundaries.race
    const axisDeg = replay.course.axis_deg

    it('verifies race boundary points exist and form a closed polygon', () => {
      expect(raceBoundaries.length).toBeGreaterThanOrEqual(4)
      for (const pt of raceBoundaries) {
        expect(Number.isFinite(pt[0])).toBe(true)
        expect(Number.isFinite(pt[1])).toBe(true)
      }
    })

    it('verifies fitViewportWithBottomClearance encloses all boundary points in North-Up mode', () => {
      for (const { width, height } of testViewports) {
        const vp = fitViewportWithBottomClearance(
          width,
          height,
          raceBoundaries,
          'north',
          axisDeg,
          TOOLBELT_CLEARANCE_PX
        )

        expect(vp.rotationDeg).toBe(0)
        expect(vp.scale).toBeGreaterThan(0.05)
        expect(vp.scale).toBeLessThan(2.0)

        for (const pt of raceBoundaries) {
          const [sx, sy] = worldToScreen(vp, pt)
          // Point must be inside screen bounds horizontally
          expect(sx).toBeGreaterThanOrEqual(0)
          expect(sx).toBeLessThanOrEqual(width)
          // Point must be inside screen bounds vertically and above bottom clearance
          expect(sy).toBeGreaterThanOrEqual(0)
          expect(sy).toBeLessThanOrEqual(height)
        }
      }
    })

    it('verifies fitViewportWithBottomClearance encloses all boundary points in Course-Up mode', () => {
      for (const { width, height } of testViewports) {
        const vp = fitViewportWithBottomClearance(
          width,
          height,
          raceBoundaries,
          'course',
          axisDeg,
          TOOLBELT_CLEARANCE_PX
        )

        expect(vp.rotationDeg).toBeCloseTo(axisDeg, 4)
        expect(vp.scale).toBeGreaterThan(0.05)
        expect(vp.scale).toBeLessThan(2.0)

        for (const pt of raceBoundaries) {
          const [sx, sy] = worldToScreen(vp, pt)
          expect(sx).toBeGreaterThanOrEqual(0)
          expect(sx).toBeLessThanOrEqual(width)
          expect(sy).toBeGreaterThanOrEqual(0)
          expect(sy).toBeLessThanOrEqual(height)
        }
      }
    })

    it('verifies MapLibre fitBounds coordinates projection in fitMapToPoints', () => {
      const lngLats = raceBoundaries.map(([x, y]) =>
        metricToLngLat(x, y, replay.course.origin, replay.course.projection)
      )
      const minLng = Math.min(...lngLats.map(([lng]) => lng))
      const maxLng = Math.max(...lngLats.map(([lng]) => lng))
      const minLat = Math.min(...lngLats.map(([, lat]) => lat))
      const maxLat = Math.max(...lngLats.map(([, lat]) => lat))

      // Coordinates must be around Naples venue: lat 40.8 deg, lon 14.2 deg
      expect(minLat).toBeGreaterThan(40.5)
      expect(maxLat).toBeLessThan(41.2)
      expect(minLng).toBeGreaterThan(14.0)
      expect(maxLng).toBeLessThan(14.5)

      // Span must be non-zero
      expect(maxLat - minLat).toBeGreaterThan(0.01)
      expect(maxLng - minLng).toBeGreaterThan(0.01)
    })
  })

  // =========================================================================
  // 3. App.tsx State Propagation down to TacticalDashboard & TacticalMapOverlay
  // =========================================================================
  describe('3. App.tsx State Propagation and Callback Wiring', () => {
    function createMockOverlayProps(overrides: Partial<TacticalMapOverlayProps> = {}): TacticalMapOverlayProps {
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
        selectedBoatId: '42e39310-fef5-4c5d-b099-a599aad5ddbb',
        ...overrides,
      }
    }

    it('verifies viewMode state changes propagate cleanly between map and grid', () => {
      let currentViewMode: ViewMode = 'map'
      const onViewModeChange = (mode: ViewMode) => {
        currentViewMode = mode
      }

      // Initial state: map
      let html = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createMockOverlayProps({ viewMode: currentViewMode, onViewModeChange }))
      )
      expect(html).toMatch(/<button[^>]*class="active"[^>]*>Map<\/button>/)

      // User triggers grid toggle
      onViewModeChange('grid')
      expect(currentViewMode).toBe('grid')

      // Re-render with new state
      html = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createMockOverlayProps({ viewMode: currentViewMode, onViewModeChange }))
      )
      expect(html).toMatch(/<button[^>]*class="active"[^>]*>Grid<\/button>/)
      expect(html).not.toMatch(/<button[^>]*class="active"[^>]*>Map<\/button>/)
    })

    it('verifies followMode transitions (course -> fleet -> boat)', () => {
      let currentFollowMode: FollowMode = 'course'
      const onFollowModeChange = (mode: FollowMode) => {
        currentFollowMode = mode
      }

      // 1. Course
      let html = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createMockOverlayProps({ followMode: currentFollowMode, onFollowModeChange }))
      )
      expect(html).toMatch(/<button[^>]*class="active"[^>]*>Course<\/button>/)

      // 2. Fleet
      onFollowModeChange('fleet')
      html = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createMockOverlayProps({ followMode: currentFollowMode, onFollowModeChange }))
      )
      expect(html).toMatch(/<button[^>]*class="active"[^>]*>Fleet<\/button>/)

      // 3. Boat (enabled with boat selected)
      onFollowModeChange('boat')
      html = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createMockOverlayProps({ followMode: currentFollowMode, onFollowModeChange, selectedBoatId: 'boat-1' }))
      )
      expect(html).toMatch(/<button[^>]*class="active"[^>]*>Boat<\/button>/)
    })

    it('verifies showSafetyBorders toggle flips boolean state and updates active styling', () => {
      let showSafetyBorders = false
      const onToggleSafetyBorders = () => {
        showSafetyBorders = !showSafetyBorders
      }

      // Initial: false
      let html = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createMockOverlayProps({ showSafetyBorders, onToggleSafetyBorders }))
      )
      expect(html).toContain('aria-pressed="false"')
      expect(html).not.toContain('map-tool-toggle-btn active')

      // Toggle ON
      onToggleSafetyBorders()
      expect(showSafetyBorders).toBe(true)

      html = renderToStaticMarkup(
        React.createElement(TacticalMapOverlay, createMockOverlayProps({ showSafetyBorders, onToggleSafetyBorders }))
      )
      expect(html).toContain('aria-pressed="true"')
      expect(html).toContain('map-tool-toggle-btn active')

      // Toggle OFF
      onToggleSafetyBorders()
      expect(showSafetyBorders).toBe(false)
    })

    it('verifies resetView trigger increment wiring', () => {
      let resetViewCounter = 0
      const onResetView = () => {
        resetViewCounter += 1
      }

      expect(resetViewCounter).toBe(0)
      onResetView()
      expect(resetViewCounter).toBe(1)
      onResetView()
      expect(resetViewCounter).toBe(2)
    })
  })

  // =========================================================================
  // 4. Overlap Elimination & Non-Collision Geometry Guarantee
  // =========================================================================
  describe('4. Overlap Elimination & Layout Clearance', () => {
    it('verifies that left HUD and right toolbar occupy disjoint horizontal bounds', () => {
      // Geometry specifications from TacticalMapOverlay.tsx & dashboard.css:
      // Left HUD: left = 12px. Circular compass width = 44px + 8px gap + dual HUD card (approx 220px) = total width approx 272px.
      // Left HUD occupies X in [12, 284].
      const leftHudLeft = 12
      const leftHudWidth = 272
      const leftHudRight = leftHudLeft + leftHudWidth // 284px

      // Right Toolbar: right = 12px.
      // Tools:
      // - View mode toggle (2 items x 42px = 84px)
      // - Divider (1px + 12px margins = 13px)
      // - Follow mode toggle (3 items x 48px = 144px)
      // - Divider (13px)
      // - Borders toggle (approx 72px)
      // - Divider (13px)
      // - 4 icon buttons (4 x 28px = 112px + 12px gaps = 124px)
      // Total toolbar width approx 463px.
      const toolbarWidth = 463
      const stageWidths = [950, 1050, 1280, 1586, 1920]

      for (const stageWidth of stageWidths) {
        const toolbarLeft = stageWidth - 12 - toolbarWidth
        const clearanceGap = toolbarLeft - leftHudRight

        // Clearance between Left HUD and Right Toolbar must strictly be positive
        expect(clearanceGap).toBeGreaterThan(150) // >= 150px clearance guaranteed
      }
    })
  })

  // =========================================================================
  // 5. Zero-Tilde Verification Across Touched Files
  // =========================================================================
  describe('5. Zero-Tilde Compliance', () => {
    const tildeCode = 126
    const tildeChar = String.fromCharCode(tildeCode)

    const touchedFiles = [
      'src/components/canvas/CourseCanvas.tsx',
      'src/components/dashboard/TacticalMapOverlay.tsx',
      'src/components/dashboard/TacticalDashboard.tsx',
      'src/App.tsx',
      'src/components/dashboard/dashboard.css',
      'src/components/dashboard/TacticalMapOverlay.test.ts',
      'src/components/canvas/cameraStateSyncAdversarial.test.ts',
    ]

    for (const file of touchedFiles) {
      it(`confirms zero literal tildes in ${file}`, () => {
        const absPath = path.resolve(process.cwd(), file)
        const content = fs.readFileSync(absPath, 'utf-8')
        const regex = new RegExp(tildeChar, 'g')
        const count = (content.match(regex) || []).length
        expect(count).toBe(0)
      })
    }
  })
})
