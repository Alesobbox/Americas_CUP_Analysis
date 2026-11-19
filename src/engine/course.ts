import type { Point, ReplayManifest } from '../types/replay'

export function boundaryAt(
  replay: ReplayManifest,
  timestamp: number
): { race: Point[]; safety: Point[] } {
  const timeline = replay.course.boundary_timeline
  if (!timeline?.length) return replay.course.boundaries
  let active = timeline[0]
  for (const change of timeline) {
    if (change.t > timestamp) break
    active = change
  }
  return active
}

/** Returns the active position of a mark, using dynamic frame telemetry if available. */
