import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { TelemetryWorkspace } from './TelemetryWorkspace'

describe('TelemetryWorkspace Component & Scrubber Precision Tests (R1 / M8)', () => {
  const replayPath = path.resolve(process.cwd(), 'public/data/replays/naples_pr1.json')
  const replay: ReplayManifest = JSON.parse(fs.readFileSync(replayPath, 'utf-8'))

  // Benchmark timestamp -02:04 (124 seconds before gun)
  const BENCHMARK_TIMESTAMP = 1790078876000
  const SELECTED_BOAT_ID = '42e39310-fef5-4c5d-b099-a599aad5ddbb' // FRA

  function parsePolylinePoints(pointsStr: string): Array<[number, number]> {
    return pointsStr
      .trim()
      .split(/\s+/)
      .map((pt) => {
        const [x, y] = pt.split(',').map(Number)
        return [x, y] as [number, number]
      })
  }

  function getPolylineYAtX(points: Array<[number, number]>, targetX: number): number | null {
    if (points.length < 2) return null
    for (let i = 0; i < points.length - 1; i++) {
      const [x0, y0] = points[i]
      const [x1, y1] = points[i + 1]
      const minX = Math.min(x0, x1)
      const maxX = Math.max(x0, x1)
      if (targetX >= minX - 1e-4 && targetX <= maxX + 1e-4) {
        if (Math.abs(x1 - x0) < 1e-6) return y0
        const alpha = (targetX - x0) / (x1 - x0)
        return y0 + alpha * (y1 - y0)
      }
    }
    return null
  }

  it('1. Verifies benchmark data at t = 1790078876000 (-02:04) matches naples_pr1 telemetry index 560', () => {
    const rawTimestamps = replay.telemetry?.timestamps ?? []
    const idx = rawTimestamps.indexOf(BENCHMARK_TIMESTAMP)
    expect(idx).toBe(560)

    const boatTel = replay.telemetry?.boats?.[SELECTED_BOAT_ID]
    expect(boatTel).toBeDefined()
    expect(boatTel?.sog[560]).toBe(41.7)
    expect(boatTel?.vmg[560]).toBe(-13.8)
    expect(boatTel?.twa[560]).toBe(121.5)
  })

  it('2. Verifies SOG, VMG, and TWA scrubber dots intersect rendered polylines exactly at -02:04', () => {
    const idx = 560
    const boatTel = replay.telemetry!.boats[SELECTED_BOAT_ID]

    // Construct frame matching ReplayEngine output at t = 1790078876000
    const frame: ReplayFrame = {
      timestamp: BENCHMARK_TIMESTAMP,
      boats: {
        [SELECTED_BOAT_ID]: {
          id: SELECTED_BOAT_ID,
          x: boatTel.x[idx],
          y: boatTel.y[idx],
          heading: boatTel.heading[idx],
          cog: boatTel.cog[idx],
          sog: boatTel.sog[idx],
          vmg: boatTel.vmg[idx],
          twa: boatTel.twa[idx],
          twd: boatTel.twd[idx],
          tws: boatTel.tws[idx],
          progress_m: boatTel.progress_m[idx],
          leg: boatTel.leg[idx],
        },
      },
    }

    const html = renderToStaticMarkup(
      React.createElement(TelemetryWorkspace, {
        replay,
        frame,
        selectedId: SELECTED_BOAT_ID,
        onSelectBoat: () => {},
        onSeek: () => {},
      }),
    )

    // Expected Needle X calculation
    const windowDurationMs = 300000 // 5 min default
    const windowStartMs = Math.max(
      replay.chronology.window_start,
      BENCHMARK_TIMESTAMP - windowDurationMs * 0.65,
    )
    const needleFrac = (BENCHMARK_TIMESTAMP - windowStartMs) / windowDurationMs
    const expectedNeedleX = needleFrac * 740

    // Extract circles for selected boat dots via semantic class names
    const sogDotMatch = html.match(/<circle[^>]*class="[^"]*scrubber-dot-sog[^"]*"[^>]*>/)
    const vmgDotMatch = html.match(/<circle[^>]*class="[^"]*scrubber-dot-vmg[^"]*"[^>]*>/)
    const twaDotMatch = html.match(/<circle[^>]*class="[^"]*scrubber-dot-twa[^"]*"[^>]*>/)

    expect(sogDotMatch).not.toBeNull()
    expect(vmgDotMatch).not.toBeNull()
    expect(twaDotMatch).not.toBeNull()

    const parseCircle = (tag: string) => {
      const cxMatch = tag.match(/cx="([^"]+)"/)
      const cyMatch = tag.match(/cy="([^"]+)"/)
      return {
        cx: parseFloat(cxMatch![1]),
        cy: parseFloat(cyMatch![1]),
      }
    }

    const sogDot = parseCircle(sogDotMatch![0])
    const vmgDot = parseCircle(vmgDotMatch![0])
    const twaDot = parseCircle(twaDotMatch![0])

    // Verify cx matches needleX exactly
    expect(sogDot.cx).toBeCloseTo(expectedNeedleX, 3)
    expect(vmgDot.cx).toBeCloseTo(expectedNeedleX, 3)
    expect(twaDot.cx).toBeCloseTo(expectedNeedleX, 3)

    // Verify exact expected Y coordinates based on affine transformation
    const expectedSogY = 60 - (41.7 / 60) * 52 - 4 // 19.86
    const expectedVmgY = 60 - ((-13.8 + 40) / 60) * 52 - 4 // 33.2933...
    const expectedTwaY = 60 - ((121.5 + 180) / 360) * 52 - 4 // 12.45

    expect(sogDot.cy).toBeCloseTo(expectedSogY, 3)
    expect(vmgDot.cy).toBeCloseTo(expectedVmgY, 3)
    expect(twaDot.cy).toBeCloseTo(expectedTwaY, 3)

    // Extract polylines for the selected boat (stroke-width="2.4" for selected boat)
    const polylineMatches = [...html.matchAll(/<polyline[^>]*stroke-width="2.4"[^>]*points="([^"]+)"/g)]
    expect(polylineMatches.length).toBe(3) // SOG, VMG, TWA

    const sogPolylinePoints = parsePolylinePoints(polylineMatches[0][1])
    const vmgPolylinePoints = parsePolylinePoints(polylineMatches[1][1])
    const twaPolylinePoints = parsePolylinePoints(polylineMatches[2][1])

    // Verify exact intersection with rendered polyline
    const polySogY = getPolylineYAtX(sogPolylinePoints, sogDot.cx)
    const polyVmgY = getPolylineYAtX(vmgPolylinePoints, vmgDot.cx)
    const polyTwaY = getPolylineYAtX(twaPolylinePoints, twaDot.cx)

    expect(polySogY).not.toBeNull()
    expect(polyVmgY).not.toBeNull()
    expect(polyTwaY).not.toBeNull()

    // Vertical delta between dot and polyline curve must be < 0.01 px
    expect(Math.abs(sogDot.cy - polySogY!)).toBeLessThan(0.01)
    expect(Math.abs(vmgDot.cy - polyVmgY!)).toBeLessThan(0.01)
    expect(Math.abs(twaDot.cy - polyTwaY!)).toBeLessThan(0.01)
  })

  it('3. Verifies needle cursor position has no 4px horizontal offset (uses 68px, not 72px)', () => {
    const boatTel = replay.telemetry!.boats[SELECTED_BOAT_ID]
    const idx = 560
    const frame: ReplayFrame = {
      timestamp: BENCHMARK_TIMESTAMP,
      boats: {
        [SELECTED_BOAT_ID]: {
          id: SELECTED_BOAT_ID,
          x: boatTel.x[idx],
          y: boatTel.y[idx],
          heading: boatTel.heading[idx],
          cog: boatTel.cog[idx],
          sog: boatTel.sog[idx],
          vmg: boatTel.vmg[idx],
          twa: boatTel.twa[idx],
          twd: boatTel.twd[idx],
          tws: boatTel.tws[idx],
          progress_m: boatTel.progress_m[idx],
          leg: boatTel.leg[idx],
        },
      },
    }

    const html = renderToStaticMarkup(
      React.createElement(TelemetryWorkspace, {
        replay,
        frame,
        selectedId: SELECTED_BOAT_ID,
        onSelectBoat: () => {},
        onSeek: () => {},
      }),
    )

    // Cursor must use calc(68px + (100% - 68px) * ...) to match .chart-y-axis-col (68px)
    expect(html).toContain('calc(68px + (100% - 68px) *')
    expect(html).not.toContain('calc(72px')

    // Internal SVG needle line must be present in each chart aligned with needleX
    const needleLines = [...html.matchAll(/<line[^>]*class="chart-needle-line"[^>]*>/g)]
    expect(needleLines.length).toBe(3)

    for (const match of needleLines) {
      const lineTag = match[0]
      const x1Match = lineTag.match(/x1="([^"]+)"/)
      const x2Match = lineTag.match(/x2="([^"]+)"/)
      expect(x1Match).not.toBeNull()
      expect(x2Match).not.toBeNull()
      expect(parseFloat(x1Match![1])).toBeCloseTo(138.133, 2)
      expect(parseFloat(x2Match![1])).toBeCloseTo(138.133, 2)
    }
  })

  it('4. Verifies continuous sub-sample linear interpolation between frames', () => {
    // 50ms after sample 560 (halfway to 561)
    const tSub = BENCHMARK_TIMESTAMP + 50
    const boatTel = replay.telemetry!.boats[SELECTED_BOAT_ID]
    const s560 = boatTel.sog[560]
    const s561 = boatTel.sog[561]
    const interpSog = s560 + 0.5 * (s561 - s560)

    const v560 = boatTel.vmg[560]
    const v561 = boatTel.vmg[561]
    const interpVmg = v560 + 0.5 * (v561 - v560)

    const tw560 = boatTel.twa[560]
    const tw561 = boatTel.twa[561]
    const interpTwa = tw560 + 0.5 * (tw561 - tw560)

    const frame: ReplayFrame = {
      timestamp: tSub,
      boats: {
        [SELECTED_BOAT_ID]: {
          id: SELECTED_BOAT_ID,
          x: boatTel.x[560],
          y: boatTel.y[560],
          heading: boatTel.heading[560],
          cog: boatTel.cog[560],
          sog: interpSog,
          vmg: interpVmg,
          twa: interpTwa,
          twd: boatTel.twd[560],
          tws: boatTel.tws[560],
          progress_m: boatTel.progress_m[560],
          leg: boatTel.leg[560],
        },
      },
    }

    const html = renderToStaticMarkup(
      React.createElement(TelemetryWorkspace, {
        replay,
        frame,
        selectedId: SELECTED_BOAT_ID,
        onSelectBoat: () => {},
        onSeek: () => {},
      }),
    )

    const sogDotMatch = html.match(/<circle[^>]*class="[^"]*scrubber-dot-sog[^"]*"[^>]*>/)
    expect(sogDotMatch).not.toBeNull()
    const sogDot = {
      cx: parseFloat(sogDotMatch![0].match(/cx="([^"]+)"/)![1]),
      cy: parseFloat(sogDotMatch![0].match(/cy="([^"]+)"/)![1]),
    }

    const polylineMatches = [...html.matchAll(/<polyline[^>]*stroke-width="2.4"[^>]*points="([^"]+)"/g)]
    const sogPolylinePoints = parsePolylinePoints(polylineMatches[0][1])
    const polySogY = getPolylineYAtX(sogPolylinePoints, sogDot.cx)

    expect(polySogY).not.toBeNull()
    expect(Math.abs(sogDot.cy - polySogY!)).toBeLessThan(0.01)
  })

  it('5. Verifies selected boat uses stride=1 while unselected boats use downsampled strides', () => {
    const boatTel = replay.telemetry!.boats[SELECTED_BOAT_ID]
    const frame: ReplayFrame = {
      timestamp: BENCHMARK_TIMESTAMP,
      boats: {
        [SELECTED_BOAT_ID]: {
          id: SELECTED_BOAT_ID,
          x: boatTel.x[560],
          y: boatTel.y[560],
          heading: boatTel.heading[560],
          cog: boatTel.cog[560],
          sog: boatTel.sog[560],
          vmg: boatTel.vmg[560],
          twa: boatTel.twa[560],
          twd: boatTel.twd[560],
          tws: boatTel.tws[560],
          progress_m: boatTel.progress_m[560],
          leg: boatTel.leg[560],
        },
      },
    }

    const html = renderToStaticMarkup(
      React.createElement(TelemetryWorkspace, {
        replay,
        frame,
        selectedId: SELECTED_BOAT_ID,
        onSelectBoat: () => {},
        onSeek: () => {},
      }),
    )

    const selectedPolylines = [...html.matchAll(/<polyline[^>]*stroke-width="2.4"[^>]*points="([^"]+)"/g)]
    const unselectedPolylines = [...html.matchAll(/<polyline[^>]*stroke-width="1.4"[^>]*points="([^"]+)"/g)]

    expect(selectedPolylines.length).toBeGreaterThan(0)
    expect(unselectedPolylines.length).toBeGreaterThan(0)

    const selectedPointsCount = parsePolylinePoints(selectedPolylines[0][1]).length
    const unselectedPointsCount = parsePolylinePoints(unselectedPolylines[0][1]).length

    // Selected boat has every 100ms vertex (around 3000 points in 5 min window)
    expect(selectedPointsCount).toBeGreaterThan(2000)
    // Unselected boats are decimated to approx. 120 target steps
    expect(unselectedPointsCount).toBeLessThan(200)
  })

  it('6. Verifies dynamic X-axis ticks adapt to time window and contain zero literal tilde', () => {
    const boatTel = replay.telemetry!.boats[SELECTED_BOAT_ID]
    const frame: ReplayFrame = {
      timestamp: BENCHMARK_TIMESTAMP,
      boats: {
        [SELECTED_BOAT_ID]: {
          id: SELECTED_BOAT_ID,
          x: boatTel.x[560],
          y: boatTel.y[560],
          heading: boatTel.heading[560],
          cog: boatTel.cog[560],
          sog: boatTel.sog[560],
          vmg: boatTel.vmg[560],
          twa: boatTel.twa[560],
          twd: boatTel.twd[560],
          tws: boatTel.tws[560],
          progress_m: boatTel.progress_m[560],
          leg: boatTel.leg[560],
        },
      },
    }

    const html = renderToStaticMarkup(
      React.createElement(TelemetryWorkspace, {
        replay,
        frame,
        selectedId: SELECTED_BOAT_ID,
        onSelectBoat: () => {},
        onSeek: () => {},
      }),
    )

    const tickMatches = [...html.matchAll(/<span[^>]*class="x-tick-label"[^>]*>([^<]+)<\/span>/g)]
    expect(tickMatches.length).toBeGreaterThanOrEqual(5)

    // Ticks must be formatted with relative clock e.g. -02:00, -01:00, +00:00, etc.
    for (const match of tickMatches) {
      const text = match[1]
      expect(text).toMatch(/^[+−-]\d{2}:\d{2}$/)
      expect(text).not.toContain('\u007E')
    }

    // Zero tildes across entire rendered markup
    expect(html).not.toContain('\u007E')
  })

  it('7. Verifies no scrubber dots rendered when selectedId is null', () => {
    const frame: ReplayFrame = {
      timestamp: BENCHMARK_TIMESTAMP,
      boats: {},
    }

    const html = renderToStaticMarkup(
      React.createElement(TelemetryWorkspace, {
        replay,
        frame,
        selectedId: null,
        onSelectBoat: () => {},
        onSeek: () => {},
      }),
    )

    const dots = [...html.matchAll(/<circle[^>]*class="[^"]*scrubber-dot[^"]*"[^>]*>/g)]
    expect(dots.length).toBe(0)

    // Needle lines and needle cursor must still render
    const needleLines = [...html.matchAll(/<line[^>]*class="chart-needle-line"[^>]*>/g)]
    expect(needleLines.length).toBe(3)
    expect(html).toContain('class="synchronized-needle-cursor"')
  })

  it('8. Verifies exact polyline intersection at gun time (t = 1790079000000, 00:00)', () => {
    const GUN_TIMESTAMP = replay.chronology.gun_time
    const rawTimestamps = replay.telemetry?.timestamps ?? []
    const idx = rawTimestamps.indexOf(GUN_TIMESTAMP)
    expect(idx).toBeGreaterThan(0)

    const boatTel = replay.telemetry!.boats[SELECTED_BOAT_ID]
    const frame: ReplayFrame = {
      timestamp: GUN_TIMESTAMP,
      boats: {
        [SELECTED_BOAT_ID]: {
          id: SELECTED_BOAT_ID,
          x: boatTel.x[idx],
          y: boatTel.y[idx],
          heading: boatTel.heading[idx],
          cog: boatTel.cog[idx],
          sog: boatTel.sog[idx],
          vmg: boatTel.vmg[idx],
          twa: boatTel.twa[idx],
          twd: boatTel.twd[idx],
          tws: boatTel.tws[idx],
          progress_m: boatTel.progress_m[idx],
          leg: boatTel.leg[idx],
        },
      },
    }

    const html = renderToStaticMarkup(
      React.createElement(TelemetryWorkspace, {
        replay,
        frame,
        selectedId: SELECTED_BOAT_ID,
        onSelectBoat: () => {},
        onSeek: () => {},
      }),
    )

    const sogDotMatch = html.match(/<circle[^>]*class="[^"]*scrubber-dot-sog[^"]*"[^>]*>/)
    expect(sogDotMatch).not.toBeNull()
    const sogDot = {
      cx: parseFloat(sogDotMatch![0].match(/cx="([^"]+)"/)![1]),
      cy: parseFloat(sogDotMatch![0].match(/cy="([^"]+)"/)![1]),
    }

    const polylineMatches = [...html.matchAll(/<polyline[^>]*stroke-width="2.4"[^>]*points="([^"]+)"/g)]
    const sogPolylinePoints = parsePolylinePoints(polylineMatches[0][1])
    const polySogY = getPolylineYAtX(sogPolylinePoints, sogDot.cx)

    expect(polySogY).not.toBeNull()
    expect(Math.abs(sogDot.cy - polySogY!)).toBeLessThan(0.01)
  })

  it('9. Source file integrity: zero occurrences of literal tilde in TelemetryWorkspace.tsx', () => {
    const srcPath = path.resolve(process.cwd(), 'src/components/dashboard/TelemetryWorkspace.tsx')
    const srcContent = fs.readFileSync(srcPath, 'utf-8')
    expect(srcContent.includes('\u007E')).toBe(false)
  })
})
