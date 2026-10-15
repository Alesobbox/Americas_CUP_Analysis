import type { StyleSpecification } from 'maplibre-gl'

export interface MapTileConfig {
  enabled: boolean
  urlTemplate: string
  attribution: string
  attributionLink: string
  maxZoom: number
  tileSize: number
  fallbackMode: 'oceanic-synthetic' | 'blank'
  rasterOpacity: number
  rasterSaturation: number
  rasterContrast: number
  rasterBrightnessMin: number
  rasterBrightnessMax: number
  backgroundColor: string
}

export const DEFAULT_OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
export const DEFAULT_OSM_ATTRIBUTION = '© OpenStreetMap contributors'
export const DEFAULT_OSM_ATTRIBUTION_LINK = 'https://www.openstreetmap.org/copyright'

export const DEFAULT_MAP_TILE_CONFIG: MapTileConfig = {
  enabled: true,
  urlTemplate: DEFAULT_OSM_TILE_URL,
  attribution: DEFAULT_OSM_ATTRIBUTION,
  attributionLink: DEFAULT_OSM_ATTRIBUTION_LINK,
  maxZoom: 19,
  tileSize: 256,
  fallbackMode: 'oceanic-synthetic',
  rasterOpacity: 1,
  rasterSaturation: 0,
  rasterContrast: 0,
  rasterBrightnessMin: 0,
  rasterBrightnessMax: 1,
  backgroundColor: '#040d1a',
}

/**
 * Builds a MapLibre style from OpenStreetMap raster tiles with matching attribution.
 */
export function createMaritimeMapStyle(customConfig?: Partial<MapTileConfig>): StyleSpecification {
  const config = { ...DEFAULT_MAP_TILE_CONFIG, ...customConfig }

  const attributionHtml = config.attributionLink
    ? `&copy; <a href="${config.attributionLink}" target="_blank" rel="noopener noreferrer">${config.attribution.replace(/^©\s*/, '')}</a>`
    : config.attribution

  const layers: StyleSpecification['layers'] = [
    {
      id: 'background-ocean',
      type: 'background',
      paint: {
        'background-color': config.backgroundColor,
      },
    },
  ]

  const sources: StyleSpecification['sources'] = {}

  if (config.enabled) {
    sources['osm-raster-source'] = {
      type: 'raster',
      tiles: [config.urlTemplate],
      tileSize: config.tileSize,
      maxzoom: config.maxZoom,
      attribution: attributionHtml,
    }

    layers.push({
      id: 'osm-raster-layer',
      type: 'raster',
      source: 'osm-raster-source',
      minzoom: 0,
      maxzoom: config.maxZoom,
      paint: {
        'raster-opacity': config.rasterOpacity,
        'raster-saturation': config.rasterSaturation,
        'raster-contrast': config.rasterContrast,
        'raster-brightness-min': config.rasterBrightnessMin,
        'raster-brightness-max': config.rasterBrightnessMax,
      },
    })
  }

  return {
    version: 8,
    sources,
    layers,
  }
}

/**
 * Clean-water fallback style for offline operation or tile load failure.
 */
