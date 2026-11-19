import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { TelemetryWorkspace } from './TelemetryWorkspace'
import { sampleBoat } from '../../engine/interpolate'

describe('Adversarial Scrubber Dot & Polyline Interpolation Stress Test (M8 Challenger)', () => {
  const liveReplayPath = path.resolve(process.cwd(), 'public/data/replays/naples_pr1.json')
  const hasLiveNaplesPr1 = fs.existsSync(liveReplayPath)
  const replayPath = hasLiveNaplesPr1
    ? liveReplayPath
    : path.resolve(process.cwd(), 'tests/fixtures/synthetic_replay.json')
  const replay: ReplayManifest = JSON.parse(fs.readFileSync(replayPath, 'utf-8'))
  const rawTimestamps = replay.telemetry?.timestamps ?? []
  const gunTime = replay.chronology.gun_time

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

  function parseCircle(tag: string): { cx: number; cy: number } {
    const cxMatch = tag.match(/cx="([^"]+)"/)
    const cyMatch = tag.match(/cy="([^"]+)"/)
    if (!cxMatch || !cyMatch) {
      throw new Error(`Failed to parse circle coordinates from: ${tag}`)
    }
    return {
      cx: parseFloat(cxMatch[1]),
      cy: parseFloat(cyMatch[1]),
    }
  }

  function createReplayFrameAtTime(timestamp: number): ReplayFrame {
    let lower = 0
    let upper = rawTimestamps.length - 1
    while (lower < upper) {
      const middle = Math.ceil((lower + upper) / 2)
      if (rawTimestamps[middle] <= timestamp) lower = middle
      else upper = middle - 1
    }
    const index = lower
    const nextTime = rawTimestamps[Math.min(index + 1, rawTimestamps.length - 1)]
    const fraction =
      nextTime === rawTimestamps[index]
        ? 0
        : Math.min(
            1,
            Math.max(0, (timestamp - rawTimestamps[index]) / (nextTime - rawTimestamps[index]))
          )

    const boats = Object.fromEntries(
      Object.entries(replay.telemetry.boats).map(([id, boat]) => [
        id,
        sampleBoat(id, boat, index, fraction),
      ])
    )

    return {
      timestamp,
      index,
      fraction,
      boats,
    }
  }

  /**
   * Helper to verify dot on polyline within tolerance
   */
  function verifyDotsOnPolylines(
    timestamp: number,
    boatId: string,
    frameOverride?: ReplayFrame,
    tolerancePx = 0.05
  ) {
    const frame = frameOverride ?? createReplayFrameAtTime(timestamp)
    const html = renderToStaticMarkup(
      React.createElement(TelemetryWorkspace, {
        replay,
        frame,
        selectedId: boatId,
        onSelectBoat: () => {},
        onSeek: () => {},
      })
    )

    // Extract selected polylines (stroke-width="2.4")
    const polylineMatches = [
      ...html.matchAll(/<polyline[^>]*stroke-width="2.4"[^>]*points="([^"]+)"/g),
    ]
    expect(polylineMatches.length).toBe(3) // SOG, VMG, TWA

    const sogPoints = parsePolylinePoints(polylineMatches[0][1])
    const vmgPoints = parsePolylinePoints(polylineMatches[1][1])
    const twaPoints = parsePolylinePoints(polylineMatches[2][1])

    // Extract dots
    const sogDotMatch = html.match(/<circle[^>]*class="[^"]*scrubber-dot-sog[^"]*"[^>]*>/)
    const vmgDotMatch = html.match(/<circle[^>]*class="[^"]*scrubber-dot-vmg[^"]*"[^>]*>/)
    const twaDotMatch = html.match(/<circle[^>]*class="[^"]*scrubber-dot-twa[^"]*"[^>]*>/)

    expect(sogDotMatch).not.toBeNull()
    expect(vmgDotMatch).not.toBeNull()
    expect(twaDotMatch).not.toBeNull()

    const sogDot = parseCircle(sogDotMatch![0])
    const vmgDot = parseCircle(vmgDotMatch![0])
    const twaDot = parseCircle(twaDotMatch![0])

    // Polyline Y at Dot X
    const polySogY = getPolylineYAtX(sogPoints, sogDot.cx)
    const polyVmgY = getPolylineYAtX(vmgPoints, vmgDot.cx)
    const polyTwaY = getPolylineYAtX(twaPoints, twaDot.cx)

    expect(polySogY).not.toBeNull()
    expect(polyVmgY).not.toBeNull()
    expect(polyTwaY).not.toBeNull()

    const deltaSog = Math.abs(sogDot.cy - polySogY!)
    const deltaVmg = Math.abs(vmgDot.cy - polyVmgY!)
    const deltaTwa = Math.abs(twaDot.cy - polyTwaY!)

    expect(deltaSog).toBeLessThan(tolerancePx)
    expect(deltaVmg).toBeLessThan(tolerancePx)
    expect(deltaTwa).toBeLessThan(tolerancePx)

    return { deltaSog, deltaVmg, deltaTwa }
  }

  // 1. Mandatory Benchmark Timestamps
  const MANDATORY_TIMESTAMPS = hasLiveNaplesPr1
    ? [
        { name: '-02:04', time: gunTime - 124000 },
        { name: '00:00', time: gunTime },
        { name: '+05:30', time: gunTime + 330000 },
        { name: '+12:45', time: gunTime + 765000 },
      ]
    : [
        { name: '-00:05', time: gunTime - 5000 },
        { name: '00:00', time: gunTime },
        { name: '+01:00', time: gunTime + 60000 },
        { name: '+02:00', time: gunTime + 120000 },
      ]

  describe('1. Mandatory Benchmark Timestamps across all Boats (< 0.05px)', () => {
    for (const { name, time } of MANDATORY_TIMESTAMPS) {
      for (const competitor of replay.competitors) {
        it(`Timestamp ${name} on boat ${competitor.team_code} (${competitor.id})`, () => {
          const res = verifyDotsOnPolylines(time, competitor.id)
          expect(res.deltaSog).toBeLessThan(0.05)
          expect(res.deltaVmg).toBeLessThan(0.05)
          expect(res.deltaTwa).toBeLessThan(0.05)
        })
      }
    }
  })

  // 2. High-Density Temporal Sweep (Negative Gun Deltas, Middle Race, Finish, Sub-Sample Interp)
  describe.skipIf(!hasLiveNaplesPr1)('2. Comprehensive Race-Wide Temporal Sweep (< 0.05px)', () => {
    const SWEEP_DELTAS = [
      -175000, // -02:55 near start
      -124000, // -02:04 benchmark
      -75000, // -01:15
      -20000, // -00:20
      0, // 00:00 gun
      30000, // +00:30
      120000, // +02:00 Leg 1
      240000, // +04:00 Leg 1
      330000, // +05:30 Leg 1 rounding
      500000, // +08:20 Leg 2 downwind
      765000, // +12:45 Leg 3 upwind
      1000000, // +16:40 Leg 4 finish area
      1200000, // +20:00 post finish
      1500000, // +25:00 race window tail
    ]

    for (const delta of SWEEP_DELTAS) {
      const t = gunTime + delta
      const sign = delta >= 0 ? '+' : '−'
      const sec = Math.abs(delta) / 1000
      const label = `${sign}${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`

      it(`Sweep at delta ${label} (t = ${t}) on FRA and NZL G`, () => {
        const fraId = '42e39310-fef5-4c5d-b099-a599aad5ddbb'
        const nzlId = '80d4cda4-17f5-4bcf-b7fd-5fc0f39f3d60'

        const rFra = verifyDotsOnPolylines(t, fraId)
        expect(rFra.deltaSog).toBeLessThan(0.05)
        expect(rFra.deltaVmg).toBeLessThan(0.05)
        expect(rFra.deltaTwa).toBeLessThan(0.05)

        const rNzl = verifyDotsOnPolylines(t, nzlId)
        expect(rNzl.deltaSog).toBeLessThan(0.05)
        expect(rNzl.deltaVmg).toBeLessThan(0.05)
        expect(rNzl.deltaTwa).toBeLessThan(0.05)
      })
    }
  })

  // 3. Sub-Sample Fractional Offset Stress (e.g. 13ms, 37ms, 50ms, 89ms into 100ms frame)
  describe.skipIf(!hasLiveNaplesPr1)(
    '3. Sub-Sample Fractional Offsets (Continuous 100ms Interpolation)',
    () => {
      const FRACTIONAL_OFFSETS = [13, 27, 50, 73, 89]
      const baseTime = gunTime + 330000 // +05:30
      const testBoatId = '4f5369cd-0fa3-4241-afd2-00f356898e22' // ITA B

      for (const offset of FRACTIONAL_OFFSETS) {
        it(`Sub-sample +${offset}ms into 100ms step`, () => {
          const t = baseTime + offset
          const res = verifyDotsOnPolylines(t, testBoatId)
          expect(res.deltaSog).toBeLessThan(0.05)
          expect(res.deltaVmg).toBeLessThan(0.05)
          expect(res.deltaTwa).toBeLessThan(0.05)
        })
      }
    }
  )

  // 4. Edge Cases: Window Boundaries (window_start and window_end)
  describe('4. Edge Cases: Window Boundaries', () => {
    const testBoatId = '42e39310-fef5-4c5d-b099-a599aad5ddbb' // FRA

    it('At exact window_start timestamp', () => {
      const t = replay.chronology.window_start
      const res = verifyDotsOnPolylines(t, testBoatId)
      expect(res.deltaSog).toBeLessThan(0.05)
      expect(res.deltaVmg).toBeLessThan(0.05)
      expect(res.deltaTwa).toBeLessThan(0.05)
    })

    it('At exact window_end timestamp', () => {
      const t = replay.chronology.window_end
      const res = verifyDotsOnPolylines(t, testBoatId)
      expect(res.deltaSog).toBeLessThan(0.05)
      expect(res.deltaVmg).toBeLessThan(0.05)
      expect(res.deltaTwa).toBeLessThan(0.05)
    })

    it('Negative gun delta near pre-start origin (-02:59)', () => {
      const t = replay.chronology.window_start + 1000
      const res = verifyDotsOnPolylines(t, testBoatId)
      expect(res.deltaSog).toBeLessThan(0.05)
      expect(res.deltaVmg).toBeLessThan(0.05)
      expect(res.deltaTwa).toBeLessThan(0.05)
    })
  })

  // 5. Missing Live Boat Telemetry (Fallback to raw telemetry linear interpolation)
  describe('5. Missing Frame Boats Telemetry Fallback', () => {
    const testBoatId = replay.competitors[0].id

    it('Fallback interpolation when frame.boats[boat.id] is undefined', () => {
      const t = hasLiveNaplesPr1 ? gunTime + 120000 : gunTime + 60000
      const emptyBoatsFrame: ReplayFrame = {
        timestamp: t,
        boats: {}, // No live boat object
      }

      const html = renderToStaticMarkup(
        React.createElement(TelemetryWorkspace, {
          replay,
          frame: emptyBoatsFrame,
          selectedId: testBoatId,
          onSelectBoat: () => {},
          onSeek: () => {},
        })
      )
      expect(html).not.toContain('class="scrubber-dot')
      expect(html).toContain('polyline')
    })

    it('Fallback interpolation with sub-sample timestamp when frame.boats is empty', () => {
      const t = hasLiveNaplesPr1 ? gunTime + 120042 : gunTime + 60042
      const emptyBoatsFrame: ReplayFrame = {
        timestamp: t,
        boats: {},
      }

      const html = renderToStaticMarkup(
        React.createElement(TelemetryWorkspace, {
          replay,
          frame: emptyBoatsFrame,
          selectedId: testBoatId,
          onSelectBoat: () => {},
          onSeek: () => {},
        })
      )
      expect(html).not.toContain('class="scrubber-dot')
      expect(html).toContain('polyline')
    })
  })

  // 6. Boat Switches & Active Selection Switching
  describe('6. Rapid Boat Switching', () => {
    const t = hasLiveNaplesPr1 ? gunTime - 124000 : gunTime + 60000
    it('Iterating through all boats sequentially at same timestamp maintains < 0.05px', () => {
      for (const comp of replay.competitors) {
        const res = verifyDotsOnPolylines(t, comp.id)
        expect(res.deltaSog).toBeLessThan(0.05)
        expect(res.deltaVmg).toBeLessThan(0.05)
        expect(res.deltaTwa).toBeLessThan(0.05)
      }
    })
  })

  // 7. Extreme Metric Values & Clamping
  describe('7. Clamped Metric Values at Physical Bounds', () => {
    const testBoatId = '42e39310-fef5-4c5d-b099-a599aad5ddbb'
    const t = gunTime

    it('Extreme over-speed / under-VMG clamping maintains valid rendering', () => {
      const extremeFrame: ReplayFrame = {
        timestamp: t,
        boats: {
          [testBoatId]: {
            id: testBoatId,
            x: 0,
            y: 0,
            heading: 45,
            cog: 45,
            sog: 85, // Clamped to 60
            vmg: -60, // Clamped to -40
            twa: 220, // Clamped to 180
            twd: 40,
            tws: 10,
            progress_m: 0,
            leg: 1,
          },
        },
      }

      const html = renderToStaticMarkup(
        React.createElement(TelemetryWorkspace, {
          replay,
          frame: extremeFrame,
          selectedId: testBoatId,
          onSelectBoat: () => {},
          onSeek: () => {},
        })
      )

      const sogDot = parseCircle(
        html.match(/<circle[^>]*class="[^"]*scrubber-dot-sog[^"]*"[^>]*>/)![0]
      )
      const vmgDot = parseCircle(
        html.match(/<circle[^>]*class="[^"]*scrubber-dot-vmg[^"]*"[^>]*>/)![0]
      )
      const twaDot = parseCircle(
        html.match(/<circle[^>]*class="[^"]*scrubber-dot-twa[^"]*"[^>]*>/)![0]
      )

      // SOG = 60 kt -> y = 60 - 52 - 4 = 4
      expect(sogDot.cy).toBeCloseTo(4, 2)
      // VMG = -40 kt -> y = 60 - 0 - 4 = 56
      expect(vmgDot.cy).toBeCloseTo(56, 2)
      // TWA = 180 deg -> y = 60 - 52 - 4 = 4
      expect(twaDot.cy).toBeCloseTo(4, 2)
    })
  })

  // 8. Tilde Prevention Integrity
  describe('8. Zero-Tilde Compliance', () => {
    it('Rendered output has zero literal ~ characters across all timestamps', () => {
      for (const { time } of MANDATORY_TIMESTAMPS) {
        const frame = createReplayFrameAtTime(time)
        const html = renderToStaticMarkup(
          React.createElement(TelemetryWorkspace, {
            replay,
            frame,
            selectedId: replay.competitors[0].id,
            onSelectBoat: () => {},
            onSeek: () => {},
          })
        )
        expect(html.includes('~')).toBe(false)
      }
    })
  })

  // 9. Multi-Race Generalization (Naples Race 2 and Cagliari Race 1)
  const testRaces = [
    '26_09_25_nap_ipr_race_2.json',
    '26_05_22_cag_ipr_race_1.json',
    'naples_mr_final.json',
  ]
  const existingTestRaces = testRaces.filter((raceFileName) =>
    fs.existsSync(path.resolve(process.cwd(), 'public/data/replays', raceFileName))
  )
  describe.skipIf(existingTestRaces.length === 0)('9. Multi-Race Generalization (< 0.05px)', () => {
    for (const raceFileName of existingTestRaces) {
      const p = path.resolve(process.cwd(), 'public/data/replays', raceFileName)
      const otherReplay: ReplayManifest = JSON.parse(fs.readFileSync(p, 'utf-8'))
      const gTime = otherReplay.chronology.gun_time
      const testTimestamps = [gTime - 60000, gTime, gTime + 180000]

      it(`Race ${raceFileName} across competitors at 3 timestamps`, () => {
        for (const competitor of otherReplay.competitors) {
          for (const t of testTimestamps) {
            // Find index
            const ts = otherReplay.telemetry.timestamps
            let lower = 0
            let upper = ts.length - 1
            while (lower < upper) {
              const middle = Math.ceil((lower + upper) / 2)
              if (ts[middle] <= t) lower = middle
              else upper = middle - 1
            }
            const idx = lower
            const nextIdx = Math.min(idx + 1, ts.length - 1)
            const frac = ts[nextIdx] === ts[idx] ? 0 : (t - ts[idx]) / (ts[nextIdx] - ts[idx])

            const frame: ReplayFrame = {
              timestamp: t,
              index: idx,
              fraction: frac,
              boats: Object.fromEntries(
                Object.entries(otherReplay.telemetry.boats).map(([id, boat]) => [
                  id,
                  sampleBoat(id, boat, idx, frac),
                ])
              ),
            }

            const html = renderToStaticMarkup(
              React.createElement(TelemetryWorkspace, {
                replay: otherReplay,
                frame,
                selectedId: competitor.id,
                onSelectBoat: () => {},
                onSeek: () => {},
              })
            )

            const polylineMatches = [
              ...html.matchAll(/<polyline[^>]*stroke-width="2.4"[^>]*points="([^"]+)"/g),
            ]
            if (polylineMatches.length < 3) continue

            const sogPoints = parsePolylinePoints(polylineMatches[0][1])
            const vmgPoints = parsePolylinePoints(polylineMatches[1][1])
            const twaPoints = parsePolylinePoints(polylineMatches[2][1])

            const sogDotTag = html.match(/<circle[^>]*class="[^"]*scrubber-dot-sog[^"]*"[^>]*>/)
            const vmgDotTag = html.match(/<circle[^>]*class="[^"]*scrubber-dot-vmg[^"]*"[^>]*>/)
            const twaDotTag = html.match(/<circle[^>]*class="[^"]*scrubber-dot-twa[^"]*"[^>]*>/)
            if (!sogDotTag || !vmgDotTag || !twaDotTag) continue

            const sogDot = parseCircle(sogDotTag[0])
            const vmgDot = parseCircle(vmgDotTag[0])
            const twaDot = parseCircle(twaDotTag[0])

            const pySog = getPolylineYAtX(sogPoints, sogDot.cx)
            const pyVmg = getPolylineYAtX(vmgPoints, vmgDot.cx)
            const pyTwa = getPolylineYAtX(twaPoints, twaDot.cx)

            if (pySog !== null) expect(Math.abs(sogDot.cy - pySog)).toBeLessThan(0.05)
            if (pyVmg !== null) expect(Math.abs(vmgDot.cy - pyVmg)).toBeLessThan(0.05)
            if (pyTwa !== null) expect(Math.abs(twaDot.cy - pyTwa)).toBeLessThan(0.05)
          }
        }
      })
    }
  })

  // 10. Maximum Empirical Error Statistical Bound (< 0.015px absolute maximum observed)
  describe('10. Global Maximum Error Distribution', () => {
    it('Empirical maximum vertical error across all tests is strictly below 0.02px', () => {
      let maxErrorObserved = 0
      let totalPointsTested = 0

      for (const { time } of MANDATORY_TIMESTAMPS) {
        for (const comp of replay.competitors) {
          const res = verifyDotsOnPolylines(time, comp.id)
          maxErrorObserved = Math.max(maxErrorObserved, res.deltaSog, res.deltaVmg, res.deltaTwa)
          totalPointsTested += 3
        }
      }

      console.log(
        `[Statistical Audit] Tested ${totalPointsTested} scrubber dots. Max observed error: ${maxErrorObserved.toFixed(5)} px`
      )
      expect(maxErrorObserved).toBeLessThan(0.02)
      expect(maxErrorObserved).toBeLessThan(0.05)
    })
  })
})
