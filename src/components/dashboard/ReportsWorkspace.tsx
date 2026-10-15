import { useEffect, useState } from 'react'
import type { RaceListing } from '../../engine/catalog'
import type { ReplayManifest } from '../../types/replay'

interface Artifact { id: string; url: string; race_id: string | null; label: string; view: string; bytes: number; format: string }
interface Inventory { schema_version: '1.0'; summary: { race_count: number; replayed_boat_races: number }; artifacts: Artifact[] }

export function ReportsWorkspace({ replay, catalog, onOpenRace }: {
  replay: ReplayManifest
  catalog: RaceListing[]
  onOpenRace: (race: RaceListing, view: string) => void
}) {
  const [inventory, setInventory] = useState<Inventory | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [scope, setScope] = useState('current')
  useEffect(() => {
    const controller = new AbortController()
    fetch('/data/artifacts.json', { signal: controller.signal }).then(async (response) => {
      const text = await response.text()
      if (!response.ok || text.trim().startsWith('<')) throw new Error('Artifact inventory unavailable')
      const value = JSON.parse(text) as Inventory
      if (value.schema_version !== '1.0' || !Array.isArray(value.artifacts) ||
          value.artifacts.some((item) => !/^\/data\/[a-zA-Z0-9_./-]+$/.test(item.url))) throw new Error('Artifact inventory is invalid')
      if (!controller.signal.aborted) setInventory(value)
    }).catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Artifact inventory unavailable') })
    return () => controller.abort()
  }, [])
  return <section className="dashboard-workspace" aria-label="Reports and downloads">
    <h2>{replay.name} · retrospective report</h2>
    <p>Final archive summary reconstructed from source timing and replay telemetry. These results have not been independently verified as official classifications. The Replay tab follows the playhead.</p>
    <div className="workspace-table-wrap"><table><thead><tr><th>Boat</th><th>Reconstructed rank</th><th>Elapsed</th><th>Distance sailed</th><th>Average SOG</th><th>Tacks / gybes</th></tr></thead><tbody>{replay.competitors.map((boat) => <tr key={boat.id}><td>{boat.team_code} · {boat.team_name}</td><td>{boat.classification.startsWith('RANK_') ? boat.summary.finish_rank : boat.classification}</td><td>{boat.summary.elapsed_s > 0 ? boat.summary.elapsed_s.toFixed(2) + ' s' : 'Unavailable: no ranked finish'}</td><td>{boat.summary.distance_sailed_m.toFixed(0)} m</td><td>{boat.summary.avg_speed_kt.toFixed(1)} kt</td><td>{boat.summary.tack_count} / {boat.summary.gybe_count}</td></tr>)}</tbody></table></div>
    <p>Replay channels: position in projected metres, heading/COG/TWA/TWD in degrees, SOG/VMG/TWS in knots, timestamps in Unix milliseconds. Historical metric formulas, windows, coverage and quality are available in Analysis and embedded in each analysis JSON. Heel, pitch, current and temperature have no measured replay channel.</p>
    <h2 id="artifact-downloads">Artifact library</h2>
    <p><a href="/data/artifacts.json" download>Download the complete artifact inventory</a></p>
    {inventory && <p>{inventory.summary.race_count} unique races · {inventory.summary.replayed_boat_races} replayed boat-races.</p>}
    <label>Downloads <select aria-label="Artifact scope" value={scope} onChange={(event) => setScope(event.target.value)}><option value="current">Current race and archive indexes</option><option value="all">All races and outputs</option><option value="global">Archive indexes</option></select></label>
    {error && <p role="alert">{error}</p>}{!inventory && !error && <p role="status">Loading artifact inventory…</p>}
    {inventory && <div className="workspace-table-wrap"><table><thead><tr><th>Output</th><th>Race / scope</th><th>View</th><th>Download</th></tr></thead><tbody>{inventory.artifacts.filter((item) => scope === 'all' || (scope === 'global' ? !item.race_id : !item.race_id || item.race_id === replay.id)).map((item) => {
      const race = catalog.find((candidate) => candidate.id === item.race_id)
      return <tr key={item.id}><td>{item.label}<small className="artifact-path">{item.id}</small></td><td>{race?.name ?? 'Archive'}</td><td>{race ? <button onClick={() => onOpenRace(race, item.view)}>{item.view}</button> : item.view}</td><td><a href={item.url} download>{item.format.toUpperCase()} · {(item.bytes / 1024).toFixed(0)} KiB</a></td></tr>
    })}</tbody></table></div>}
  </section>
}
