import { describe, expect, it } from 'vitest'
import { resolveAnalysisReplay, type RaceListing } from './catalog'

const races: RaceListing[] = [
  { id: 'fleet', name: 'Fleet', date: '2026-09-22', replayFile: 'replays/fleet.json', regattaId: 'regatta', regattaName: 'Regatta', venue: 'Naples' },
  { id: 'match', name: 'Match', date: '2026-09-27', replayFile: 'replays/match.json', regattaId: 'regatta', regattaName: 'Regatta', venue: 'Naples' },
]

describe('analysis to replay navigation', () => {
  it('keeps a selected event timestamp when opening another catalog race', () => {
    expect(resolveAnalysisReplay(races, 'fleet', 'match', 1790080123456)).toEqual({
      race: races[1], sameRace: false, seekTimestamp: 1790080123456,
    })
  })

  it('seeks within the active race and ignores invalid timestamps', () => {
    expect(resolveAnalysisReplay(races, 'fleet', 'fleet', 1790079000000)?.seekTimestamp).toBe(1790079000000)
    expect(resolveAnalysisReplay(races, 'fleet', 'fleet', Number.NaN)?.seekTimestamp).toBeUndefined()
  })

  it('does not navigate to a race absent from the catalog', () => {
    expect(resolveAnalysisReplay(races, 'fleet', 'missing', 1790080123456)).toBeNull()
  })
})
