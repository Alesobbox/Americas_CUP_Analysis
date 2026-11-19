import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { RaceListing } from '../../engine/catalog'
import './race-library.css'

interface CoursePreview {
  boat_count: number
  race_type: string | null
  boat_class: string
  boundary: number[][]
  marks: Array<{ name: string; point: number[] }>
  gates: Array<{ kind: string; points: number[][] }>
}
interface PreviewIndex {
  schema_version: '1.0'
  method_version: 'course-preview-1'
  races: Record<string, CoursePreview>
}

// Share the small immutable index across dialog mounts, including StrictMode.
let previewRequest: Promise<PreviewIndex | null> | null = null
function loadCoursePreviews(): Promise<PreviewIndex | null> {
  if (!previewRequest)
    previewRequest = fetch('/data/presentation/race_previews.json')
      .then((response) => (response.ok ? (response.json() as Promise<PreviewIndex>) : null))
      .then((value) =>
        value?.schema_version === '1.0' &&
        value.method_version === 'course-preview-1' &&
        value.races
          ? value
          : null
      )
      .catch(() => null)
  return previewRequest
}

function CourseArtwork({
  preview,
  name,
  featured = false,
}: {
  preview?: CoursePreview
  name: string
  featured?: boolean
}) {
  const gridId = useId().replace(/:/g, '')
  return (
    <div className={`race-course-art${featured ? ' featured' : ''}`}>
      {preview ? (
        <svg viewBox="0 0 420 250" role="img" aria-label={`${name} course schematic`}>
          <defs>
            <pattern id={gridId} width="28" height="28" patternUnits="userSpaceOnUse">
              <path d="M28 0H0V28" fill="none" className="race-preview-grid" />
            </pattern>
          </defs>
          <rect width="420" height="250" fill={`url(#${gridId})`} />
          {preview.boundary.length > 2 && (
            <polygon
              points={preview.boundary.map((p) => p.join(',')).join(' ')}
              className="race-preview-boundary"
            />
          )}
          {preview.gates.map((gate, index) => (
            <line
              key={index}
              x1={gate.points[0][0]}
              y1={gate.points[0][1]}
              x2={gate.points[1][0]}
              y2={gate.points[1][1]}
              className={`race-preview-gate${gate.kind === 'START' ? ' start' : ''}`}
            />
          ))}
          {preview.marks.map((mark) => (
            <g key={mark.name}>
              <circle cx={mark.point[0]} cy={mark.point[1]} r="4" className="race-preview-mark" />
              {featured && (
                <text x={mark.point[0] + 8} y={mark.point[1] + 4}>
                  {mark.name}
                </text>
              )}
            </g>
          ))}
          <g className="race-preview-north" transform="translate(386 26)">
            <path d="M0 16V0m-4 5 4-5 4 5" />
            <text x="0" y="30" textAnchor="middle">
              N
            </text>
          </g>
        </svg>
      ) : (
        <div className="race-preview-missing">
          <span>Course preview</span>
          <small>Available in replay</small>
        </div>
      )}
      <span className="race-preview-caption">
        {preview
          ? featured
            ? 'Course schematic · north up'
            : 'Course schematic'
          : 'No preview published'}
      </span>
    </div>
  )
}

function raceFacts(preview?: CoursePreview) {
  if (!preview) return 'Race details available in replay'
  const type =
    preview.race_type === 'RACE_TYPE_MATCH'
      ? 'Match race'
      : preview.race_type === 'RACE_TYPE_FLEET'
        ? 'Fleet race'
        : 'Race type unavailable'
  return `${preview.boat_class} · ${type} · ${preview.boat_count} boats`
}

