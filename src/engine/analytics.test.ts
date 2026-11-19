import { describe, expect, it } from 'vitest'
import { compareBoats, getStandings, statusAt, windAt } from './analytics'
import type { BoatFrame, Competitor, ReplayFrame, ReplayManifest } from '../types/replay'

const makeCompetitor = (
  id: string,
  elapsed: number,
  rank: number,
  classification = `RANK_${rank}`
): Competitor => ({
  id,
  team_code: id,
  team_name: id,
  color: '#ffffff',
  classification,
  start: {
    crossing_time: 1_000,
    delta_to_gun_s: 0,
    ocs: classification === 'RET',
    chosen_side: 'PORT',
  },
  gates: [],
  manoeuvres: [],
  summary: {
    finish_rank: rank,
    elapsed_s: elapsed,
    distance_sailed_m: 0,
    tack_count: 0,
    gybe_count: 0,
    avg_speed_kt: 0,
    avg_vmg_kt: 0,
  },
})
const makeBoat = (id: string, progress: number, x = 0, y = 0): BoatFrame => ({
  id,
  x,
  y,
  heading: 0,
  cog: 0,
  sog: 20,
  vmg: 15,
  twa: 45,
  twd: 50,
  tws: 12,
  progress_m: progress,
  leg: 1,
})
const replay = {
  id: 'race',
  name: 'Race',
  venue: 'Venue',
  date: '2026-10-07',
  chronology: { gun_time: 1_000, window_start: 0, window_end: 200_000 },
  competitors: [
    makeCompetitor('A', 100, 1),
    makeCompetitor('B', 110, 2),
    makeCompetitor('C', 0, 3, 'RET'),
  ],
  course: {
    axis_deg: 0,
    length_m: 100,
    origin: { lat: 0, lon: 0 },
    projection: { k_lat: 1, k_lon: 1 },
    boundaries: { race: [], safety: [] },
    marks: {
      RM8: { name: 'RM8', target: [0, 0] },
      RM6: { name: 'RM6', target: [10, 0] },
      RM4: { name: 'RM4', target: [0, 100] },
      RM2: { name: 'RM2', target: [10, 100] },
    },
  },
  wind: { reference_twd_deg: 50, reference_tws_kt: 12, timeline: [] },
  telemetry: { timestamps: [], boats: {}, marks: {} },
} as ReplayManifest
const at = (timestamp: number, a: number, b: number): ReplayFrame => ({
  timestamp,
  index: 0,
  fraction: 0,
  boats: { A: makeBoat('A', a), B: makeBoat('B', b), C: makeBoat('C', 0) },
  marks: {},
})

describe('live tactical analytics', () => {
  it('does not reveal an untimed retirement before the end of the replay window', () => {
    const boat = {
      ...makeCompetitor('C', 0, 3, 'RET'),
      start: { crossing_time: 0, delta_to_gun_s: 0, ocs: true, chosen_side: 'PORT' as const },
    }
    expect(statusAt(replay, boat, 20_000)).toBe('PRE START')
    expect(statusAt(replay, boat, replay.chronology.window_end)).toBe('OCS / RET')
  })
  it('does not turn an archive wind reference or a future sample into current wind', () => {
    expect(Number.isNaN(windAt(replay, 1000).tws)).toBe(true)
    const future = {
      ...replay,
      wind: { ...replay.wind, timeline: [{ t: 2000, tws: 12, twd: 50 }] },
    }
    expect(Number.isNaN(windAt(future, 1000).tws)).toBe(true)
    expect(windAt(future, 2000).tws).toBe(12)
  })
  it('keeps pre-start boats unranked and retired boats out of racing positions', () => {
    expect(getStandings(replay, at(500, 0, 0)).every((entry) => entry.rank === null)).toBe(true)
    const entries = getStandings(replay, at(11_000, 100, 70))
    expect(entries.map((entry) => entry.competitor.id)).toEqual(['A', 'B', 'C'])
    expect(entries[1].gapM).toBe(30)
    expect(entries[1].gapIsEstimate).toBe(true)
    expect(entries[2].status).toBe('OCS / RET')
  })

  it('switches to recorded finish deltas after both boats finish', () => {
    const entries = getStandings(replay, at(112_000, 400, 400))
    expect(entries[0].status).toBe('FINISHED')
    expect(entries[1].gapS).toBe(10)
    expect(entries[1].gapIsEstimate).toBe(false)
  })

  it('computes next-gate and pairwise geometry without conflating physical separation with race progress', () => {
    const a = makeBoat('A', 100, 0, 0)
    const b = makeBoat('B', 150, 30, 40)
    const pair = compareBoats(a, b, 0)
    expect(pair.separationM).toBe(50)
    expect(pair.alongLegM).toBe(40)
    expect(pair.progressDeltaM).toBe(50)
    expect(statusAt(replay, replay.competitors[0], 102_000)).toBe('FINISHED')
  })

  it('formats live gap string with signed deltas and strictly forbids ~ character', () => {
    const entries = getStandings(replay, at(11_000, 100, 70))
    expect(entries[0].gapS).toBe(0)
    const b = entries[1]
    expect(b.gapS).toBeGreaterThan(0)
    const formattedGap = b.gapS === 0 ? 'LEAD' : `+${b.gapS!.toFixed(1)}s`
    expect(formattedGap).toMatch(/^\+\d+\.\d+s$/)
    expect(formattedGap.includes('~')).toBe(false)
  })

  it('computes distance to leader for 2-boat match races in pre-start, racing, and finished phases', () => {
    const matchReplay: ReplayManifest = {
      ...replay,
      competitors: [makeCompetitor('A', 100, 1), makeCompetitor('B', 110, 2)],
    }
    // 1. Pre-start phase: Euclidean physical separation
    const preStartFrame: ReplayFrame = {
      timestamp: 500,
      index: 0,
      fraction: 0,
      boats: {
        A: makeBoat('A', 0, 0, 0),
        B: makeBoat('B', 0, 60, 80),
      },
      marks: {},
    }
    const preStandings = getStandings(matchReplay, preStartFrame)
    expect(preStandings).toHaveLength(2)
    expect(preStandings[1].gapM).toBeCloseTo(100, 1) // hypot(60, 80) = 100m
    expect(preStandings[1].gapM).toBeGreaterThan(0)

    // 2. Racing phase: Course progress delta
    const racingFrame: ReplayFrame = {
      timestamp: 15_000,
      index: 1,
      fraction: 0,
      boats: {
        A: makeBoat('A', 500, 0, 100),
        B: makeBoat('B', 422, 10, 80),
      },
      marks: {},
    }
    const racingStandings = getStandings(matchReplay, racingFrame)
    expect(racingStandings[0].rank).toBe(1)
    expect(racingStandings[0].gapS).toBe(0)
    expect(racingStandings[1].gapM).toBeCloseTo(78, 1) // 500 - 422 = 78m
    expect(racingStandings[1].gapS).toBeGreaterThan(0)

    // 3. Finished phase: delta remains available
    const finishedFrame: ReplayFrame = {
      timestamp: 112_000,
      index: 2,
      fraction: 0,
      boats: {
        A: makeBoat('A', 2000, 0, 0),
        B: makeBoat('B', 2000, 0, 0),
      },
      marks: {},
    }
    const finishedStandings = getStandings(matchReplay, finishedFrame)
    expect(finishedStandings[0].status).toBe('FINISHED')
    expect(finishedStandings[1].status).toBe('FINISHED')
    expect(finishedStandings[1].gapS).toBe(10) // 110s - 100s
  })
})
