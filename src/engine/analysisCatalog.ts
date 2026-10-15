import type { AnalysisDetail, AnalysisIndex, AnalysisIndexRace } from '../types/analysis'

export async function loadAnalysisIndex(signal?: AbortSignal): Promise<AnalysisIndex> {
  const response = await fetch('/data/analysis/index.json', { signal })
  if (!response.ok) throw new Error(`Analysis archive is unavailable (${response.status})`)
  if (!response.headers.get('content-type')?.includes('json')) throw new Error('Analysis archive did not return JSON')
  const index = await response.json() as AnalysisIndex
  if (index.schema_version !== '2.0' || !Array.isArray(index.races) || !Array.isArray(index.histories)) {
    throw new Error('Analysis archive has an unsupported format')
  }
  return index
}

export async function loadAnalysisDetail(race: Pick<AnalysisIndexRace, 'id' | 'analysis_file'>, signal?: AbortSignal): Promise<AnalysisDetail> {
  if (!/^analysis\/[a-zA-Z0-9_-]+\.json$/.test(race.analysis_file)) {
    throw new Error('Detailed analysis is unavailable for this race')
  }
  const response = await fetch(`/data/${race.analysis_file}`, { signal })
  if (!response.ok) throw new Error(`Detailed analysis is unavailable (${response.status})`)
  if (!response.headers.get('content-type')?.includes('json')) throw new Error('Detailed analysis did not return JSON')
  const detail = await response.json() as AnalysisDetail
  if (detail.schema_version !== '2.0' || detail.race?.id !== race.id || !Array.isArray(detail.boats) || !detail.definitions) {
    throw new Error('Detailed analysis does not match the selected race')
  }
  if (detail.event_feed && (detail.event_feed.schema_version !== '1.0' ||
    !Array.isArray(detail.event_feed.events) ||
    detail.event_feed.events.some((event) => !event.id || !Number.isFinite(event.timestamp_ms) || !event.type || !event.source || !event.quality))) {
    throw new Error('Analysis event feed has an unsupported format')
  }
  return detail
}
