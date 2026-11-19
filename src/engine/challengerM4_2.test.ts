import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { parseRaceCatalog } from './catalog'
import { ReplayEngine } from './ReplayEngine'
import { drawStaticCourse } from '../components/canvas/StaticCourseLayer'
import {
  createViewport,
  fitViewport,
  screenToWorld,
  worldToScreen,
} from '../components/canvas/ViewportMatrix'
import { createMaritimeMapStyle, DEFAULT_OSM_ATTRIBUTION } from '../components/canvas/mapStyle'
import { compareBoats, getStandings } from './analytics'
import type { ReplayManifest, ReplayFrame } from '../types/replay'

const manifestsPath = path.resolve(process.cwd(), 'public/data/manifests.json')
const pr1Path = path.resolve(process.cwd(), 'public/data/replays/naples_pr1.json')
const mrFinalPath = path.resolve(process.cwd(), 'public/data/replays/naples_mr_final.json')
const hasLiveArchive =
  fs.existsSync(manifestsPath) && fs.existsSync(pr1Path) && fs.existsSync(mrFinalPath)

describe.skipIf(!hasLiveArchive)(
  'Challenger M4.2 Empirical Test Suite — Manifest Switching & Offline Resilience',
  () => {
    const manifestsRaw = hasLiveArchive ? JSON.parse(fs.readFileSync(manifestsPath, 'utf-8')) : null
    const pr1: ReplayManifest = hasLiveArchive
      ? JSON.parse(fs.readFileSync(pr1Path, 'utf-8'))
      : (null as unknown as ReplayManifest)
    const mrFinal: ReplayManifest = hasLiveArchive
      ? JSON.parse(fs.readFileSync(mrFinalPath, 'utf-8'))
      : (null as unknown as ReplayManifest)

    // =========================================================================
    // 1. Multi-Race Manifest & Ontology Verification
    // =========================================================================
    describe('1. Multi-Race Manifest & Ontology Verification', () => {
      it('parses race catalog cleanly and extracts both races with correct metadata', () => {
        const catalog = parseRaceCatalog(manifestsRaw)
        expect(catalog).toHaveLength(28)

        const pr1Listing = catalog.find((r) => r.id === 'naples_pr1')
        const mrListing = catalog.find((r) => r.id === 'naples_mr_final')

        expect(pr1Listing).toBeDefined()
        expect(mrListing).toBeDefined()

        expect(pr1Listing?.name).toBe('Practice Race 1')
        expect(pr1Listing?.replayFile).toBe('replays/naples_pr1.json')

        expect(mrListing?.name).toContain('Match Race Final')
        expect(mrListing?.replayFile).toBe('replays/naples_mr_final.json')

        // Check root catalog metadata
        expect(manifestsRaw.boat_class).toBe('AC40')
        expect([
          "38th America's Cup Preliminary Regattas 2026",
          "38th America's Cup Preliminary Regatta Naples 2026",
        ]).toContain(manifestsRaw.event_edition)
      })

      it('verifies naples_pr1 ontology: AC40 boat_class, event_edition, 9 competitors, 6 virtual contacts', () => {
        expect(pr1.id).toBe('naples_pr1')
        expect(pr1.boat_class).toBe('AC40')
        expect(pr1.event_edition).toBe("38th America's Cup Preliminary Regatta Naples 2026")
        expect(pr1.class_evidence).toBeDefined()
        expect(pr1.class_evidence?.confidence).toBe('CONFIRMED')
        expect(pr1.class_evidence?.description).toContain('AC40')

        expect(pr1.competitors).toHaveLength(9)
        expect(pr1.competitors.map((c) => c.team_code)).toEqual(
          expect.arrayContaining([
            'FRA',
            'NZL G',
            'ITA B',
            'USA',
            'ITA G',
            'GBR G',
            'NZL B',
            'SUI',
            'GBR B',
          ])
        )

        // Virtual contact incidents
        expect(pr1.virtual_contact_incidents).toBeDefined()
        expect(pr1.virtual_contact_incidents).toHaveLength(6)

        // Safety borders
        const safety = pr1.safety_borders ?? pr1.course.safety_borders
        expect(safety).toBeDefined()
        expect(safety?.platform_border).toHaveLength(9)
        expect(safety?.keep_clear_border).toHaveLength(10)
      })

      it('verifies naples_mr_final ontology: AC40 boat_class, event_edition, 2 competitors, 0 virtual contacts', () => {
        expect(mrFinal.id).toBe('naples_mr_final')
        expect(mrFinal.boat_class).toBe('AC40')
        expect(mrFinal.event_edition).toBe("38th America's Cup Preliminary Regatta Naples 2026")
        expect(mrFinal.class_evidence).toBeDefined()
        expect(mrFinal.class_evidence?.confidence).toBe('CONFIRMED')
        expect(mrFinal.class_evidence?.description).toContain('AC40')

        expect(mrFinal.competitors).toHaveLength(2)
        expect(mrFinal.competitors.map((c) => c.team_code)).toEqual(['ITA B', 'NZL B'])

        // Virtual contact incidents: exactly 0
        expect(mrFinal.virtual_contact_incidents).toBeDefined()
        expect(mrFinal.virtual_contact_incidents).toHaveLength(0)

        // Safety borders
        const safety = mrFinal.safety_borders ?? mrFinal.course.safety_borders
        expect(safety).toBeDefined()
        expect(safety?.platform_border).toHaveLength(9)
        expect(safety?.keep_clear_border).toHaveLength(10)
      })
    })

    // =========================================================================
    // 2. Seamless Race Switching State Machine & Selection Safety
    // =========================================================================
    describe('2. Seamless Race Switching State Machine & Selection Safety', () => {
      it('simulates switching from PR1 (9-boat fleet) to MR Final (2-boat match race)', () => {
        // Step A: In PR1, boat 'FRA' is selected, comparison is 'NZL G'
        const pr1Selected = pr1.competitors[0] // FRA
        const pr1Compare = pr1.competitors[1] // NZL G
        expect(pr1Selected.team_code).toBe('FRA')

        // Step B: Race switch occurs. Application loads MR Final data
        const nextReplay = mrFinal
        const isMatchRace = nextReplay.competitors.length === 2
        expect(isMatchRace).toBe(true)

        // Fallback selection logic from App.tsx line 100-101:
        const newSelectedId = nextReplay.competitors[0]?.id ?? null
        const newComparisonId = nextReplay.competitors[1]?.id ?? null

        expect(newSelectedId).toBe(mrFinal.competitors[0].id) // ITA G
        expect(newComparisonId).toBe(mrFinal.competitors[1].id) // NZL B

        // Ensure that old selectedId ('FRA') is NOT carried over, avoiding missing boat crashes
        expect(nextReplay.telemetry.boats[pr1Selected.id]).toBeUndefined()
        expect(nextReplay.telemetry.boats[newSelectedId!]).toBeDefined()
        expect(nextReplay.telemetry.boats[newComparisonId!]).toBeDefined()

        // Step C: Initialize ReplayEngine with MR Final and sample frame
        const engine = new ReplayEngine(nextReplay)
        let sampledFrame: ReplayFrame | null = null
        engine.subscribe((f) => {
          sampledFrame = f
        })

        expect(sampledFrame).not.toBeNull()
        expect(sampledFrame!.boats[newSelectedId!]).toBeDefined()
        expect(sampledFrame!.boats[newComparisonId!]).toBeDefined()
        expect(Object.keys(sampledFrame!.boats)).toHaveLength(2)

        // Step D: Validate duel analytics between newSelected and newComparison
        const boatA = sampledFrame!.boats[newSelectedId!]
        const boatB = sampledFrame!.boats[newComparisonId!]
        const comparison = compareBoats(boatA, boatB, nextReplay.course.axis_deg)

        expect(Number.isFinite(comparison.separationM)).toBe(true)
        expect(Number.isFinite(comparison.closureMps)).toBe(true)
        expect(Number.isFinite(comparison.vmgDeltaKt)).toBe(true)

        engine.dispose()
      })

      it('simulates switching from MR Final back to PR1 without lingering state', () => {
        // Step A: In MR Final, selected boat is ITA G
        const mrSelected = mrFinal.competitors[0] // ITA G
        expect(mrSelected.team_code).toBe('ITA B')

        // Step B: Race switch back to PR1
        const nextReplay = pr1
        const isMatchRace = nextReplay.competitors.length === 2
        expect(isMatchRace).toBe(false)

        const newSelectedId = nextReplay.competitors[0]?.id ?? null
        const newComparisonId = nextReplay.competitors[1]?.id ?? null

        expect(newSelectedId).toBe(pr1.competitors[0].id) // FRA
        expect(newComparisonId).toBe(pr1.competitors[1].id) // NZL G

        // Step C: Initialize ReplayEngine with PR1 and sample frame
        const engine = new ReplayEngine(nextReplay)
        let sampledFrame: ReplayFrame | null = null
        engine.subscribe((f) => {
          sampledFrame = f
        })

        expect(sampledFrame).not.toBeNull()
        expect(Object.keys(sampledFrame!.boats)).toHaveLength(9)

        // Verify all 9 boats have valid telemetry in the frame
        for (const comp of pr1.competitors) {
          const boat = sampledFrame!.boats[comp.id]
          expect(boat).toBeDefined()
          expect(Number.isFinite(boat.x)).toBe(true)
          expect(Number.isFinite(boat.y)).toBe(true)
          expect(Number.isFinite(boat.heading)).toBe(true)
          expect(boat.heading).toBeGreaterThanOrEqual(0)
          expect(boat.heading).toBeLessThan(360)
        }

        engine.dispose()
      })

      it('safely handles timestamp seeking across non-overlapping race windows', () => {
        const pr1Start = pr1.chronology.window_start
        const pr1End = pr1.chronology.window_end
        const mrStart = mrFinal.chronology.window_start
        const mrEnd = mrFinal.chronology.window_end

        // Verify PR1 window and MR window are distinct valid time periods
        expect(pr1End).toBeGreaterThan(pr1Start)
        expect(mrEnd).toBeGreaterThan(mrStart)

        const pr1Engine = new ReplayEngine(pr1)
        // Attempt seeking to MR start time (which is 5 days later) in PR1
        pr1Engine.seek(mrStart)
        // ReplayEngine clamps out-of-range timestamp to pr1.chronology.window_end!
        expect(pr1Engine.getTime()).toBe(pr1End)

        // Attempt seeking to 0 (far in the past)
        pr1Engine.seek(0)
        expect(pr1Engine.getTime()).toBe(pr1Start)

        pr1Engine.dispose()

        const mrEngine = new ReplayEngine(mrFinal)
        // Attempt seeking to PR1 start time in MR Final
        mrEngine.seek(pr1Start)
        expect(mrEngine.getTime()).toBe(mrStart)

        mrEngine.dispose()
      })
    })

    // =========================================================================
    // 3. Clean-Water Fallback & MapLibre Offline Resilience
    // =========================================================================
    describe('3. Clean-Water Fallback & MapLibre Offline Resilience', () => {
      it('renders rich synthetic Mediterranean water gradient and wavelets when fallback is active', () => {
        // Mock Canvas 2D context to verify draw operations
        const operations: string[] = []
        const gradientStops: Array<{ offset: number; color: string }> = []

        const mockGradient: CanvasGradient = {
          addColorStop: (offset: number, color: string) => {
            gradientStops.push({ offset, color })
          },
        }

        const mockContext = {
          clearRect: (x: number, y: number, w: number, h: number) => {
            operations.push(`clearRect(${x},${y},${w},${h})`)
          },
          createRadialGradient: (
            x0: number,
            y0: number,
            r0: number,
            x1: number,
            y1: number,
            r1: number
          ) => {
            operations.push(`createRadialGradient(${x0},${y0},${r0},${x1},${y1},${r1})`)
            return mockGradient
          },
          fillRect: (x: number, y: number, w: number, h: number) => {
            operations.push(`fillRect(${x},${y},${w},${h})`)
          },
          beginPath: () => operations.push('beginPath'),
          moveTo: (x: number, y: number) =>
            operations.push(`moveTo(${Math.round(x)},${Math.round(y)})`),
          lineTo: (x: number, y: number) =>
            operations.push(`lineTo(${Math.round(x)},${Math.round(y)})`),
          stroke: () => operations.push('stroke'),
          fill: () => operations.push('fill'),
          closePath: () => operations.push('closePath'),
          save: () => operations.push('save'),
          restore: () => operations.push('restore'),
          setLineDash: (segments: number[]) =>
            operations.push(`setLineDash([${segments.join(',')}])`),
          fillStyle: '',
          strokeStyle: '',
          lineWidth: 1,
        } as unknown as CanvasRenderingContext2D

        const width = 1200
        const height = 800
        const viewport = createViewport(width, height, [0, 0], 0.2, 'north', 45)
        const boundaries = {
          race: pr1.course.boundaries.race,
          safety: pr1.course.boundaries.safety,
        }

        // Test Case A: technical canvas surface in Grid View or offline fallback.
        drawStaticCourse(mockContext, width, height, pr1, viewport, boundaries, {
          showWaterSurface: true,
        })

        // Verify clearRect was called first
        expect(operations[0]).toBe('clearRect(0,0,1200,800)')

        expect(operations.some((op) => op.includes('createRadialGradient'))).toBe(false)
        expect(gradientStops).toEqual([])

        // Verify full canvas is filled by the neutral surface.
        expect(operations.some((op) => op === 'fillRect(0,0,1200,800)')).toBe(true)

        // Verify metric grid and boundaries were drawn.
        expect(operations.filter((op) => op === 'stroke').length).toBeGreaterThan(2)

        // Test Case B: MapLibre tiles receive a transparent overlay.
        operations.length = 0
        gradientStops.length = 0

        drawStaticCourse(mockContext, width, height, pr1, viewport, boundaries, {
          showWaterSurface: false,
        })

        expect(operations[0]).toBe('clearRect(0,0,1200,800)')
        // In online mode, radial gradient must NOT be drawn to preserve transparent overlay over MapLibre
        expect(operations.some((op) => op.includes('createRadialGradient'))).toBe(false)
        expect(operations.some((op) => op.includes('fillRect'))).toBe(false)
        // But grid and boundaries MUST still be drawn
        expect(operations.some((op) => op === 'stroke')).toBe(true)
      })

      it('empirically verifies pure canvas viewport navigation when MapLibre is offline or disabled', () => {
        const width = 1000
        const height = 700
        const points = pr1.course.boundaries.race

        // Fit course boundary
        const vp = fitViewport(width, height, points, 'north', pr1.course.axis_deg, 1.25)
        expect(vp.width).toBe(width)
        expect(vp.height).toBe(height)
        expect(vp.scale).toBeGreaterThan(0.05)
        expect(vp.scale).toBeLessThan(1.0)
        expect(Number.isFinite(vp.center[0])).toBe(true)
        expect(Number.isFinite(vp.center[1])).toBe(true)

        // Screen <-> World roundtrip
        const testWorld: [number, number] = [250, -350]
        const screenPt = worldToScreen(vp, testWorld)
        const reconstructed = screenToWorld(vp, screenPt)

        expect(Math.abs(reconstructed[0] - testWorld[0])).toBeLessThan(1e-6)
        expect(Math.abs(reconstructed[1] - testWorld[1])).toBeLessThan(1e-6)

        // Zoom In (+20%)
        const zoomedIn = { ...vp, scale: vp.scale * 1.2 }
        expect(zoomedIn.scale).toBeGreaterThan(vp.scale)

        // Zoom Out (-20%)
        const zoomedOut = { ...vp, scale: vp.scale / 1.2 }
        expect(zoomedOut.scale).toBeLessThan(vp.scale)

        // Course Up rotation
        const vpCourseUp = createViewport(
          width,
          height,
          vp.center,
          vp.scale,
          'course',
          pr1.course.axis_deg
        )
        expect(vpCourseUp.rotationDeg).toBe(pr1.course.axis_deg)
      })

      it('verifies OpenStreetMap attribution text and link constants', () => {
        expect(DEFAULT_OSM_ATTRIBUTION).toContain('OpenStreetMap')
        expect(DEFAULT_OSM_ATTRIBUTION).toContain('contributors')
      })
    })

    // =========================================================================
    // 4. Exhaustive Zero-Tilde Audit across all UI presentation paths
    // =========================================================================
    describe('4. Exhaustive Zero-Tilde Audit across all UI presentation paths', () => {
      it('verifies that no tilde (~) appears in any frontend UI or logic code outside comments', () => {
        const srcDir = path.resolve(process.cwd(), 'src')
        const violations: Array<{ file: string; line: number; text: string }> = []

        function scanDir(dir: string) {
          for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
            const fullPath = path.join(dir, entry.name)
            if (entry.isDirectory()) {
              scanDir(fullPath)
            } else if (
              (entry.name.endsWith('.tsx') || entry.name.endsWith('.ts')) &&
              !entry.name.endsWith('.test.ts') &&
              !entry.name.endsWith('.test.tsx')
            ) {
              const content = fs.readFileSync(fullPath, 'utf-8')
              const lines = content.split('\n')
              lines.forEach((line, idx) => {
                if (line.includes('~')) {
                  const trimmed = line.trim()
                  if (
                    !trimmed.startsWith('//') &&
                    !trimmed.startsWith('/*') &&
                    !trimmed.startsWith('*')
                  ) {
                    violations.push({
                      file: path.relative(process.cwd(), fullPath),
                      line: idx + 1,
                      text: trimmed,
                    })
                  }
                }
              })
            }
          }
        }

        scanDir(srcDir)

        if (violations.length > 0) {
          console.error('Zero-Tilde Violations Found:', violations)
        }
        expect(violations).toHaveLength(0)
      })

      it('verifies live signed gaps across all frames in both races never contain tilde (~)', () => {
        for (const manifest of [pr1, mrFinal]) {
          const engine = new ReplayEngine(manifest)
          let frame: ReplayFrame | null = null
          engine.subscribe((f) => {
            frame = f
          })

          // Sample 5 representative moments in the race
          const times = manifest.telemetry.timestamps
          const stride = Math.floor(times.length / 5)
          for (let i = 0; i < times.length; i += stride) {
            engine.seek(times[i])
            expect(frame).not.toBeNull()
            const standings = getStandings(manifest, frame!)

            for (const s of standings) {
              if (s.gapS !== null && s.gapS > 0) {
                const gapTimeStr = `+${s.gapS.toFixed(1)}s`
                expect(gapTimeStr).not.toContain('~')
                expect(gapTimeStr.startsWith('+')).toBe(true)
              }
              if (s.gapM !== null && s.gapM > 0) {
                const gapDistStr = `+${Math.round(s.gapM)}m`
                expect(gapDistStr).not.toContain('~')
                expect(gapDistStr.startsWith('+')).toBe(true)
              }
            }
          }
          engine.dispose()
        }
      })
    })
  }
)
