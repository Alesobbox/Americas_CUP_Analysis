import type { CameraMode, Point } from '../../types/replay'

export interface Viewport { center: Point; scale: number; rotationDeg: number; width: number; height: number }

export function createViewport(width: number, height: number, center: Point, scale: number, mode: CameraMode, axisDeg: number): Viewport {
  return { center, scale, rotationDeg: mode === 'course' ? axisDeg : 0, width, height }
}

export function worldToScreen(viewport: Viewport, point: Point): Point {
  const radians = viewport.rotationDeg * Math.PI / 180; const dx = point[0] - viewport.center[0]; const dy = point[1] - viewport.center[1]
  return [viewport.width / 2 + (Math.cos(radians) * dx - Math.sin(radians) * dy) * viewport.scale, viewport.height / 2 - (Math.sin(radians) * dx + Math.cos(radians) * dy) * viewport.scale]
}

export function screenToWorld(viewport: Viewport, point: Point): Point {
  const radians = viewport.rotationDeg * Math.PI / 180; const rx = (point[0] - viewport.width / 2) / viewport.scale; const ry = -(point[1] - viewport.height / 2) / viewport.scale
  return [viewport.center[0] + Math.cos(radians) * rx + Math.sin(radians) * ry, viewport.center[1] - Math.sin(radians) * rx + Math.cos(radians) * ry]
}

export function worldVectorToScreen(viewport: Viewport, vector: Point): Point {
  const radians = viewport.rotationDeg * Math.PI / 180
  return [(Math.cos(radians) * vector[0] - Math.sin(radians) * vector[1]) * viewport.scale, -(Math.sin(radians) * vector[0] + Math.cos(radians) * vector[1]) * viewport.scale]
}

export function fitViewport(width: number, height: number, points: Point[], mode: CameraMode, axisDeg: number, padding = 1.18): Viewport {
  const xs = points.map(([x]) => x); const ys = points.map(([, y]) => y); const center: Point = [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2]
  const raw: Viewport = createViewport(width, height, center, 1, mode, axisDeg)
  const projected = points.map((point) => worldToScreen(raw, point)); const minX = Math.min(...projected.map(([x]) => x)); const maxX = Math.max(...projected.map(([x]) => x)); const minY = Math.min(...projected.map(([, y]) => y)); const maxY = Math.max(...projected.map(([, y]) => y))
  return { ...raw, scale: Math.min(width / Math.max(1, maxX - minX) / padding, height / Math.max(1, maxY - minY) / padding) }
}

/** Fit a world polygon into the visible area above a bottom overlay. */
export function fitViewportWithBottomClearance(
  width: number,
  height: number,
  points: Point[],
  mode: CameraMode,
  axisDeg: number,
  bottomClearancePx: number,
  padding = 1.2,
): Viewport {
  const clearance = Math.min(Math.max(0, bottomClearancePx), height * 0.35)
  const fitted = fitViewport(width, Math.max(1, height - clearance), points, mode, axisDeg, padding)
  const fullViewport = { ...fitted, height }
  return {
    ...fullViewport,
    center: screenToWorld(fullViewport, [width / 2, height / 2 + clearance / 2]),
  }
}
