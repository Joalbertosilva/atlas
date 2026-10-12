import type { StyleSpecification } from 'maplibre-gl'
import { EXTRUSION_HEIGHT, LINE_WIDTH } from './camera'
import type { PaintedProps } from './SvgChoropleth'

export const OCEAN = '#b9cce3'

export const MINIMAL_STYLE: StyleSpecification = {
  version: 8,
  name: 'atlas-minimo',
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': OCEAN } }],
}

export function colorIndexCollection(
  collection: GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, PaintedProps>,
): {
  data: GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, PaintedProps & { ci: number }>
  colorExpr: unknown[]
} {
  const colors = [
    ...new Set(
      collection.features
        .map((feature) => feature.properties.atlasFill || feature.properties.fill)
        .filter((value): value is string => Boolean(value)),
    ),
  ]
  const index = new Map(colors.map((color, i) => [color, i]))
  const colorExpr: unknown[] = ['match', ['to-number', ['get', 'ci']]]
  for (const [i, color] of colors.entries()) {
    colorExpr.push(i, color)
  }
  colorExpr.push('#e5e7eb')
  return {
    data: {
      type: 'FeatureCollection',
      features: collection.features.map((feature) => {
        const fill = feature.properties.atlasFill || feature.properties.fill || '#e5e7eb'
        return {
          ...feature,
          properties: { ...feature.properties, ci: index.get(fill) ?? -1 },
        }
      }),
    },
    colorExpr,
  }
}

export function atlasStyle(
  collection: GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, PaintedProps>,
  mode: '2d' | '3d',
): StyleSpecification {
  const { data, colorExpr } = colorIndexCollection(collection)
  const layers: StyleSpecification['layers'] = [
    { id: 'background', type: 'background', paint: { 'background-color': OCEAN } },
    {
      id: 'atlas-fill',
      type: 'fill',
      source: 'atlas',
      paint: {
        'fill-antialias': true,
        'fill-color': colorExpr as never,
        'fill-opacity': 1,
      },
    },
  ]
  if (mode === '3d') {
    layers.push({
      id: 'atlas-extrusion',
      type: 'fill-extrusion',
      source: 'atlas',
      paint: {
        'fill-extrusion-color': colorExpr as never,
        'fill-extrusion-height': EXTRUSION_HEIGHT as never,
        'fill-extrusion-base': 0,
        'fill-extrusion-opacity': 0.92,
        'fill-extrusion-vertical-gradient': true,
      },
    })
  }
  layers.push({
    id: 'atlas-line',
    type: 'line',
    source: 'atlas',
    paint: {
      'line-color': '#ffffff',
      'line-width': LINE_WIDTH as never,
      'line-opacity': 1,
    },
  })
  return {
    version: 8,
    name: 'atlas-3d',
    light: {
      anchor: 'viewport',
      color: '#ffffff',
      intensity: 0.55,
      position: [1.35, 210, 28],
    },
    sources: {
      atlas: { type: 'geojson', data, generateId: true },
    },
    layers,
  }
}
