import type { ReplayManifest } from '../types/replay'

export interface RaceListing { id: string; name: string; date: string; replayFile: string; regattaId: string; regattaName: string; venue: string }
interface RawRace { id?: unknown; name?: unknown; date?: unknown; replay_file?: unknown; file?: unknown }
interface RawRegatta { id?: unknown; name?: unknown; venue?: unknown; races?: unknown }

/** Supports the current regattas catalog and the older flat races catalog. */
export function parseRaceCatalog(value: unknown): RaceListing[] {
  if (!value || typeof value !== 'object') throw new Error('Race catalog is missing')
  const root = value as { regattas?: unknown; races?: unknown; regatta?: unknown; venue?: unknown }
  const groups: RawRegatta[] = Array.isArray(root.regattas) ? root.regattas : [{ id: 'legacy', name: root.regatta, venue: root.venue, races: root.races }]
  const listings: RaceListing[] = []
  for (const group of groups) {
    if (!Array.isArray(group.races)) continue
    for (const candidate of group.races) {
      const race = candidate as RawRace
      const path = race.replay_file ?? race.file
      if (typeof race.id !== 'string' || typeof race.name !== 'string' || typeof race.date !== 'string' || typeof path !== 'string') continue
      if (!/^replays\/[a-zA-Z0-9_-]+\.json$/.test(path)) continue
      listings.push({ id: race.id, name: race.name, date: race.date, replayFile: path, regattaId: String(group.id ?? 'regatta'), regattaName: String(group.name ?? 'Regatta'), venue: String(group.venue ?? '') })
    }
  }
  if (!listings.length) throw new Error('The race catalog contains no loadable races')
  return listings
}

export async function loadCatalog(signal?: AbortSignal): Promise<RaceListing[]> {
  const response = await fetch('/data/manifests.json', { signal })
  if (!response.ok) throw new Error(`Could not load race catalog (${response.status})`)
  return parseRaceCatalog(await response.json() as unknown)
}

export async function loadReplay(listing: RaceListing, signal?: AbortSignal): Promise<ReplayManifest> {
  const response = await fetch(`/data/${listing.replayFile}`, { signal })
  if (!response.ok) throw new Error(`Could not load ${listing.name} (${response.status})`)
  const replay = await response.json() as ReplayManifest
  if (replay.id !== listing.id || !Array.isArray(replay.telemetry?.timestamps) || !Array.isArray(replay.competitors) || !replay.competitors.length) throw new Error('Race data does not match its catalog entry')
  const count = replay.telemetry.timestamps.length
  if (count < 2 || !replay.course?.marks || !replay.chronology || !replay.telemetry.boats) throw new Error('Race data is incomplete')
  const fields = ['x', 'y', 'heading', 'cog', 'sog', 'vmg', 'twa', 'twd', 'tws', 'progress_m', 'leg'] as const
  for (const competitor of replay.competitors) {
    const boat = replay.telemetry.boats[competitor.id]
    if (!boat || fields.some((field) => !Array.isArray(boat[field]) || boat[field].length !== count)) throw new Error(`Telemetry columns are incomplete for ${competitor.team_code}`)
  }
  return replay
}

/** Resolve an analysis event to a catalog replay without trusting a detail file path. */
export function resolveAnalysisReplay(races: RaceListing[], currentRaceId: string, raceId: string, timestamp?: number) {
  const race = races.find((entry) => entry.id === raceId)
  if (!race) return null
  return {
    race,
    sameRace: race.id === currentRaceId,
    seekTimestamp: timestamp !== undefined && Number.isFinite(timestamp) ? timestamp : undefined,
  }
}
