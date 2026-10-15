import { useEffect } from 'react'
import type { RaceListing } from '../../engine/catalog'

export function RacePickerModal({ races, currentId, onSelect, onClose }: { races: RaceListing[]; currentId: string; onSelect: (race: RaceListing) => void; onClose: () => void }) {
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', keydown)
    return () => window.removeEventListener('keydown', keydown)
  }, [onClose])

  const groups = Array.from(
    new Map(
      races.map((race) => [
        race.regattaId,
        {
          id: race.regattaId,
          name: race.regattaName,
          venue: race.venue,
        },
      ]),
    ).values(),
  )

  return (
    <div className="modal-shade" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div className="modal race-picker" role="dialog" aria-modal="true" aria-label="Choose race">
        <div className="modal-head">
          <div>
            <span className="eyebrow">REGATTA ARCHIVE</span>
            <h2>Choose a race</h2>
          </div>
          <button onClick={onClose} aria-label="Close race picker">×</button>
        </div>
        {groups.map((group) => (
          <section key={group.id}>
            <h3>{group.name}</h3>
            {races
              .filter((race) => race.regattaId === group.id)
              .map((race) => (
                <button
                  key={race.id}
                  className={`race-option${race.id === currentId ? ' current' : ''}`}
                  onClick={() => onSelect(race)}
                >
                  <span>
                    <strong>{race.name}</strong>
                    <small>{race.venue} · {race.date}</small>
                  </span>
                  <em>{race.id === currentId ? 'CURRENT' : 'OPEN'}</em>
                </button>
              ))}
          </section>
        ))}
      </div>
    </div>
  )
}