export function RacePickerModal({
  races,
  currentId,
  onSelect,
  onClose,
}: {
  races: RaceListing[]
  currentId: string
  onSelect: (race: RaceListing) => void
  onClose: () => void
}) {
  const [query, setQuery] = useState('')
  const [previews, setPreviews] = useState<PreviewIndex | null>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const titleId = useId()
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  useEffect(() => {
    let active = true
    void loadCoursePreviews().then((value) => {
      if (active) setPreviews(value)
    })
    return () => {
      active = false
    }
  }, [])
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    searchRef.current?.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeRef.current()
        return
      }
      if (event.key !== 'Tab' || !dialogRef.current) return
      const controls = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input, select, a[href]'
        )
      ).filter((element) => element.offsetParent !== null)
      const first = controls[0],
        last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last?.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first?.focus()
      }
    }
    window.addEventListener('keydown', keydown)
    return () => {
      window.removeEventListener('keydown', keydown)
      document.body.style.overflow = previousOverflow
      if (opener?.isConnected) opener.focus()
    }
  }, [])

  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase()
    return races.filter((race) =>
      `${race.name} ${race.date} ${race.venue} ${race.regattaName} ${race.id}`
        .toLocaleLowerCase()
        .includes(term)
    )
  }, [query, races])
  const groups = [
    ...new Map(
      filtered.map((race) => [race.regattaId, { id: race.regattaId, name: race.regattaName }])
    ).values(),
  ]
  const current = races.find((race) => race.id === currentId)

  return (
    <div
      className="modal-shade race-library-shade"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={dialogRef}
        className="modal race-picker race-library"
        role="dialog"
        aria-modal="true"
        aria-label="Choose race"
      >
        <div className="race-library-heading">
          <div>
            <h2 id={titleId}>Choose a race</h2>
            <p>
              {races.length} races across {new Set(races.map((race) => race.regattaId)).size}{' '}
              regattas.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close race picker"
            className="race-library-close"
          >
            ×
          </button>
        </div>
        {current && !query && (
          <div className="race-library-feature">
            <CourseArtwork preview={previews?.races[current.id]} name={current.name} featured />
            <div className="race-library-feature-copy">
              <span className="race-library-current">Current race</span>
              <h3>{current.name}</h3>
              <p>
                {current.venue} · {current.date}
              </p>
              <p>{raceFacts(previews?.races[current.id])}</p>
              <button type="button" onClick={() => onSelect(current)}>
                Return to race <span aria-hidden="true">→</span>
              </button>
            </div>
          </div>
        )}
        <div className="race-library-search">
          <label htmlFor={titleId + '-search'}>Find a race</label>
          <div>
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
              <circle cx="10.5" cy="10.5" r="6.5" />
              <path d="m16 16 5 5" />
            </svg>
            <input
              ref={searchRef}
              id={titleId + '-search'}
              type="search"
              placeholder="Race, venue or date"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <span role="status">
            {filtered.length} of {races.length} races
          </span>
        </div>
        {!filtered.length && (
          <p className="race-library-empty">
            No races match “{query}”. Try a venue, race name or date.
          </p>
        )}
        {groups.map((group) => (
          <section className="race-library-group" key={group.id}>
            <div className="race-library-group-heading">
              <h3>{group.name}</h3>
              <span>{filtered.filter((race) => race.regattaId === group.id).length} races</span>
            </div>
            <div className="race-library-grid">
              {filtered
                .filter((race) => race.regattaId === group.id)
                .map((race) => (
                  <button
                    key={race.id}
                    type="button"
                    className={`race-option race-library-option${race.id === currentId ? ' current' : ''}`}
                    onClick={() => onSelect(race)}
                    aria-current={race.id === currentId ? 'true' : undefined}
                  >
                    <CourseArtwork preview={previews?.races[race.id]} name={race.name} />
                    <span className="race-library-option-copy">
                      <small>{race.date}</small>
                      <strong>{race.name}</strong>
                      <small>{raceFacts(previews?.races[race.id])}</small>
                      <span className="race-library-option-action">
                        {race.id === currentId ? 'Current race' : 'Open race'}{' '}
                        <span aria-hidden="true">↗</span>
                      </span>
                    </span>
                  </button>
                ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
