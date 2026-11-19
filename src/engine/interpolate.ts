import type { BoatFrame, BoatTelemetry } from '../types/replay'

export const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value))
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * clamp(t, 0, 1)
}

/** Interpolate a bearing along its shortest path, always returning [0, 360). */
export function angleLerp(a: number, b: number, t: number): number {
  const delta = ((b - a + 540) % 360) - 180
  return (((a + delta * clamp(t, 0, 1)) % 360) + 360) % 360
}

export function sampleBoat(
  id: string,
  data: BoatTelemetry,
  index: number,
  fraction: number
): BoatFrame {
  const next = Math.min(index + 1, data.x.length - 1)
  const linear = (values: number[]) => lerp(values[index] ?? 0, values[next] ?? 0, fraction)
  return {
    id,
    x: linear(data.x),
    y: linear(data.y),
    heading: angleLerp(data.heading[index] ?? 0, data.heading[next] ?? 0, fraction),
    cog: angleLerp(data.cog[index] ?? 0, data.cog[next] ?? 0, fraction),
    sog: linear(data.sog),
    vmg: linear(data.vmg),
    twa: linear(data.twa),
    twd: angleLerp(data.twd[index] ?? 0, data.twd[next] ?? 0, fraction),
    tws: linear(data.tws),
    progress_m: linear(data.progress_m),
    leg: Math.round(linear(data.leg)),
  }
}
