import type { Point, ReplayManifest } from '../../types/replay'
import { screenToWorld, worldToScreen, type Viewport } from './ViewportMatrix'

const strokePath = (context: CanvasRenderingContext2D, viewport: Viewport, points: Array<[number, number]>, close = false) => {
  context.beginPath()
  points.forEach((point, index) => {
    const [x, y] = worldToScreen(viewport, point)
    if (index === 0) context.moveTo(x, y)
    else context.lineTo(x, y)
  })
  if (close) context.closePath()
}

export function drawStaticCourse(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  _replay: ReplayManifest,
  viewport: Viewport,
  boundaries: { race: Point[]; safety: Point[] },
  options?: { showWaterSurface?: boolean }
): void {
  context.clearRect(0, 0, width, height)

  if (options?.showWaterSurface) {
    context.fillStyle = '#0a0f18'
    context.fillRect(0, 0, width, height)
  }

  // Metric 250m grid over the visible world area, including after panning.
  context.save()
  context.strokeStyle = 'rgba(128, 188, 210, 0.14)'
  context.lineWidth = 1
  const grid = 250
  const corners = [[0, 0], [width, 0], [width, height], [0, height]].map(
    ([x, y]) => screenToWorld(viewport, [x, y]),
  )
  const xMin = Math.min(...corners.map(([x]) => x))
  const xMax = Math.max(...corners.map(([x]) => x))
  const yMin = Math.min(...corners.map(([, y]) => y))
  const yMax = Math.max(...corners.map(([, y]) => y))
  for (let value = Math.ceil(xMin / grid) * grid; value <= xMax; value += grid) {
    strokePath(context, viewport, [[value, yMin], [value, yMax]])
    context.stroke()
  }
  for (let value = Math.ceil(yMin / grid) * grid; value <= yMax; value += grid) {
    strokePath(context, viewport, [[xMin, value], [xMax, value]])
    context.stroke()
  }

  // Active boundary corridor from the session timeline.
  const { race, safety } = boundaries
  if (safety && safety.length > 0) {
    strokePath(context, viewport, safety, true)
    context.strokeStyle = 'rgba(148, 163, 184, 0.55)'
    context.lineWidth = 1.0
    context.setLineDash([4, 4])
    context.stroke()
    context.setLineDash([])
  }

  if (race && race.length > 0) {
    strokePath(context, viewport, race, true)
    context.fillStyle = 'rgba(14, 165, 233, 0.06)'
    context.fill()
    context.strokeStyle = 'rgba(56, 189, 248, 0.70)'
    context.lineWidth = 1.5
    context.stroke()
  }

  context.restore()
}

