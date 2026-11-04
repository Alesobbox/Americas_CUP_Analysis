import { useEffect, useMemo, useRef, useState } from 'react'
import { Map as MapLibreMap, setWorkerUrl } from 'maplibre-gl'
import mapWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { BoatScaleMode, CameraMode, FollowMode, Point, ReplayFrame, ReplayManifest, TrailColor, TrailLength, TrailScope, ViewMode } from '../../types/replay'
import { drawDynamicVessels } from './DynamicVesselLayer'
import { layoutBoatLabels, type LabelObstacle } from './boatPresentation'
import { drawStaticCourse } from './StaticCourseLayer'
import { boundaryAt } from '../../engine/course'
import { createViewport, fitViewport, fitViewportWithBottomClearance, screenToWorld, worldToScreen, type Viewport } from './ViewportMatrix'
import { createMaritimeMapStyle } from './mapStyle'
import {
  computeAffineScreenTransform,
  lngLatToMetric,
  metricToLngLat,
} from '../../utils/geoProjection'

setWorkerUrl(mapWorkerUrl)

interface CourseCanvasProps {
  replay: ReplayManifest
  frame: ReplayFrame
  cameraMode: CameraMode
  followMode: FollowMode
  selectedId: string | null
  comparisonId: string | null
  resetView: number
  trailLength: TrailLength
  trailColor: TrailColor
  showSafetyBorders?: boolean
  viewMode: ViewMode
  scaleMode: BoatScaleMode
  trailScope?: TrailScope
  showVmgLabels?: boolean
  highlightComparison?: boolean
  onSelectBoat: (id: string) => void
  visibleBoatId?: string | null
  zoomInTrigger?: number
  zoomOutTrigger?: number
}

interface DragState {
  point: [number, number]
  lastPoint: [number, number]
  viewport: Viewport
  moved: boolean
}

function isWebGLSupported(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const canvas = document.createElement('canvas')
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    )
  } catch {
    return false
  }
}

function sizeCanvas(canvas: HTMLCanvasElement, width: number, height: number) {
  const ratio = window.devicePixelRatio || 1
  canvas.width = Math.max(1, Math.round(width * ratio))
  canvas.height = Math.max(1, Math.round(height * ratio))
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  canvas.getContext('2d')?.setTransform(ratio, 0, 0, ratio, 0, 0)
}

const TOOLBELT_CLEARANCE_PX = 140

function fitMapToPoints(
  map: MapLibreMap,
  points: Point[],
  replay: ReplayManifest,
  targetBearing: number
) {
  if (!points || !points.length) return
  const lngLats = points.map(([x, y]) =>
    metricToLngLat(x, y, replay.course.origin, replay.course.projection)
  )
  const minLng = Math.min(...lngLats.map(([lng]) => lng))
  const maxLng = Math.max(...lngLats.map(([lng]) => lng))
  const minLat = Math.min(...lngLats.map(([, lat]) => lat))
  const maxLat = Math.max(...lngLats.map(([, lat]) => lat))

  map.fitBounds(
    [
      [minLng, minLat],
      [maxLng, maxLat],
    ],
    {
      padding: { top: 48, bottom: TOOLBELT_CLEARANCE_PX, left: 48, right: 48 },
      bearing: targetBearing,
      maxZoom: 16.5,
      duration: 600,
    }
  )
}

