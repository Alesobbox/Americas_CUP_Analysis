import { describe, expect, it, vi } from 'vitest'
import {
  AC40_COCKPIT_PORT,
  AC40_COCKPIT_STARBOARD,
  AC40_DIMENSIONS,
  AC40_FOIL_WING_PORT,
  AC40_FOIL_WING_STARBOARD,
  AC40_HULL_POLYGON,
  AC40_KEEP_CLEAR_BORDER,
  AC40_PLATFORM_BORDER,
  AC75_DIMENSIONS,
  AC75_FOIL_WING_PORT,
  AC75_FOIL_WING_STARBOARD,
  AC75_HULL_POLYGON,
  AC75_KEEP_CLEAR_BORDER,
  AC75_PLATFORM_BORDER,
  computeBoatRenderScale,
  getBoatDimensions,
  getSafetyBorders,
  renderFoilingBoatModel,
  tracePolygonInCanvas,
} from './boatModels'

describe('Parametric Foiling Fleet Models (AC40 & AC75)', () => {
  describe('AC40 Class Rule V2.11 Geometry & Dimensions', () => {
    it('verifies AC40 canonical dimensions match one-design specifications', () => {
      expect(AC40_DIMENSIONS.hullLengthM).toBe(11.8)
      expect(AC40_DIMENSIONS.bowspritLengthM).toBeCloseTo(1.163, 2)
      expect(AC40_DIMENSIONS.totalLengthM).toBeCloseTo(13.178, 2)
      expect(AC40_DIMENSIONS.maxHalfBeamM).toBeCloseTo(1.5075, 4)
      expect(AC40_DIMENSIONS.foilHalfSpanM).toBeCloseTo(5.415, 3)
      expect(AC40_DIMENSIONS.minPixelFloor).toBe(22.0)
    })

    it('verifies AC40 hull polygon geometry and symmetry', () => {
      expect(AC40_HULL_POLYGON.length).toBeGreaterThan(10)
      const bow = AC40_HULL_POLYGON[0]
      expect(bow[0]).toBe(0.0) // On centerline
      expect(bow[1]).toBeCloseTo(12.963, 3) // Bowsprit tip

      // Find max half-beam
      const maxU = Math.max(...AC40_HULL_POLYGON.map(([u]) => u))
      const minU = Math.min(...AC40_HULL_POLYGON.map(([u]) => u))
      expect(maxU).toBeCloseTo(1.5075, 3)
      expect(minU).toBeCloseTo(-1.5075, 3)

      // Hull closes at bow
      const last = AC40_HULL_POLYGON[AC40_HULL_POLYGON.length - 1]
      expect(last[0]).toBe(bow[0])
      expect(last[1]).toBe(bow[1])
    })

    it('verifies AC40 foil wing outboard tips reach 5.415m span', () => {
      const minPortU = Math.min(...AC40_FOIL_WING_PORT.map(([u]) => u))
      const maxStbdU = Math.max(...AC40_FOIL_WING_STARBOARD.map(([u]) => u))
      expect(minPortU).toBeCloseTo(-5.415, 3)
      expect(maxStbdU).toBeCloseTo(5.415, 3)
    })

    it('verifies AC40 cockpit trenches are separated by central deck spine', () => {
      const portMaxU = Math.max(...AC40_COCKPIT_PORT.map(([u]) => u))
      const stbdMinU = Math.min(...AC40_COCKPIT_STARBOARD.map(([u]) => u))
      expect(portMaxU).toBeLessThan(0)
      expect(stbdMinU).toBeGreaterThan(0)
      expect(stbdMinU - portMaxU).toBeGreaterThanOrEqual(0.8) // Central spine >= 0.8m
    })
  })

  describe('AC75 Class Rule V3.05 (Rule 9.4) Geometry & Dimensions', () => {
    it('verifies AC75 canonical dimensions adhere to Rule 9.4 constraints', () => {
      // Rule 9.4: forward point 20.600m to 20.700m forward of transom
      expect(AC75_DIMENSIONS.hullLengthM).toBeGreaterThanOrEqual(20.6)
      expect(AC75_DIMENSIONS.hullLengthM).toBeLessThanOrEqual(20.7)
      // Rule 9.4: max half-beam 2.400m to 2.500m
      expect(AC75_DIMENSIONS.maxHalfBeamM).toBeGreaterThanOrEqual(2.4)
      expect(AC75_DIMENSIONS.maxHalfBeamM).toBeLessThanOrEqual(2.5)
      // AC75 deployed foil span ~ 16.0m (+/- 8.0m)
      expect(AC75_DIMENSIONS.foilHalfSpanM).toBe(8.0)
      expect(AC75_DIMENSIONS.minPixelFloor).toBe(34.0)
    })

    it('verifies AC75 hull polygon reaches Rule 9.4 length and beam bounds', () => {
      const bow = AC75_HULL_POLYGON[0]
      expect(bow[0]).toBe(0.0)
      expect(bow[1]).toBe(21.5) // Forward instrumentation wand

      const maxU = Math.max(...AC75_HULL_POLYGON.map(([u]) => u))
      const minU = Math.min(...AC75_HULL_POLYGON.map(([u]) => u))
      expect(maxU).toBeCloseTo(2.45, 2)
      expect(minU).toBeCloseTo(-2.45, 2)
    })

    it('verifies AC75 foil wings reach 8.0m lateral span', () => {
      const minPortU = Math.min(...AC75_FOIL_WING_PORT.map(([u]) => u))
      const maxStbdU = Math.max(...AC75_FOIL_WING_STARBOARD.map(([u]) => u))
      expect(minPortU).toBeCloseTo(-8.0, 1)
      expect(maxStbdU).toBeCloseTo(8.0, 1)
    })
  })

  describe('Bounding Box & Dimensions Lookup', () => {


    it('defaults UNKNOWN to AC40 dimensions', () => {
      const dims = getBoatDimensions('UNKNOWN')
      expect(dims.hullLengthM).toBe(AC40_DIMENSIONS.hullLengthM)
    })
  })

  describe('Dynamic Render Scaling & Pixel Legibility Floor', () => {
    it('uses exact viewport scale in true metric mode', () => {
      expect(computeBoatRenderScale('AC40', 0.05, 'true')).toBe(0.05)
      expect(computeBoatRenderScale('AC75', 0.05, 'true')).toBe(0.05)
      expect(computeBoatRenderScale('AC40', 0.05, 'enhanced')).toBeGreaterThan(0.05)
    })

    it('enforces 22px legibility floor for AC40 at wide regatta zoom levels', () => {
      const wideScale = 0.05 // px/m at 2.5km course zoom
      const renderScale = computeBoatRenderScale('AC40', wideScale)
      const renderedPixelLength = renderScale * AC40_DIMENSIONS.totalLengthM

      expect(renderedPixelLength).toBeGreaterThanOrEqual(21.99)
      expect(renderScale).toBeGreaterThan(wideScale)
    })

    it('enforces 34px legibility floor for AC75 at wide zoom levels', () => {
      const wideScale = 0.05
      const renderScale = computeBoatRenderScale('AC75', wideScale)
      const renderedPixelLength = renderScale * AC75_DIMENSIONS.totalLengthM

      expect(renderedPixelLength).toBeGreaterThanOrEqual(33.99)
      expect(renderScale).toBeGreaterThan(wideScale)
    })

    it('scales 1:1 with metric viewport scale when zoomed in close', () => {
      const closeScale = 12.0 // px/m
      const ac40Scale = computeBoatRenderScale('AC40', closeScale)
      const ac75Scale = computeBoatRenderScale('AC75', closeScale)

      expect(ac40Scale).toBe(closeScale)
      expect(ac75Scale).toBe(closeScale)
    })
  })

  describe('Canvas Rendering Execution', () => {
    function createMockCanvasContext(): CanvasRenderingContext2D {
      return {
        save: vi.fn(),
        restore: vi.fn(),
        beginPath: vi.fn(),
        closePath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        arc: vi.fn(),
        fill: vi.fn(),
        stroke: vi.fn(),
        fillStyle: '',
        strokeStyle: '',
        lineWidth: 1,
      } as unknown as CanvasRenderingContext2D
    }

    it('renders AC40 boat model to 2D canvas without error', () => {
      const ctx = createMockCanvasContext()
      renderFoilingBoatModel(ctx, 'AC40', '#00f0fd', 2.0, false)

      expect(ctx.save).toHaveBeenCalled()
      expect(ctx.restore).toHaveBeenCalled()
      expect(ctx.beginPath).toHaveBeenCalled()
      expect(ctx.fill).toHaveBeenCalled()
      expect(ctx.stroke).toHaveBeenCalled()
    })

    it('renders AC75 boat model with selected state highlight', () => {
      const ctx = createMockCanvasContext()
      renderFoilingBoatModel(ctx, 'AC75', '#ff0000', 2.5, true)

      expect(ctx.save).toHaveBeenCalled()
      expect(ctx.restore).toHaveBeenCalled()
      expect(ctx.stroke).toHaveBeenCalled()
    })

    it('avoids fixed-size fittings when true metric boats are subpixel at course zoom', () => {
      const ctx = createMockCanvasContext()
      renderFoilingBoatModel(ctx, 'AC40', '#06b6d4', 0.09, false, 'true')
      expect(ctx.moveTo).toHaveBeenCalledWith(12.963 * 0.09, 0)
      expect(ctx.arc).not.toHaveBeenCalled()
      expect(ctx.stroke).not.toHaveBeenCalled()
    })

    it('traces closed polygon into canvas with correct coordinate swap', () => {
      const ctx = createMockCanvasContext()
      tracePolygonInCanvas(ctx, [[1.0, 5.0], [2.0, 6.0]], 2.0)

      expect(ctx.beginPath).toHaveBeenCalled()
      expect(ctx.moveTo).toHaveBeenCalledWith(5.0 * 2.0, 1.0 * 2.0)
      expect(ctx.lineTo).toHaveBeenCalledWith(6.0 * 2.0, 2.0 * 2.0)
      expect(ctx.closePath).toHaveBeenCalled()
    })
  })

  describe('Canonical Platform & Keep Clear Borders', () => {
    it('verifies AC75 Platform Border matches Rule 9.4 dimensions', () => {
      expect(AC75_PLATFORM_BORDER.length).toBeGreaterThanOrEqual(8)
      const ys = AC75_PLATFORM_BORDER.map((p) => p.y)
      const xs = AC75_PLATFORM_BORDER.map((p) => p.x)

      expect(Math.min(...ys)).toBe(-0.4) // Rudder aft point
      expect(Math.max(...ys)).toBe(21.5) // Forward instrumentation wand
      expect(Math.min(...xs)).toBe(-8.0) // Port foil tip
      expect(Math.max(...xs)).toBe(8.0)  // Starboard foil tip

      // Transom corners adhere to Rule 9.4 max half-beam (2.45m)
      const transomCorners = AC75_PLATFORM_BORDER.filter((p) => p.y === 0)
      expect(transomCorners).toHaveLength(2)
      expect(transomCorners.map((p) => Math.abs(p.x))).toEqual([2.45, 2.45])
    })

    it('verifies AC75 Keep Clear Border expands by 2m laterally', () => {
      expect(AC75_KEEP_CLEAR_BORDER.length).toBeGreaterThanOrEqual(8)
      const ys = AC75_KEEP_CLEAR_BORDER.map((p) => p.y)
      const xs = AC75_KEEP_CLEAR_BORDER.map((p) => p.x)

      expect(Math.min(...ys)).toBe(-0.4)
      expect(Math.max(...ys)).toBe(21.5)
      expect(Math.min(...xs)).toBe(-10.0) // 8.0 + 2.0m lateral expansion
      expect(Math.max(...xs)).toBe(10.0)  // 8.0 + 2.0m lateral expansion

      // Transom corners expanded by 2m (2.45 + 2.0 = 4.45m)
      const transomCorners = AC75_KEEP_CLEAR_BORDER.filter((p) => p.y === 0)
      expect(transomCorners).toHaveLength(2)
      expect(transomCorners.map((p) => Math.abs(p.x))).toEqual([4.45, 4.45])
    })

    it('verifies getSafetyBorders returns class-appropriate canonical borders', () => {
      const ac40Borders = getSafetyBorders('AC40')
      expect(ac40Borders.platform_border).toBe(AC40_PLATFORM_BORDER)
      expect(ac40Borders.keep_clear_border).toBe(AC40_KEEP_CLEAR_BORDER)

      const ac75Borders = getSafetyBorders('AC75')
      expect(ac75Borders.platform_border).toBe(AC75_PLATFORM_BORDER)
      expect(ac75Borders.keep_clear_border).toBe(AC75_KEEP_CLEAR_BORDER)

      // Defaults to AC40 when undefined or UNKNOWN
      expect(getSafetyBorders(undefined).platform_border).toBe(AC40_PLATFORM_BORDER)
      expect(getSafetyBorders('UNKNOWN').platform_border).toBe(AC40_PLATFORM_BORDER)

      // Preserves valid custom borders
      const custom = {
        platform_border: [{ x: 0, y: 0 }, { x: 1, y: 1 }, { x: 0, y: 2 }],
        keep_clear_border: [{ x: -1, y: -1 }, { x: 2, y: 2 }, { x: -1, y: 3 }],
      }
      expect(getSafetyBorders('AC75', custom)).toBe(custom)
    })
  })

  describe('Zero Scale Divergence Invariance', () => {
    it('confirms true metric scale factor equals viewport scale exactly at all zooms', () => {
      const testZooms = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0, 20.0, 100.0]
      for (const zoom of testZooms) {
        expect(computeBoatRenderScale('AC40', zoom, 'true')).toBe(zoom)
        expect(computeBoatRenderScale('AC75', zoom, 'true')).toBe(zoom)
      }
    })

    it('confirms enhanced scale factor applies minimum pixel floor at wide zoom', () => {
      const wideZoom = 0.02
      const ac40Enhanced = computeBoatRenderScale('AC40', wideZoom, 'enhanced')
      const ac75Enhanced = computeBoatRenderScale('AC75', wideZoom, 'enhanced')

      expect(ac40Enhanced).toBeCloseTo(22.0 / AC40_DIMENSIONS.totalLengthM, 4)
      expect(ac75Enhanced).toBeCloseTo(34.0 / AC75_DIMENSIONS.totalLengthM, 4)
      expect(ac40Enhanced).toBeGreaterThan(wideZoom)
      expect(ac75Enhanced).toBeGreaterThan(wideZoom)
    })
  })
})
