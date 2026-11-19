import { describe, expect, it } from 'vitest'
import { parseRaceCatalog } from './catalog'

describe('manifest-driven race catalog', () => {
  it('keeps the regatta hierarchy and accepts a second race without source edits', () => {
    const races = parseRaceCatalog({
      regattas: [
        {
          id: 'naples',
          name: 'Naples',
          venue: 'Gulf',
          races: [
            { id: 'r1', name: 'First', date: '2026-09-22', replay_file: 'replays/r1.json' },
            { id: 'r2', name: 'Second', date: '2026-09-23', replay_file: 'replays/r2.json' },
          ],
        },
      ],
    })
    expect(races.map((race) => race.id)).toEqual(['r1', 'r2'])
    expect(races[1].regattaName).toBe('Naples')
  })

  it('supports the older flat manifest and ignores unsafe data paths', () => {
    const races = parseRaceCatalog({
      regatta: 'Naples',
      venue: 'Gulf',
      races: [
        { id: 'valid', name: 'Race', date: '2026-09-22', file: 'replays/race.json' },
        { id: 'bad', name: 'Bad', date: '2026-09-22', file: '../secret.json' },
      ],
    })
    expect(races).toHaveLength(1)
    expect(races[0].id).toBe('valid')
    expect(() => parseRaceCatalog({ races: [] })).toThrow('no loadable races')
  })
})
