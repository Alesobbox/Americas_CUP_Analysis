import type { BoatFrame, Competitor, Point, ReplayFrame, ReplayManifest } from '../types/replay'

const KNOTS_TO_MPS = 1852 / 3600

export type RaceStatus = 'PRE START' | 'RACING' | 'FINISHED' | 'DNF' | 'OCS / RET'

export interface Standing {
  competitor: Competitor
  frame: BoatFrame
  rank: number | null
  status: RaceStatus
  gapM: number | null
  gapS: number | null
  gapIsEstimate: boolean
}

export interface Comparison {
  separationM: number
  eastM: number
  northM: number
  alongLegM: number
  lateralM: number
  progressDeltaM: number
  speedDeltaKt: number
  vmgDeltaKt: number
  closureMps: number
}

export function finishTime(replay: ReplayManifest, competitor: Competitor): number | null {
  return competitor.classification.startsWith('RANK_') && competitor.summary.elapsed_s > 0
    ? replay.chronology.gun_time + competitor.summary.elapsed_s * 1000
    : null
}

export function statusAt(replay: ReplayManifest, competitor: Competitor, timestamp: number): RaceStatus {
  if (timestamp < replay.chronology.gun_time) return 'PRE START'
  if ((competitor.start.ocs && competitor.start.crossing_time > 0 && competitor.start.crossing_time <= timestamp) ||
      (competitor.classification === 'RET' && timestamp >= replay.chronology.window_end)) return 'OCS / RET'
  if (competitor.classification === 'DNF' && timestamp >= replay.chronology.window_end) return 'DNF'
  if (!(competitor.start.crossing_time > 0) || competitor.start.crossing_time > timestamp) return 'PRE START'
  const finish = finishTime(replay, competitor)
  if (finish !== null && timestamp >= finish) return 'FINISHED'
  if (competitor.classification === 'DNF' && timestamp >= replay.chronology.window_end) return 'DNF'
  return 'RACING'
}

/** Seconds are an estimate from leader speed while racing; official deltas are used after both boats finish. */
export function getStandings(replay: ReplayManifest, frame: ReplayFrame): Standing[] {
  const entries = replay.competitors
    .filter((competitor) => frame.boats[competitor.id])
    .map((competitor) => ({ competitor, frame: frame.boats[competitor.id], rank: null, status: statusAt(replay, competitor, frame.timestamp), gapM: null, gapS: null, gapIsEstimate: false }) as Standing)

  const priority: Record<RaceStatus, number> = { FINISHED: 0, RACING: 1, 'PRE START': 2, DNF: 3, 'OCS / RET': 4 }
  entries.sort((a, b) => {
    if (priority[a.status] !== priority[b.status]) return priority[a.status] - priority[b.status]
    if (a.status === 'FINISHED') return (finishTime(replay, a.competitor) ?? Infinity) - (finishTime(replay, b.competitor) ?? Infinity)
    if (a.status === 'RACING') return b.frame.progress_m - a.frame.progress_m || a.competitor.team_code.localeCompare(b.competitor.team_code)
    return a.competitor.team_code.localeCompare(b.competitor.team_code)
  })

  const leader = entries.find((entry) => entry.status === 'FINISHED' || entry.status === 'RACING')
  let placed = 0
  for (const entry of entries) {
    if (entry.status === 'PRE START' || entry.status === 'OCS / RET' || entry.status === 'DNF') continue
    entry.rank = ++placed
    if (!leader || entry === leader) { entry.gapM = 0; entry.gapS = 0; continue }
    entry.gapM = Math.max(0, leader.frame.progress_m - entry.frame.progress_m)
    if (leader.status === 'FINISHED' && entry.status === 'FINISHED') {
      entry.gapS = Math.max(0, ((finishTime(replay, entry.competitor) ?? 0) - (finishTime(replay, leader.competitor) ?? 0)) / 1000)
    } else {
      entry.gapS = leader.frame.sog > 0 ? entry.gapM / (leader.frame.sog * KNOTS_TO_MPS) : null
      entry.gapIsEstimate = entry.gapS !== null
    }
  }

  // Pre-start separation for 2-boat match race
  if (entries.length === 2 && entries.every((e) => e.status === 'PRE START')) {
    const dist = Math.hypot(entries[0].frame.x - entries[1].frame.x, entries[0].frame.y - entries[1].frame.y)
    entries[0].gapM = 0
    entries[1].gapM = dist
  }

  return entries
}

export function compareBoats(a: BoatFrame, b: BoatFrame, axisDeg: number): Comparison {
  const eastM = b.x - a.x
  const northM = b.y - a.y
  const separationM = Math.hypot(eastM, northM)
  const axis = axisDeg * Math.PI / 180
  const direction = a.leg > 0 && a.leg % 2 === 0 ? -1 : 1
  const alongLegM = direction * (eastM * Math.sin(axis) + northM * Math.cos(axis))
  const lateralM = eastM * Math.cos(axis) - northM * Math.sin(axis)
  const velocity = (boat: BoatFrame): Point => [Math.sin(boat.cog * Math.PI / 180) * boat.sog * KNOTS_TO_MPS, Math.cos(boat.cog * Math.PI / 180) * boat.sog * KNOTS_TO_MPS]
  const av = velocity(a)
  const bv = velocity(b)
  const closureMps = separationM < 0.001 ? 0 : -((bv[0] - av[0]) * eastM + (bv[1] - av[1]) * northM) / separationM
  return { separationM, eastM, northM, alongLegM, lateralM, progressDeltaM: b.progress_m - a.progress_m, speedDeltaKt: b.sog - a.sog, vmgDeltaKt: b.vmg - a.vmg, closureMps }
}

export function windAt(replay: ReplayManifest, timestamp: number) {
  const timeline = replay.wind.timeline
  if (!timeline.length || timeline[0].t > timestamp) return { t: null, twd: Number.NaN, tws: Number.NaN }
  let lo = 0
  let hi = timeline.length - 1
  while (lo < hi) { const mid = Math.ceil((lo + hi) / 2); if (timeline[mid].t <= timestamp) lo = mid; else hi = mid - 1 }
  return timeline[lo]
}
