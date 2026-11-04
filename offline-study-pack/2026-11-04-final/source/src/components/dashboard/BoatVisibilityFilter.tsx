import { useEffect, useRef, useState } from 'react'
import type { Competitor } from '../../types/replay'

export function BoatVisibilityFilter({ boats, visibleId, onChange }: { boats: Competitor[]; visibleId: string | null; onChange: (id: string | null) => void }) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape' && open) { setOpen(false); trigger.current?.focus() } }
    document.addEventListener('pointerdown', outside); document.addEventListener('keydown', key)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', key) }
  }, [open])
  return <div className="header-dropdown-container boat-visibility-filter" ref={root}>
    <button ref={trigger} className="hdr-pill-dropdown-btn" aria-expanded={open} aria-controls="boat-visibility-list" onClick={() => setOpen((value) => !value)}>{visibleId ? boats.find((boat) => boat.id === visibleId)?.team_code : 'All Boats'}<span aria-hidden="true">⌄</span></button>
    {open && <div className="hdr-dropdown-popover" id="boat-visibility-list"><div className="popover-header">Visible on course and traces</div><button className={`popover-item ${visibleId === null ? 'active' : ''}`} onClick={() => { onChange(null); setOpen(false) }}><strong>All Boats</strong><small>{boats.length} competitors</small></button>{boats.map((boat) => <button key={boat.id} className={`popover-item ${visibleId === boat.id ? 'active' : ''}`} onClick={() => { onChange(boat.id); setOpen(false) }}><span className="boat-filter-identity"><i style={{ background: boat.color }} />{boat.team_code}</span><small>{boat.team_name}</small></button>)}</div>}
  </div>
}