export function CourseCanvas({
  replay,
  frame,
  cameraMode,
  followMode,
  selectedId,
  comparisonId,
  resetView,
  trailLength,
  trailColor,
  showSafetyBorders = false,
  viewMode,
  scaleMode,
  trailScope = 'all',
  showVmgLabels = true,
  highlightComparison = false,
  onSelectBoat,
  visibleBoatId = null,
  zoomInTrigger,
  zoomOutTrigger,
}: CourseCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const staticRef = useRef<HTMLCanvasElement>(null)
  const dynamicRef = useRef<HTMLCanvasElement>(null)
  const dragRef = useRef<DragState | null>(null)
  const suppressClickRef = useRef(false)

  const [isFallback, setIsFallback] = useState(() => !isWebGLSupported())
  const [isOfflineFallback, setIsOfflineFallback] = useState(false)
  const [size, setSize] = useState({ width: 900, height: 620 })
  const [viewport, setViewport] = useState<Viewport>(() =>
    createViewport(900, 620, [0, 0], 0.2, cameraMode, replay.course.axis_deg)
  )
  const viewportRef = useRef<Viewport>(viewport)
  useEffect(() => {
    viewportRef.current = viewport
  }, [viewport])
  const initialFitDoneRef = useRef(false)

  const boundaries = boundaryAt(replay, frame.timestamp)
  const mapIsActive = viewMode === 'map' && !isFallback

  // 1. Container Resize Observer
  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const resize = () => {
      const width = Math.max(1, container.clientWidth)
      const height = Math.max(1, container.clientHeight)
      setSize({ width, height })
      if (mapRef.current) {
        mapRef.current.resize()
      }
    }
    resize()
    const observer = new ResizeObserver(resize)
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  // 2. Canvas Device Pixel Ratio sizing
  useEffect(() => {
    if (staticRef.current) sizeCanvas(staticRef.current, size.width, size.height)
    if (dynamicRef.current) sizeCanvas(dynamicRef.current, size.width, size.height)
  }, [size.width, size.height])

  // 3. MapLibre GL JS Lifecycle & Camera Authority
  useEffect(() => {
    if (!mapIsActive) return
    const mapContainer = mapContainerRef.current
    if (!mapContainer) return

    try {
      const cameraOnEntry = initialFitDoneRef.current ? viewportRef.current : null
      const initialCenter = cameraOnEntry
        ? metricToLngLat(cameraOnEntry.center[0], cameraOnEntry.center[1], replay.course.origin, replay.course.projection)
        : metricToLngLat(0, 0, replay.course.origin, replay.course.projection)
      const initialBearing = cameraOnEntry
        ? cameraOnEntry.rotationDeg
        : (cameraMode === 'course' ? replay.course.axis_deg : 0)

      const map = new MapLibreMap({
        container: mapContainer,
        style: createMaritimeMapStyle(),
        center: initialCenter,
        zoom: 13.2,
        bearing: initialBearing,
        pitch: 0,
        attributionControl: false,
        dragPan: false,
        scrollZoom: false,
        doubleClickZoom: false,
        boxZoom: false,
      })

      mapRef.current = map
      if (cameraOnEntry) {
        // Match the actual pixels-per-metre scale, including Grid zoom changes.
        // A map zoom cached before Grid cannot represent that current camera.
        const transform = computeAffineScreenTransform((ll) => map.project(ll), replay.course.origin, replay.course.projection)
        map.setZoom(map.getZoom() + Math.log2(cameraOnEntry.scale / transform.scale))
      }
      setIsOfflineFallback(false)

      const syncCameraFromMap = () => {
        try {
          const transform = computeAffineScreenTransform(
            (ll) => map.project(ll),
            replay.course.origin,
            replay.course.projection
          )
          const centerLngLat = map.getCenter()
          const centerMetric = lngLatToMetric(
            centerLngLat.lng,
            centerLngLat.lat,
            replay.course.origin,
            replay.course.projection
          )
          const bearing = map.getBearing()
          const w = mapContainer.clientWidth || size.width
          const h = mapContainer.clientHeight || size.height

          setViewport({
            center: centerMetric,
            scale: transform.scale,
            rotationDeg: bearing,
            width: w,
            height: h,
          })

          if (typeof window !== 'undefined') {
            window.dispatchEvent(
              new CustomEvent('regatta:bearing', { detail: { bearing } })
            )
          }
        } catch (err) {
          console.warn('MapLibre transform synchronization warning:', err)
        }
      }

      map.on('load', () => {
        syncCameraFromMap()
        if (!cameraOnEntry && !initialFitDoneRef.current) {
          initialFitDoneRef.current = true
          const fitPoints = boundaries.race.length ? boundaries.race : replay.course.boundaries.race
          fitMapToPoints(map, fitPoints, replay, initialBearing)
        }
      })

      map.on('move', syncCameraFromMap)
      map.on('rotate', syncCameraFromMap)
      map.on('resize', syncCameraFromMap)

      map.on('error', (e: unknown) => {
        const errorObj = e as { sourceId?: string; error?: { message?: string } }
        if (
          errorObj.sourceId === 'osm-raster-source' ||
          (errorObj.error?.message && errorObj.error.message.includes('tile'))
        ) {
          setIsOfflineFallback(true)
        }
      })
    } catch (err) {
      console.warn('MapLibre GL failed to initialize, switching to fallback:', err)
      setIsFallback(true)
    }

    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
      }
    }
  }, [mapIsActive, replay.id, replay.course.origin.lat, replay.course.origin.lon])

  // 4. Smooth bearing animation on cameraMode change
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapIsActive) return
    const targetBearing = cameraMode === 'course' ? replay.course.axis_deg : 0
    if (Math.abs(map.getBearing() - targetBearing) > 0.05) {
      map.easeTo({ bearing: targetBearing, duration: 600 })
    }
  }, [cameraMode, mapIsActive, replay.course.axis_deg])

  const handleResetView = () => {
    const fitPoints = boundaries.race.length ? boundaries.race : replay.course.boundaries.race
    const targetBearing = cameraMode === 'course' ? replay.course.axis_deg : 0
    if (mapRef.current && mapIsActive) {
      fitMapToPoints(mapRef.current, fitPoints, replay, targetBearing)
    } else {
      setViewport(fitViewportWithBottomClearance(size.width, size.height, fitPoints, cameraMode, replay.course.axis_deg, TOOLBELT_CLEARANCE_PX))
    }
  }

  // 5. Course reset & initial fitting
  useEffect(() => {
    initialFitDoneRef.current = true
    handleResetView()
  }, [cameraMode, replay, resetView, size.width, size.height])

  // 6. Follow Modes (Course, Fleet, Boat)
  useEffect(() => {
    if (followMode === 'course' || dragRef.current) return
    if (followMode === 'boat' && selectedId && frame.boats[selectedId]) {
      const boat = frame.boats[selectedId]
      if (mapRef.current && mapIsActive) {
        const [lng, lat] = metricToLngLat(boat.x, boat.y, replay.course.origin, replay.course.projection)
        mapRef.current.setCenter([lng, lat])
      } else {
        setViewport((current) => ({ ...current, center: [boat.x, boat.y], scale: Math.max(current.scale, 0.43) }))
      }
    } else if (followMode === 'fleet') {
      const points: Array<[number, number]> = Object.values(frame.boats).map((b) => [b.x, b.y])
      if (!points.length) return
      if (mapRef.current && mapIsActive) {
        const xs = points.map(([x]) => x)
        const ys = points.map(([, y]) => y)
        const centerMetric: Point = [
          (Math.min(...xs) + Math.max(...xs)) / 2,
          (Math.min(...ys) + Math.max(...ys)) / 2,
        ]
        const [lng, lat] = metricToLngLat(
          centerMetric[0],
          centerMetric[1],
          replay.course.origin,
          replay.course.projection
        )
        mapRef.current.setCenter([lng, lat])
      } else {
        const fitted = fitViewport(size.width, size.height, points, cameraMode, replay.course.axis_deg, 1.9)
        setViewport((current) => ({ ...fitted, scale: Math.min(current.scale, fitted.scale) }))
      }
    }
  }, [cameraMode, followMode, frame, mapIsActive, replay, selectedId])

  // 6b. Interactive HUD Zoom Controls
  const prevZoomInRef = useRef(zoomInTrigger ?? 0)
  useEffect(() => {
    if (typeof zoomInTrigger === 'number' && zoomInTrigger > prevZoomInRef.current) {
      prevZoomInRef.current = zoomInTrigger
      if (mapRef.current && mapIsActive) {
        mapRef.current.easeTo({ zoom: mapRef.current.getZoom() + 0.4, duration: 160 })
      } else {
        setViewport((current) => ({
          ...current,
          scale: Math.min(5.0, current.scale * 1.25),
        }))
      }
    }
  }, [zoomInTrigger, mapIsActive])

  const prevZoomOutRef = useRef(zoomOutTrigger ?? 0)
  useEffect(() => {
    if (typeof zoomOutTrigger === 'number' && zoomOutTrigger > prevZoomOutRef.current) {
      prevZoomOutRef.current = zoomOutTrigger
      if (mapRef.current && mapIsActive) {
        mapRef.current.easeTo({ zoom: mapRef.current.getZoom() - 0.4, duration: 160 })
      } else {
        setViewport((current) => ({
          ...current,
          scale: Math.max(0.03, current.scale / 1.25),
        }))
      }
    }
  }, [zoomOutTrigger, mapIsActive])

  // 7. Static layer: transparent over map tiles, opaque technical surface in Grid View.
  useEffect(() => {
    const context = staticRef.current?.getContext('2d')
    if (!context) return
    const showWaterSurface = viewMode === 'grid' || !mapIsActive || isOfflineFallback
    drawStaticCourse(context, size.width, size.height, replay, viewport, boundaries, { showWaterSurface })
  }, [boundaries, isOfflineFallback, mapIsActive, replay, size.height, size.width, viewMode, viewport])

  // 8. 60 FPS Dynamic tactical overlay rendering
  useEffect(() => {
    const context = dynamicRef.current?.getContext('2d')
    if (context) {
      drawDynamicVessels(
        context,
        size.width,
        size.height,
        replay,
        frame,
        viewport,
        trailLength,
        trailColor,
        selectedId,
        comparisonId,
        showSafetyBorders,
        scaleMode,
        visibleBoatId,
        { trailScope, highlightedIds: [selectedId, highlightComparison ? comparisonId : null].filter((id): id is string => !!id), drawCallouts: false },
      )
    }
  }, [comparisonId, highlightComparison, trailScope, frame, replay, scaleMode, selectedId, showSafetyBorders, size.height, size.width, trailColor, trailLength, viewport, visibleBoatId])

  // 9. Pointer interactions
  const localPoint = (event: React.PointerEvent<HTMLCanvasElement>): [number, number] => {
    const rect = event.currentTarget.getBoundingClientRect()
    return [event.clientX - rect.left, event.clientY - rect.top]
  }

  const pointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const pt = localPoint(event)
    dragRef.current = { point: pt, lastPoint: pt, viewport, moved: false }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const pointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current
    if (!drag) return
    const pt = localPoint(event)
    const dx = pt[0] - drag.lastPoint[0]
    const dy = pt[1] - drag.lastPoint[1]

    if (Math.hypot(pt[0] - drag.point[0], pt[1] - drag.point[1]) > 3) {
      drag.moved = true
    }
    drag.lastPoint = pt

    if (mapRef.current && mapIsActive) {
      mapRef.current.panBy([-dx, -dy], { animate: false })
    } else {
      const before = screenToWorld(drag.viewport, drag.point)
      const after = screenToWorld(drag.viewport, pt)
      setViewport({
        ...drag.viewport,
        center: [
          drag.viewport.center[0] + before[0] - after[0],
          drag.viewport.center[1] + before[1] - after[1],
        ],
      })
    }
  }

  const pointerUp = () => {
    suppressClickRef.current = dragRef.current?.moved ?? false
    dragRef.current = null
  }

  const wheel = (event: React.WheelEvent<HTMLCanvasElement>) => {
    event.preventDefault()
    if (mapRef.current && mapIsActive) {
      const delta = event.deltaY < 0 ? 0.25 : -0.25
      mapRef.current.easeTo({ zoom: mapRef.current.getZoom() + delta, duration: 120 })
    } else {
      setViewport((current) => {
        const factor = event.deltaY < 0 ? 1.20 : 1 / 1.20
        const newScale = Math.min(5.0, Math.max(0.03, current.scale * factor))
        return {
          ...current,
          scale: newScale,
        }
      })
    }
  }

  const chooseBoat = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (suppressClickRef.current) {
      suppressClickRef.current = false
      return
    }
    const rect = event.currentTarget.getBoundingClientRect()
    const world = screenToWorld(viewport, [event.clientX - rect.left, event.clientY - rect.top])
    let closestId: string | null = null
    let closestDistance = Infinity
    for (const boat of Object.values(frame.boats)) {
      if (visibleBoatId && boat.id !== visibleBoatId) continue
      const distance = Math.hypot(world[0] - boat.x, world[1] - boat.y)
      if (distance < closestDistance) {
        closestId = boat.id
        closestDistance = distance
      }
    }
    if (closestId && closestDistance < 45 / viewport.scale) {
      onSelectBoat(closestId)
    }
  }


  const labels = useMemo(() => {
    const boats = replay.competitors.filter((boat) => !visibleBoatId || boat.id === visibleBoatId)
    const anchors = boats.flatMap((boat) => {
      const state = frame.boats[boat.id]
      if (!state || !Number.isFinite(state.x) || !Number.isFinite(state.y)) return []
      const [x, y] = worldToScreen(viewport, [state.x, state.y])
      if (x < -12 || y < -12 || x > size.width + 12 || y > size.height + 12) return []
      return [{ id: boat.id, x, y, width: showVmgLabels ? 116 : 84, height: 44, priority: boat.id === selectedId ? 0 : highlightComparison && boat.id === comparisonId ? 1 : 2 }]
    })
    const courseLabels: LabelObstacle[] = []
    const markScreen = (id: string): Point | null => {
      const mark = frame.marks[id]
      const point = mark ? [mark.x, mark.y] as Point : replay.course.marks[id]?.target
      return point ? worldToScreen(viewport, point) : null
    }
    for (const id of Object.keys(replay.course.marks)) {
      const point = markScreen(id)
      if (point) courseLabels.push({ left: point[0] - 28, top: point[1] - 10, width: 56, height: 40 })
    }
    for (const gate of replay.course.sequences ?? []) {
      const port = markScreen(gate.port_mark), starboard = markScreen(gate.starboard_mark)
      if (port && starboard) courseLabels.push({ left: (port[0] + starboard[0]) / 2 - 68, top: (port[1] + starboard[1]) / 2 - 36, width: 136, height: 28 })
    }
    return layoutBoatLabels(anchors, size.width, size.height, courseLabels).map((label) => ({ ...label, boat: replay.competitors.find((boat) => boat.id === label.id)!, state: frame.boats[label.id] }))
  }, [comparisonId, frame, highlightComparison, replay.competitors, replay.course, selectedId, showVmgLabels, size.height, size.width, viewport, visibleBoatId])


  return (
    <div
      ref={containerRef}
      className="course-canvas"
      style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}
    >
      <style>{`
        .map-osm-attribution {
          position: absolute;
          right: 8px;
          bottom: 6px;
          z-index: 10;
          font-size: 10px;
          color: rgba(148, 163, 184, 0.85);
          background: rgba(4, 13, 26, 0.75);
          padding: 2px 6px;
          border-radius: 3px;
          border: 1px solid rgba(30, 41, 59, 0.6);
          pointer-events: auto;
          user-select: none;
        }
        .map-osm-attribution a {
          color: var(--foiling-cyan, #38bdf8);
          text-decoration: none;
        }
        .map-osm-attribution a:hover {
          text-decoration: underline;
        }
      `}</style>

      {/* Layer 0: MapLibre GL JS WebGL Geographic Map */}
      {mapIsActive && (
        <div
          ref={mapContainerRef}
          className="maplibre-gl-layer"
          style={{ position: 'absolute', inset: 0, zIndex: 0 }}
        />
      )}

      {/* Layer 1: Static Grid, Race Boundary Corridor & Synthetic Water fallback */}
      <canvas
        ref={staticRef}
        aria-label="Race course environment"
        style={{ position: 'absolute', inset: 0, zIndex: 1, pointerEvents: 'none' }}
      />

      {/* Layer 2: 60 FPS Dynamic Vessels, Marks, Trails & Badges */}
      <canvas
        ref={dynamicRef}
        aria-label="Live vessel positions"
        data-trail-scope={trailScope}
        data-highlighted-boats={[selectedId, highlightComparison ? comparisonId : null].filter(Boolean).join(",")}
        data-vmg-labels={showVmgLabels}
        data-viewport={JSON.stringify(viewport)}
        data-visible-boat={visibleBoatId ?? 'all'}
        style={{ position: 'absolute', inset: 0, zIndex: 2, cursor: 'crosshair' }}
        onPointerDown={pointerDown}
        onPointerMove={pointerMove}
        onPointerUp={pointerUp}
        onPointerCancel={pointerUp}
        onWheel={wheel}
        onClick={chooseBoat}
      />
      <div className="course-boat-label-layer" aria-label="Boat labels and VMG">
        <svg className="course-boat-leaders" viewBox={`0 0 ${size.width} ${size.height}`} aria-hidden="true">{labels.map((label) => <g key={label.id}><line x1={label.x} y1={label.y} x2={Math.max(label.left, Math.min(label.left + label.width, label.x))} y2={Math.max(label.top, Math.min(label.top + label.height, label.y))} /><circle cx={label.x} cy={label.y} r="3" /></g>)}</svg>
        {labels.map((label) => {
          const primary = label.id === selectedId, comparison = highlightComparison && label.id === comparisonId && !primary
          const vmg = Number.isFinite(label.state.vmg) ? `${label.state.vmg >= 0 ? '+' : ''}${label.state.vmg.toFixed(1)} kt` : 'Unavailable'
          return <button key={label.id} type="button" className={`course-boat-label${comparison ? ' is-comparison' : ''}`} style={{ left: label.left, top: label.top, width: label.width, height: label.height }} aria-label={`${label.boat.team_code}${primary ? ', highlighted A' : comparison ? ', highlighted B' : ''}, VMG ${vmg}`} aria-pressed={primary || comparison} onClick={() => onSelectBoat(label.id)} title={`${label.boat.team_name} · select as boat A`}><span className="course-label-identity"><i style={{ background: label.boat.color }} />{(primary || comparison) && <b>{primary ? 'A' : 'B'}</b>}{label.boat.team_code}</span>{showVmgLabels && <span className="course-label-vmg" title="Signed VMG along the fixed course axis">VMG {vmg}</span>}</button>
        })}
      </div>

      {/* Visible OpenStreetMap Attribution */}
      {viewMode === 'map' && (isFallback || isOfflineFallback) && <div className="map-source-status" role="status">{isOfflineFallback ? 'Map tiles offline' : 'Map unavailable'} · Grid fallback</div>}
      {viewMode === 'map' && !isFallback && !isOfflineFallback && (
        <div className="map-osm-attribution">
          ©{' '}
          <a
            href="https://www.openstreetmap.org/copyright"
            target="_blank"
            rel="noopener noreferrer"
          >
            OpenStreetMap
          </a>{' '}
          contributors
        </div>
      )}
    </div>
  )
}
