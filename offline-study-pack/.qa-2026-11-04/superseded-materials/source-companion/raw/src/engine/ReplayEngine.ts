import { clamp, lerp, sampleBoat } from './interpolate'
import type { PlaybackSpeed, ReplayFrame, ReplayManifest } from '../types/replay'

type Subscriber = (frame: ReplayFrame) => void

const UUID_TO_MARK: Record<string, string> = {
  '3e0be123-6ef5-4485-8b35-19e84cb4d8dd': 'RM1',
  'e018121d-b03e-4be7-9998-2a000135a599': 'RM2',
  'd72957d4-4eb3-41ef-9a51-5983a906aa8b': 'RM3',
  'a392c0a6-582e-41a6-905e-0e490f3a27b1': 'RM4',
  'e0b1111d-3274-475a-a5be-97e1501d58f2': 'RM5',
  'c35b7718-40e5-4a9d-a4e6-934d18ecfa2a': 'RM6',
  'b001c19e-b70b-484f-947b-4841d7a4842e': 'RM7',
  '026f70b1-9ecb-479d-b03c-085e40fd166d': 'RM8',
}

export function sampleMark(data: { x: number[]; y: number[] }, index: number, fraction: number): { x: number; y: number } {
  const next = Math.min(index + 1, data.x.length - 1)
  return {
    x: lerp(data.x[index] ?? 0, data.x[next] ?? 0, fraction),
    y: lerp(data.y[index] ?? 0, data.y[next] ?? 0, fraction),
  }
}

/** Browser-clock adapter that samples the compact telemetry timeline at display cadence. */
export class ReplayEngine {
  private readonly start: number; private readonly end: number; private time: number; private speed: PlaybackSpeed = 1; private playing = false; private rafId: number | null = null; private previousWallTime: number | null = null; private readonly subscribers = new Set<Subscriber>()
  constructor(private readonly replay: ReplayManifest) { this.start = replay.chronology.window_start; this.end = replay.chronology.window_end; this.time = this.start }
  subscribe(subscriber: Subscriber): () => void { this.subscribers.add(subscriber); subscriber(this.frame()); return () => this.subscribers.delete(subscriber) }
  play(): void { if (!this.playing) { this.playing = true; this.previousWallTime = null; this.schedule() } }
  pause(): void { this.playing = false; this.previousWallTime = null; if (this.rafId !== null) cancelAnimationFrame(this.rafId); this.rafId = null }
  toggle(): void { this.playing ? this.pause() : this.play() }
  isPlaying(): boolean { return this.playing }; getTime(): number { return this.time }; getSpeed(): PlaybackSpeed { return this.speed }; setSpeed(speed: PlaybackSpeed): void { this.speed = speed }
  seek(timestamp: number): void { this.time = clamp(timestamp, this.start, this.end); this.emit() }; seekBy(seconds: number): void { this.seek(this.time + seconds * 1000) }; dispose(): void { this.pause(); this.subscribers.clear() }
  private schedule(): void { this.rafId = requestAnimationFrame((wallTime) => this.tick(wallTime)) }
  private tick(wallTime: number): void { if (!this.playing) return; if (this.previousWallTime !== null) this.time = Math.min(this.end, this.time + (wallTime - this.previousWallTime) * this.speed); this.previousWallTime = wallTime; if (this.time >= this.end) { this.pause(); this.emit(); return }; this.emit(); this.schedule() }
  private frame(): ReplayFrame {
    const times = this.replay.telemetry.timestamps
    let index = 0
    let fraction = 0
    if (times.length > 0) {
      let lower = 0
      let upper = times.length - 1
      while (lower < upper) {
        const middle = Math.ceil((lower + upper) / 2)
        if (times[middle] <= this.time) lower = middle
        else upper = middle - 1
      }
      index = lower
      const nextTime = times[Math.min(index + 1, times.length - 1)]
      fraction = nextTime === times[index] ? 0 : clamp((this.time - times[index]) / (nextTime - times[index]), 0, 1)
    }
    const boats = Object.fromEntries(Object.entries(this.replay.telemetry.boats).map(([id, boat]) => [id, sampleBoat(id, boat, index, fraction)]))

    const marks: Record<string, { x: number; y: number }> = {}
    const telemetryMarks = this.replay.telemetry.marks || {}
    const dynamicUuidToMark: Record<string, string> = { ...UUID_TO_MARK }
    if (this.replay.course?.marks) {
      for (const [code, mark] of Object.entries(this.replay.course.marks)) {
        if (mark.asset_id) {
          dynamicUuidToMark[mark.asset_id] = code
        }
        const assetId = mark.asset_id
        const markData = telemetryMarks[code] ?? (assetId ? telemetryMarks[assetId] : undefined)
        if (markData) {
          marks[code] = sampleMark(markData, index, fraction)
        } else if (mark.target) {
          marks[code] = { x: mark.target[0], y: mark.target[1] }
        }
      }
    }
    for (const [key, stream] of Object.entries(telemetryMarks)) {
      const code = dynamicUuidToMark[key] ?? (key.startsWith('RM') ? key : undefined)
      if (code && !marks[code]) {
        marks[code] = sampleMark(stream, index, fraction)
      }
      if (!marks[key]) {
        marks[key] = sampleMark(stream, index, fraction)
      }
    }

    return { timestamp: this.time, index, fraction, boats, marks }
  }
  private emit(): void { const frame = this.frame(); this.subscribers.forEach((subscriber) => subscriber(frame)) }
}
