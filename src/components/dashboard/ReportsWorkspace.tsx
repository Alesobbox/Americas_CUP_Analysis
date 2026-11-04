import { evidenceText } from '../../utils/evidenceText'
import { useEffect, useState } from 'react'
import type { RaceListing } from '../../engine/catalog'
import type { AnalysisDetail, AnalysisMetric } from '../../types/analysis'
import type { ReplayManifest } from '../../types/replay'
import './reports.css'

export interface Artifact {
  id: string; url: string; race_id: string | null; label: string; view: string; bytes: number; format: string
  kind?: string; status?: 'current' | 'supporting' | 'retained'; scope?: 'race' | 'archive'; primary_download?: boolean
}
interface Inventory { schema_version: '1.0' | '1.1'; summary: { race_count: number; replayed_boat_races: number }; artifacts: Artifact[] }
export const primaryDownloads = (items: Artifact[], raceId: string) => items.filter((item) => item.race_id === raceId && item.primary_download && item.status === 'current')
export function technicalDownloads(items: Artifact[], raceId: string, scope: string, search: string): Artifact[] {
  const query = search.trim().toLocaleLowerCase()
  return items.filter((item) => (scope === 'all' || (scope === 'current' ? item.race_id === raceId && item.status !== 'retained' : scope === 'catalogs' ? item.kind === 'catalog' : item.status === scope)) &&
    (!query || `${item.label} ${item.id} ${item.race_id ?? ''} ${item.kind ?? ''}`.toLocaleLowerCase().includes(query)))
}
function ReportMetric({ metric }: { metric?: AnalysisMetric }) {
  if (!metric || metric.value === null) return <><span>Unavailable</span><small>{evidenceText(metric?.reason ?? 'No canonical racing value')}</small></>
  const digits = metric.unit === 'events' ? 0 : 2
  return <><span>{metric.value.toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits })} {metric.unit}</span><small>{evidenceText(metric.quality)}{metric.coverage_s === null ? '' : ` · ${metric.coverage_s.toFixed(1)} s covered`}{metric.reason ? ` · ${evidenceText(metric.reason)}` : ''}</small></>
}
function ReportCell({ id, metric }: { id: string; metric?: AnalysisMetric }) {
  return <td data-metric-id={id} data-value={metric?.value ?? ''} data-quality={metric?.quality ?? 'unavailable'}><ReportMetric metric={metric} /></td>
}
const downloadDescriptions: Record<string, string> = {
  analysis: 'Metrics, definitions, coverage and supporting evidence.',
  performance_csv: 'Boat and leg comparisons, ready for a spreadsheet.',
  summary_csv: 'Canonical race metrics for the complete field.',
  environment: 'Historical sea and temperature model estimates.',
  forecast: 'Published race forecasts and model references.',
  replay: 'Synchronized positions and recorded telemetry.',
}
export function ReportsWorkspace({ replay, analysisDetail, catalog, onOpenRace }: {
  replay: ReplayManifest; analysisDetail: AnalysisDetail | null; catalog: RaceListing[]
  onOpenRace: (race: RaceListing, view: string) => void
}) {
  const [inventory, setInventory] = useState<Inventory | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [scope, setScope] = useState('current')
  const [search, setSearch] = useState('')
  const detail = analysisDetail?.race.id === replay.id ? analysisDetail : null
  useEffect(() => {
    const controller = new AbortController()
    fetch('/data/artifacts.json', { signal: controller.signal }).then(async (response) => {
      if (!response.ok || !response.headers.get('content-type')?.includes('json')) throw new Error('Download catalog is unavailable')
      const value = await response.json() as Inventory
      if (!['1.0', '1.1'].includes(value.schema_version) || !Array.isArray(value.artifacts) || !value.summary ||
          !Number.isInteger(value.summary.race_count) || !Number.isInteger(value.summary.replayed_boat_races) ||
          value.artifacts.some((item) => !/^\/data\/[a-zA-Z0-9_./-]+$/.test(item.url) || item.url.split('/').includes('..') ||
            !item.id || !item.label || !item.view || !Number.isFinite(item.bytes) || item.bytes <= 0 ||
            (value.schema_version === '1.1' && (!item.kind || !['current', 'supporting', 'retained'].includes(item.status ?? '') || typeof item.primary_download !== 'boolean')))) throw new Error('Download catalog has an unsupported format')
      if (!controller.signal.aborted) setInventory(value)
    }).catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Download catalog is unavailable') })
    return () => controller.abort()
  }, [])
  useEffect(() => { setScope('current'); setSearch('') }, [replay.id])
  const primary = primaryDownloads(inventory?.artifacts ?? [], replay.id)
  const technical = technicalDownloads(inventory?.artifacts ?? [], replay.id, scope, search)
  return <section className="dashboard-workspace reports-workspace" aria-label="Reports and downloads">
    <div className="reports-heading"><div><h2>{replay.name} · race report</h2><p>Historical racing metrics and the files behind them.</p></div><span className="reports-race-meta">{[replay.venue, replay.date].filter(Boolean).join(' · ')}</span></div>
    <p className="reports-evidence-note">Results and crossing times are calculated from recorded telemetry. Finishing classifications have not been independently verified.</p>
    {!detail && <p role="status">Historical analysis is unavailable or still loading. Racing metrics remain unavailable until the matching analysis is loaded.</p>}
    <div className="workspace-table-wrap"><table aria-label="Race report metrics"><thead><tr><th>Boat</th><th>Result</th><th>Elapsed</th><th>Distance sailed</th><th>Mean SOG</th><th>Tacks</th><th>Gybes</th></tr></thead><tbody>{replay.competitors.map((boat) => {
      const canonical = detail?.boats.find((candidate) => candidate.id === boat.id)
      return <tr key={boat.id} data-boat-id={boat.id}><th scope="row"><span className="report-boat-identity"><span className="report-team-marker" style={{ backgroundColor: boat.color }} aria-hidden="true" /><span><strong>{boat.team_code}</strong><span className="report-team-name">{boat.team_name}</span></span></span>{canonical?.source_conflicts?.map((conflict) => <small className="report-source-conflict" key={conflict}>{evidenceText(conflict)}</small>)}</th><td>{canonical ? canonical.official_rank === null ? canonical.classification : `#${canonical.official_rank}` : 'Unavailable'}</td><td>{canonical?.official_elapsed_s == null ? 'Unavailable: no ranked finish' : `${canonical.official_elapsed_s.toFixed(2)} s`}</td><ReportCell id="distance_m" metric={canonical?.metrics.distance_m} /><ReportCell id="sog_mean_kt" metric={canonical?.metrics.sog_mean_kt} /><ReportCell id="tack_count" metric={canonical?.metrics.tack_count} /><ReportCell id="gybe_count" metric={canonical?.metrics.gybe_count} /></tr>
    })}</tbody></table></div>
    <p className="report-table-footnote">Partial values cover only the exported valid racing intervals. Open Analysis for the formula, leg coverage and supporting events; missing intervals remain unavailable.</p>
    <section className="race-exports" aria-label="Race exports"><div className="race-exports-heading"><h3>Race exports</h3><p>Spreadsheet-ready metrics and source files.</p></div>
      {error && <p role="alert">{error}</p>}{!inventory && !error && <p role="status">Loading race downloads…</p>}
      <div className="race-export-grid">{primary.map((item) => <a key={item.id} href={item.url} download data-download-kind={item.kind}><span className="export-file-type">{item.format.toUpperCase()}</span><span className="export-description"><strong>{item.label}</strong><span>{downloadDescriptions[item.kind ?? ''] ?? 'Published source file for this race.'}</span></span><span className="export-file-size">{(item.bytes / 1024).toFixed(0)} KiB</span><span className="export-download-action">Download <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M5 16v4h14v-4" strokeLinecap="round" strokeLinejoin="round" /></svg></span></a>)}</div>
      {inventory && !primary.length && <p>Curated race downloads are unavailable in this catalog. All published files remain available in Technical data and provenance.</p>}
    </section>
    <details className="technical-data"><summary>Technical data and provenance</summary>
      <p>Complete, reproducible data, model evidence and retained versions. Retained forecasts remain available for older references.</p><p><a href="/data/artifacts.json" download>Download the complete artifact inventory</a></p>
      {inventory && <p>{inventory.summary.race_count} unique races · {inventory.summary.replayed_boat_races} replayed boat-races · {inventory.artifacts.length} published files.</p>}
      <div className="technical-data-controls"><label>Scope <select aria-label="Technical data scope" value={scope} onChange={(event) => setScope(event.target.value)}><option value="current">Current race</option><option value="catalogs">Archive catalogs</option><option value="supporting">Supporting evidence</option><option value="retained">Retained versions</option><option value="all">All published files</option></select></label><label>Search <input type="search" aria-label="Search technical data" value={search} onChange={(event) => setSearch(event.target.value)} /></label></div>
      {inventory && <><p role="status" aria-live="polite">{technical.length} matching files.</p>{!technical.length && <p className="technical-data-empty">No published files match this search. Try another name or choose a wider scope.</p>}<div className="workspace-table-wrap"><table aria-label="Technical downloads"><thead><tr><th>Output</th><th>Race / scope</th><th>Status</th><th>Open</th><th>Download</th></tr></thead><tbody>{technical.map((item) => {
        const race = catalog.find((candidate) => candidate.id === item.race_id)
        return <tr key={item.id}><td>{item.label}<details><summary>File reference</summary><code className="artifact-path">{item.id}</code></details></td><td>{race?.name ?? 'Archive'}</td><td>{item.status ?? 'Unclassified'}</td><td>{race ? <button onClick={() => onOpenRace(race, item.view)}>{item.view}</button> : item.view}</td><td><a href={item.url} download>{item.format.toUpperCase()} · {(item.bytes / 1024).toFixed(0)} KiB</a></td></tr>
      })}</tbody></table></div></>}
      <details><summary>Source channels</summary><p>Replay positions use projected metres; heading, COG, TWA and TWD use degrees; SOG, VMG and TWS use knots. Heel, pitch and current have no measured replay channel. Historical sea and temperature estimates are separate contextual sources.</p></details>
    </details>
  </section>
}
