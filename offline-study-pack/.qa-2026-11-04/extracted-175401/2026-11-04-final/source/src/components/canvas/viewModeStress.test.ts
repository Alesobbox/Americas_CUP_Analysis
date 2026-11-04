import { describe, expect, it, vi } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { drawStaticCourse } from './StaticCourseLayer'
import { createMaritimeMapStyle } from './mapStyle'
import { createViewport, worldToScreen, type Viewport } from './ViewportMatrix'
import type { Point, ReplayManifest, ViewMode } from '../../types/replay'

function loadReplayManifest(): ReplayManifest {
  const replayPath = path.resolve(__dirname, '../../../public/data/replays/naples_pr1.json')
  if (!fs.existsSync(replayPath)) {
    throw new Error(`Replay manifest not found at ${replayPath}`)
  }
  return JSON.parse(fs.readFileSync(replayPath, 'utf8'))
}

// Emulate readViewMode from App.tsx
function readViewModeFromStorage(storage: Record<string, string>): ViewMode {
  try {
    const raw = storage['regatta_view_mode'] ?? storage['regatta.viewMode']
    return raw === 'grid' ? 'grid' : 'map'
  } catch {
    return 'map'
  }
}

describe('Milestone 3 Stress Test: Map View vs Tactical Grid View Switcher', () => {
  const replay = loadReplayManifest()
  const axisDeg = replay.course.axis_deg

  // =========================================================================
  // 1. View Mode State & LocalStorage Persistence
  // =========================================================================
  describe('1. View Mode State & LocalStorage Persistence', () => {
    it('reads "grid" when regatta_view_mode is set to "grid"', () => {
      const storage: Record<string, string> = { regatta_view_mode: 'grid' }
      expect(readViewModeFromStorage(storage)).toBe('grid')
    })

    it('reads "map" when regatta_view_mode is set to "map"', () => {
      const storage: Record<string, string> = { regatta_view_mode: 'map' }
      expect(readViewModeFromStorage(storage)).toBe('map')
    })

    it('falls back to legacy "regatta.viewMode" when "regatta_view_mode" is absent', () => {
      const storage: Record<string, string> = { 'regatta.viewMode': 'grid' }
      expect(readViewModeFromStorage(storage)).toBe('grid')
    })

    it('prioritizes "regatta_view_mode" over legacy "regatta.viewMode"', () => {
      const storage: Record<string, string> = {
        regatta_view_mode: 'grid',
        'regatta.viewMode': 'map',
      }
      expect(readViewModeFromStorage(storage)).toBe('grid')
    })

    it('defaults safely to "map" when storage is empty', () => {
      const storage: Record<string, string> = {}
      expect(readViewModeFromStorage(storage)).toBe('map')
    })

    it('defaults safely to "map" for unknown or corrupted storage values', () => {
      expect(readViewModeFromStorage({ regatta_view_mode: 'satellite' })).toBe('map')
      expect(readViewModeFromStorage({ regatta_view_mode: '' })).toBe('map')
      expect(readViewModeFromStorage({ regatta_view_mode: '12345' })).toBe('map')
      expect(readViewModeFromStorage({ regatta_view_mode: 'GRID' })).toBe('map')
    })

    it('handles localStorage throwing SecurityError without crashing', () => {
      const throwingStorage = new Proxy({} as Record<string, string>, {
        get() {
          throw new Error('SecurityError: Access is denied in restricted iframe')
        },
      })
      expect(readViewModeFromStorage(throwingStorage)).toBe('map')
    })

    it('verifies App.tsx writes BOTH regatta_view_mode and regatta.viewMode in persistence effect', () => {
      const appSource = fs.readFileSync(path.resolve(__dirname, '../../App.tsx'), 'utf8')
      expect(appSource).toContain("window.localStorage.setItem('regatta_view_mode', viewMode)")
      expect(appSource).toContain("window.localStorage.setItem('regatta.viewMode', viewMode)")
      expect(appSource).toContain("window.localStorage.getItem('regatta_view_mode')")
    })
  })

  // =========================================================================
  // 3. Zero External Tile Requests in Grid View
  // =========================================================================
  describe('3. Zero External Tile Requests in Grid View', () => {


    it('verifies CourseCanvas.tsx disables MapLibre container and attribution in Grid View', () => {
      const canvasSource = fs.readFileSync(
        path.resolve(__dirname, 'CourseCanvas.tsx'),
        'utf8',
      )

      // MapLibre is active only when viewMode === 'map' && !isFallback
      expect(canvasSource).toContain("const mapIsActive = viewMode === 'map' && !isFallback")

      // Layer 0 MapLibre container is mounted only when mapIsActive is true
      expect(canvasSource).toContain('{mapIsActive && (')
      expect(canvasSource).toContain('ref={mapContainerRef}')

      // OSM attribution is conditionally rendered ONLY in map mode without fallback
      expect(canvasSource).toContain(
        "viewMode === 'map' && !isFallback && !isOfflineFallback && (",
      )
    })
  })

  // =========================================================================
  // 4. StaticCourseLayer Technical Water Surface & 250m Metric Grid
  // =========================================================================
  describe('4. StaticCourseLayer Technical Water Surface & 250m Metric Grid', () => {
    it('renders opaque pale water #edf4f6 and 250m metric grid when showWaterSurface is true', () => {
      const calls: Array<{ op: string; args?: unknown[] }> = []
      let currentStrokeStyle: unknown = null
      let currentFillStyle: unknown = null

      const mockContext = {
        clearRect: (...args: unknown[]) => calls.push({ op: 'clearRect', args }),
        get fillStyle() {
          return currentFillStyle
        },
        set fillStyle(val: unknown) {
          currentFillStyle = val
          calls.push({ op: 'set_fillStyle', args: [val] })
        },
        get strokeStyle() {
          return currentStrokeStyle
        },
        set strokeStyle(val: unknown) {
          currentStrokeStyle = val
          calls.push({ op: 'set_strokeStyle', args: [val] })
        },
        fillRect: (...args: unknown[]) => calls.push({ op: 'fillRect', args }),
        save: () => calls.push({ op: 'save' }),
        restore: () => calls.push({ op: 'restore' }),
        beginPath: () => calls.push({ op: 'beginPath' }),
        moveTo: (...args: unknown[]) => calls.push({ op: 'moveTo', args }),
        lineTo: (...args: unknown[]) => calls.push({ op: 'lineTo', args }),
        stroke: () => calls.push({ op: 'stroke' }),
        fill: () => calls.push({ op: 'fill' }),
        setLineDash: (...args: unknown[]) => calls.push({ op: 'setLineDash', args }),
        closePath: () => calls.push({ op: 'closePath' }),
      } as unknown as CanvasRenderingContext2D

      const width = 1200
      const height = 800
      const viewport = createViewport(width, height, [0, 0], 0.25, 'north', axisDeg)
      const boundaries = {
        race: replay.course.boundaries.race,
        safety: replay.course.boundaries.safety,
      }

      drawStaticCourse(mockContext, width, height, replay, viewport, boundaries, {
        showWaterSurface: true,
      })

      // 1. Clears canvas
      expect(calls[0].op).toBe('clearRect')
      expect(calls[0].args).toEqual([0, 0, width, height])

      // 2. Pale offline water surface fill.
      const fillStyleCall = calls.find(
        (c) => c.op === 'set_fillStyle' && c.args?.[0] === '#edf4f6',
      )
      expect(fillStyleCall).toBeDefined()
      const fillRectCall = calls.find((c) => c.op === 'fillRect')
      expect(fillRectCall).toBeDefined()
      expect(fillRectCall?.args).toEqual([0, 0, width, height])

      // 3. Quiet metric grid retains the same 250m world spacing.
      const gridStrokeStyleCall = calls.find(
        (c) => c.op === 'set_strokeStyle' && c.args?.[0] === 'rgba(89, 123, 139, 0.13)',
      )
      expect(gridStrokeStyleCall).toBeDefined()

      // 4. Multiple stroke calls for grid lines and boundaries
      const strokeCalls = calls.filter((c) => c.op === 'stroke')
      expect(strokeCalls.length).toBeGreaterThanOrEqual(10)

      // 5. Active race boundary corridor stroked and filled
      const boundaryFillCall = calls.find(
        (c) => c.op === 'set_fillStyle' && c.args?.[0] === 'rgba(50, 104, 134, 0.035)',
      )
      expect(boundaryFillCall).toBeDefined()
    })

    it('leaves canvas transparent (no fillRect) when showWaterSurface is false in Map View', () => {
      const calls: string[] = []
      const mockContext = {
        clearRect: () => calls.push('clearRect'),
        fillRect: () => calls.push('fillRect'),
        save: () => calls.push('save'),
        restore: () => calls.push('restore'),
        beginPath: () => calls.push('beginPath'),
        moveTo: () => calls.push('moveTo'),
        lineTo: () => calls.push('lineTo'),
        stroke: () => calls.push('stroke'),
        fill: () => calls.push('fill'),
        setLineDash: () => {},
        closePath: () => {},
      } as unknown as CanvasRenderingContext2D

      const width = 900
      const height = 620
      const viewport = createViewport(width, height, [0, 0], 0.25, 'north', axisDeg)
      const boundaries = {
        race: replay.course.boundaries.race,
        safety: replay.course.boundaries.safety,
      }

      drawStaticCourse(mockContext, width, height, replay, viewport, boundaries, {
        showWaterSurface: false,
      })

      expect(calls).toContain('clearRect')
      expect(calls).not.toContain('fillRect')
      expect(calls).toContain('stroke')
    })
  })

  // =========================================================================
  // 5. Camera Continuity & Zero Coordinate Drift
  // =========================================================================
  describe('5. Camera Continuity & Zero Coordinate Drift', () => {
    it('verifies CourseCanvas.tsx excludes mapIsActive from course reset effect dependencies', () => {
      const canvasSource = fs.readFileSync(
        path.resolve(__dirname, 'CourseCanvas.tsx'),
        'utf8',
      )

      // Locate effect 5: Course reset & initial fitting
      const effect5Index = canvasSource.indexOf('// 5. Course reset & initial fitting')
      expect(effect5Index).toBeGreaterThan(-1)

      const effect5Snippet = canvasSource.slice(effect5Index, effect5Index + 600)
      // Must NOT depend on mapIsActive
      expect(effect5Snippet).toContain('}, [cameraMode, replay, resetView, size.width, size.height])')
      expect(effect5Snippet).not.toContain('}, [cameraMode, mapIsActive, replay, resetView])')
    })

    it('verifies mathematical coordinate invariance between screen and world across view modes', () => {
      const width = 1440
      const height = 900
      const customCenter: Point = [350.25, -120.75]
      const scale = 0.35

      const vpNorth = createViewport(width, height, customCenter, scale, 'north', axisDeg)
      const vpCourse = createViewport(width, height, customCenter, scale, 'course', axisDeg)

      // Test point inside racing boundary
      const testPoint: Point = [500, 200]

      const screenNorth = worldToScreen(vpNorth, testPoint)
      const screenCourse = worldToScreen(vpCourse, testPoint)

      // North Up: rotationDeg = 0
      expect(vpNorth.rotationDeg).toBe(0)
      const expectedNorthX = width / 2 + (testPoint[0] - customCenter[0]) * scale
      const expectedNorthY = height / 2 - (testPoint[1] - customCenter[1]) * scale
      expect(screenNorth[0]).toBeCloseTo(expectedNorthX, 5)
      expect(screenNorth[1]).toBeCloseTo(expectedNorthY, 5)

      // Course Up: rotationDeg = axisDeg
      expect(vpCourse.rotationDeg).toBeCloseTo(axisDeg, 4)
      // Screen distance to center must equal Euclidean metric distance * scale in both orientations
      const distFromCenterScreenNorth = Math.hypot(
        screenNorth[0] - width / 2,
        screenNorth[1] - height / 2,
      )
      const distFromCenterScreenCourse = Math.hypot(
        screenCourse[0] - width / 2,
        screenCourse[1] - height / 2,
      )
      const worldMetricDist = Math.hypot(
        testPoint[0] - customCenter[0],
        testPoint[1] - customCenter[1],
      )

      expect(distFromCenterScreenNorth).toBeCloseTo(worldMetricDist * scale, 5)
      expect(distFromCenterScreenCourse).toBeCloseTo(worldMetricDist * scale, 5)
    })
  })
})
