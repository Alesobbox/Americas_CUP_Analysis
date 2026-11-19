import { describe, expect, it } from 'vitest'
import { layoutBoatLabels, trailBoatIds } from './boatPresentation'

describe('boat visibility presentation', () => {
  it.each([
    [727, 360],
    [358, 320],
  ])('declutters a nine-boat cluster inside a %s × %s viewport', (width, height) => {
    const points = Array.from({ length: 9 }, (_, i) => ({
      id: String(i),
      x: width / 2 + i * 3,
      y: height / 2 + i,
      width: 116,
      height: 44,
      priority: i < 2 ? i : 2,
    }))
    const labels = layoutBoatLabels(points, width, height)
    expect(labels).toHaveLength(9)
    for (const label of labels) {
      expect(label.left).toBeGreaterThanOrEqual(8)
      expect(label.top).toBeGreaterThanOrEqual(8)
      expect(label.left + label.width).toBeLessThanOrEqual(width - 8)
      expect(label.top + label.height).toBeLessThanOrEqual(height - 8)
      expect([label.x, label.y]).toEqual([points[Number(label.id)].x, points[Number(label.id)].y])
      for (const other of labels.filter((candidate) => candidate.id !== label.id)) {
        const overlaps =
          label.left < other.left + other.width &&
          label.left + label.width > other.left &&
          label.top < other.top + other.height &&
          label.top + label.height > other.top
        expect(overlaps, `${label.id} overlaps ${other.id}`).toBe(false)
      }
    }
  })
  it('keeps readable boat labels clear of course badges when space is available', () => {
    const badge = { left: 270, top: 135, width: 136, height: 28 }
    const anchors = Array.from({ length: 4 }, (_, i) => ({
      id: String(i),
      x: 330 + i * 3,
      y: 185,
      width: 116,
      height: 44,
      priority: i,
    }))
    for (const label of layoutBoatLabels(anchors, 727, 380, [badge])) {
      expect(
        label.left < badge.left + badge.width &&
          label.left + label.width > badge.left &&
          label.top < badge.top + badge.height &&
          label.top + label.height > badge.top
      ).toBe(false)
    }
  })
  it('filters trails independently, including explicit A/B without duplicating a boat', () => {
    const ids = ['a', 'b', 'c']
    expect(trailBoatIds(ids, 'all', ['a', 'b'])).toEqual(ids)
    expect(trailBoatIds(ids, 'highlighted', ['a', 'b', 'a'])).toEqual(['a', 'b'])
    expect(trailBoatIds(ids, 'highlighted', ['absent'])).toEqual([])
    expect(trailBoatIds(ids, 'none', ['a', 'b'])).toEqual([])
    expect(ids).toEqual(['a', 'b', 'c'])
  })
})
