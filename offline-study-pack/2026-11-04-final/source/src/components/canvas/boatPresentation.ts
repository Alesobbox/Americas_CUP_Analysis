import type { TrailScope } from '../../types/replay'

export interface BoatLabelAnchor { id: string; x: number; y: number; width: number; height: number; priority: number }
export interface BoatLabelPosition extends BoatLabelAnchor { left: number; top: number }
export interface LabelObstacle { left: number; top: number; width: number; height: number }
type Rect = LabelObstacle

function overlap(a: Rect, b: Rect): number {
  return Math.max(0, Math.min(a.left + a.width, b.left + b.width) - Math.max(a.left, b.left)) *
    Math.max(0, Math.min(a.top + a.height, b.top + b.height) - Math.max(a.top, b.top))
}

/** Greedy screen-space labels: vessel positions remain untouched and leader lines show their anchors. */
export function layoutBoatLabels(anchors: BoatLabelAnchor[], width: number, height: number, courseLabels: LabelObstacle[] = []): BoatLabelPosition[] {
  if (!anchors.length) return []
  const inset = 8
  const placed: BoatLabelPosition[] = []
  const reserve: Rect = { left: 0, top: height - 112, width: Math.min(320, width * .72), height: 112 }
  const ordered = [...anchors].sort((a, b) => a.priority - b.priority || a.id.localeCompare(b.id))
  for (const anchor of ordered) {
    const w = Math.min(anchor.width, width - inset * 2), h = anchor.height
    const candidates: Array<[number, number]> = []
    for (const distance of [22, 54, 90, 130, 170]) {
      for (const [dx, dy] of [[1, -1], [-1, -1], [1, 1], [-1, 1], [0, -1], [0, 1], [1, 0], [-1, 0]]) {
        candidates.push([anchor.x + dx * distance - (dx < 0 ? w : dx === 0 ? w / 2 : 0), anchor.y + dy * distance - (dy < 0 ? h : dy === 0 ? h / 2 : 0)])
      }
    }
    for (let top = inset; top + h <= height - inset; top += h + 6) {
      candidates.push([inset, top], [width - w - inset, top])
    }
    let best: Rect = { left: inset, top: inset, width: w, height: h }, bestCost = Infinity
    for (const [left, top] of candidates) {
      const candidate = { left: Math.max(inset, Math.min(width - w - inset, left)), top: Math.max(inset, Math.min(height - h - inset, top)), width: w, height: h }
      const obstacles = placed.reduce((sum, label) => sum + overlap(candidate, { left: label.left - 3, top: label.top - 3, width: label.width + 6, height: label.height + 6 }), 0)
      const coveredVessels = anchors.filter((point) => point.x > candidate.left - 14 && point.x < candidate.left + w + 14 && point.y > candidate.top - 14 && point.y < candidate.top + h + 14).length
      const distance = Math.hypot(candidate.left + w / 2 - anchor.x, candidate.top + h / 2 - anchor.y)
      const courseOverlap = courseLabels.reduce((sum, label) => sum + overlap(candidate, label), 0)
      const cost = obstacles * 1000000 + courseOverlap * 1000 + overlap(candidate, reserve) * 10 + coveredVessels * 100000 + distance
      if (cost < bestCost) { bestCost = cost; best = candidate }
    }
    placed.push({ ...anchor, ...best })
  }
  // Extremely tight fleets can exhaust the greedy ring positions. A pair of
  // label columns remains unambiguous; only labels move, never boat geometry.
  const w = Math.min(Math.max(...ordered.map((a) => a.width)), width - inset * 2)
  const h = Math.max(...ordered.map((a) => a.height))
  const columns = Math.max(1, Math.floor((width - inset * 2 + 6) / (w + 6)))
  const rows = Math.ceil(ordered.length / columns)
  const gridHeight = rows * h + (rows - 1) * 6
  const crowded = placed.some((a, index) => placed.some((b, other) => index !== other && overlap(a, b) > 0))
  const underHud = placed.some((label) => overlap(label, reserve) > 0)
  if (!crowded && (!underHud || gridHeight > height - 112 - inset * 2)) return placed
  const top = Math.max(inset, Math.min(height - gridHeight - inset, (height - 112 - gridHeight) / 2))
  const slots = Array.from({ length: rows * columns }, (_, index) => ({ left: columns === 1 ? (width - w) / 2 : inset + (index % columns) * (width - inset * 2 - w) / (columns - 1), top: top + Math.floor(index / columns) * (h + 6), width: w, height: h }))
  return ordered.map((anchor) => {
    const cost = (slot: Rect) => Math.hypot(slot.left + w / 2 - anchor.x, slot.top + h / 2 - anchor.y) + overlap(slot, reserve) * 10 + courseLabels.reduce((sum, label) => sum + overlap(slot, label), 0) * 1000
    slots.sort((a, b) => cost(a) - cost(b))
    return { ...anchor, ...slots.shift()! }
  })
}

/** Trail scope never filters the actual fleet or changes contact geometry. */
export function trailBoatIds(ids: string[], scope: TrailScope, highlightedIds: string[]): string[] {
  if (scope === 'none') return []
  return scope === 'highlighted' ? ids.filter((id) => highlightedIds.includes(id)) : ids
}
