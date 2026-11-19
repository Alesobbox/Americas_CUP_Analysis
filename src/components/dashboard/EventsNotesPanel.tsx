import { evidenceText } from '../../utils/evidenceText'
import { useEffect, useMemo, useState } from 'react'
import type { AnalysisEvent } from '../../types/analysis'
import { eventColor, eventType } from './RaceTimelinePanel'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'

interface EventsNotesPanelProps {
  replay: ReplayManifest
  frame: ReplayFrame
  onSeek: (time: number) => void
  selectedId: string | null
  events?: AnalysisEvent[]
}

export interface EventNoteItem {
  id: string
  timeStr: string
  timestamp: number
  type: string
  color: string
  title: string
  detail?: string
  boatCode?: string
}

function formatRelativeClock(deltaMs: number): string {
  const sign = deltaMs >= 0 ? '+' : '−'
  const totalSec = Math.floor(Math.abs(deltaMs) / 1000)
  const mm = Math.floor(totalSec / 60)
  const ss = totalSec % 60
  return `${sign}${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

export function EventsNotesPanel({
  replay,
  frame,
  onSeek,
  selectedId: _selectedId,
  events,
}: EventsNotesPanelProps) {
  const [activeTab, setActiveTab] = useState<'All' | 'Tacks' | 'Marks' | 'Wind' | 'Notes'>('All')
  const [showAddModal, setShowAddModal] = useState(false)
  const [newNoteText, setNewNoteText] = useState('')
  const readNotes = (raceId: string): EventNoteItem[] => {
    try {
      const stored = localStorage.getItem(`regatta_notes_${raceId}`)
      const parsed: unknown = stored ? JSON.parse(stored) : []
      return Array.isArray(parsed)
        ? (parsed.filter(
            (item) =>
              item &&
              typeof item.id === 'string' &&
              Number.isFinite(item.timestamp) &&
              typeof item.title === 'string' &&
              item.type === 'Note'
          ) as EventNoteItem[])
        : []
    } catch {
      return []
    }
  }
  const [customNotes, setCustomNotes] = useState<EventNoteItem[]>(() => readNotes(replay.id))
  useEffect(() => {
    setCustomNotes(readNotes(replay.id))
  }, [replay.id])

  const { chronology } = replay

  // Only the exported analysis event feed and user-authored notes enter this list.
  const allEvents = useMemo<EventNoteItem[]>(() => {
    const sourced = (events ?? [])
      .filter(
        (event) => Number.isFinite(event.timestamp_ms) && event.timestamp_ms <= frame.timestamp
      )
      .map((event): EventNoteItem => {
        const boat = replay.competitors.find((candidate) => candidate.id === event.boat_id)
        const normalized = eventType(event.type)
        const displayType =
          normalized === 'wind_shift'
            ? 'Wind shift'
            : normalized.charAt(0).toUpperCase() + normalized.slice(1)
        return {
          id: event.id,
          timeStr: formatRelativeClock((event.timestamp_ms as number) - chronology.gun_time),
          timestamp: event.timestamp_ms as number,
          type: displayType,
          color: eventColor(event.type),
          title: evidenceText(event.label),
          detail: evidenceText(
            `${event.quality} · ${event.source}${event.unavailable_reason ? ` · ${event.unavailable_reason}` : ''}`
          ),
          boatCode: boat?.team_code,
        }
      })
    return [...sourced, ...customNotes.filter((note) => note.timestamp <= frame.timestamp)].sort(
      (a, b) => a.timestamp - b.timestamp
    )
  }, [chronology.gun_time, customNotes, events, replay.competitors, frame.timestamp])

  // Filter based on active tab
  const filteredEvents = useMemo(() => {
    if (activeTab === 'All') return allEvents
    if (activeTab === 'Tacks')
      return allEvents.filter((e) => e.type === 'Tack' || e.type === 'Gybe')
    if (activeTab === 'Marks')
      return allEvents.filter((e) => ['Gun', 'Mark', 'Gate', 'Start', 'Finish'].includes(e.type))
    if (activeTab === 'Wind') return allEvents.filter((e) => e.type === 'Wind shift')
    if (activeTab === 'Notes') return allEvents.filter((e) => e.type === 'Note')
    return allEvents
  }, [activeTab, allEvents])

  const handleAddNote = () => {
    if (!newNoteText.trim()) return
    const deltaMs = frame.timestamp - chronology.gun_time
    const newNote: EventNoteItem = {
      id: `note-${Date.now()}`,
      timeStr: formatRelativeClock(deltaMs),
      timestamp: frame.timestamp,
      type: 'Note',
      color: '#3b82f6',
      title: newNoteText.trim(),
    }
    const updated = [...customNotes, newNote]
    setCustomNotes(updated)
    try {
      localStorage.setItem(`regatta_notes_${replay.id}`, JSON.stringify(updated))
    } catch {}
    setNewNoteText('')
    setShowAddModal(false)
  }

  return (
    <article className="events-notes-card" aria-label="Events and Notes">
      {/* Card Header */}
      <div className="card-header events-notes-header">
        <div className="header-left">
          <strong className="panel-title">Events & notes</strong>
        </div>
        <button
          type="button"
          className="add-note-btn"
          onClick={() => setShowAddModal((prev) => !prev)}
          title="Add a note at the current race timestamp"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path
              d="M6 2V10M2 6H10"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
          </svg>
          <span>Add note</span>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="events-filter-tabs" role="tablist">
        {(['All', 'Tacks', 'Marks', 'Wind', 'Notes'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            className={`tab-pill-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Inline Add Note Form */}
      {showAddModal && (
        <div className="inline-add-note-box">
          <input
            type="text"
            className="note-input-field"
            placeholder="Type tactical note..."
            value={newNoteText}
            onChange={(e) => setNewNoteText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleAddNote()
              if (e.key === 'Escape') setShowAddModal(false)
            }}
            autoFocus
          />
          <div className="inline-note-actions">
            <button type="button" className="note-save-btn" onClick={handleAddNote}>
              Save
            </button>
            <button
              type="button"
              className="note-cancel-btn"
              onClick={() => setShowAddModal(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Chronological Event Cards List */}
      <div className="events-list-scrollable">
        {filteredEvents.length === 0 && (
          <p className="timeline-empty-message">
            {events ? 'No sourced events for this filter' : 'Event feed unavailable for this race'}
          </p>
        )}
        {filteredEvents.map((evt) => {
          const isNearby = Math.abs(frame.timestamp - evt.timestamp) < 5000
          return (
            <div
              key={evt.id}
              className={`event-item-row ${isNearby ? 'current-active' : ''}`}
              onClick={() => onSeek(evt.timestamp)}
              title={`${evt.title} · ${evt.detail ?? 'User note'}`}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSeek(evt.timestamp)
                }
              }}
            >
              <div className="event-time-col">{evt.timeStr}</div>

              <div className="event-type-badge-wrap">
                <span className="event-dot-indicator" style={{ backgroundColor: evt.color }} />
                <span className="event-type-label">{evt.type}</span>
              </div>

              <div className="event-desc-col" title={evt.title}>
                {evt.title}
              </div>

              <div className="event-action-col" title={evt.detail}>
                {evt.boatCode ?? ''}
              </div>
            </div>
          )
        })}
      </div>
    </article>
  )
}
