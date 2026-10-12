import { useEffect, useRef } from 'react'
import {
  Map as MapLibreMap,
  NavigationControl,
  Popup,
  LngLatBounds,
  setWorkerUrl,
  type GeoJSONSource,
  type MapLayerMouseEvent,
} from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import 'maplibre-gl/dist/maplibre-gl.css'
import { cameraFor, EXTRUSION_HEIGHT, LINE_WIDTH, type MapGrain } from './camera'
import { colorIndexCollection, MINIMAL_STYLE, OCEAN } from './style'
import type { PaintedProps } from './SvgChoropleth'

type Props = {
  collection: GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, PaintedProps>
  mode: '2d' | '3d'
  grain?: MapGrain
  selectedId?: string | null
  onFail: () => void
  onSelectMunicipio?: (tse: string, uf: string, ibge?: string) => void
  onSelectUf?: (uf: string) => void
  flyToId?: string | null
}

function extendBounds(bounds: LngLatBounds, geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon) {
  const rings = geometry.type === 'Polygon' ? geometry.coordinates : geometry.coordinates.flat()
  for (const ring of rings) {
    for (const pair of ring) bounds.extend([pair[0], pair[1]])
  }
}

function boundsOf(collection: Props['collection']): LngLatBounds | null {
  const bounds = new LngLatBounds()
  for (const feature of collection.features) extendBounds(bounds, feature.geometry)
  return bounds.isEmpty() ? null : bounds
}

function featureId(feature: GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon, PaintedProps>) {
  return String(feature.properties?.cd_municipio_ibge || feature.properties?.sg_uf || feature.id || '')
}

function collectionKey(collection: Props['collection']) {
  const first = collection.features[0]
  return `${collection.features.length}:${first ? featureId(first) : ''}:${first?.properties?.cd_municipio_ibge ? 'mun' : 'uf'}`
}

let workerConfigured = false
function configureWorker() {
  if (workerConfigured) return
  setWorkerUrl(workerUrl)
  workerConfigured = true
}

function paintAtlas(
  map: MapLibreMap,
  collection: Props['collection'],
  mode: '2d' | '3d',
  selectedId?: string | null,
) {
  const { data, colorExpr } = colorIndexCollection(collection)
  const existing = map.getSource('atlas') as GeoJSONSource | undefined
  if (existing) existing.setData(data)
  else map.addSource('atlas', { type: 'geojson', data, generateId: true })
  for (const id of ['atlas-highlight', 'atlas-line', 'atlas-extrusion', 'atlas-fill']) {
    if (map.getLayer(id)) map.removeLayer(id)
  }
  map.addLayer({
    id: 'atlas-fill',
    type: 'fill',
    source: 'atlas',
    paint: {
      'fill-antialias': true,
      'fill-color': colorExpr as never,
      'fill-opacity': 1,
    },
  })
  if (mode === '3d') {
    map.addLayer({
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
  map.addLayer({
    id: 'atlas-line',
    type: 'line',
    source: 'atlas',
    paint: {
      'line-color': '#ffffff',
      'line-width': LINE_WIDTH as never,
      'line-opacity': 1,
    },
  })
  if (selectedId) {
    map.addLayer({
      id: 'atlas-highlight',
      type: 'line',
      source: 'atlas',
      filter: [
        'any',
        ['==', ['get', 'cd_municipio_ibge'], selectedId],
        ['==', ['get', 'cd_municipio_tse'], selectedId],
        ['==', ['get', 'sg_uf'], selectedId],
      ],
      paint: {
        'line-color': '#0f172a',
        'line-width': 2.6,
        'line-opacity': 1,
      },
    })
  }
}

function applyCamera(
  map: MapLibreMap,
  bounds: LngLatBounds,
  mode: '2d' | '3d',
  grain: MapGrain,
  animate: boolean,
) {
  const cam = cameraFor(mode, grain)
  const box = map.getContainer()
  if (box.clientWidth < 80 || box.clientHeight < 80) return false
  const fitted = map.cameraForBounds(bounds, {
    padding: cam.padding,
    maxZoom: cam.maxZoom,
    bearing: 0,
    pitch: 0,
  })
  if (!fitted?.center || fitted.zoom == null) return false
  const next = {
    center: fitted.center,
    zoom: fitted.zoom,
    pitch: mode === '3d' ? cam.pitch : 0,
    bearing: mode === '3d' ? cam.bearing : 0,
  }
  if (animate) map.easeTo({ ...next, duration: 850 })
  else map.jumpTo(next)
  return true
}

function frame(map: MapLibreMap, collection: Props['collection'], mode: '2d' | '3d', grain: MapGrain, animate = false) {
  map.resize()
  const bounds = boundsOf(collection)
  if (!bounds) return false
  return applyCamera(map, bounds, mode, grain, animate)
}

function findFlyFeature(collection: Props['collection'], flyToId: string, grain: MapGrain) {
  return collection.features.find((item) => {
    const id = String(item.id ?? '')
    const ibge = item.properties?.cd_municipio_ibge
    const tse = item.properties?.cd_municipio_tse
    const uf = item.properties?.sg_uf
    if (id === flyToId || ibge === flyToId || tse === flyToId) return true
    return grain === 'uf' && uf === flyToId
  })
}

export default function MapLibreView({
  collection,
  mode,
  grain = 'uf',
  selectedId,
  onFail,
  onSelectMunicipio,
  onSelectUf,
  flyToId,
}: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const onFailRef = useRef(onFail)
  const collectionRef = useRef(collection)
  const modeRef = useRef(mode)
  const grainRef = useRef(grain)
  const selectedRef = useRef(selectedId)
  const onMunRef = useRef(onSelectMunicipio)
  const onUfRef = useRef(onSelectUf)
  const framedKey = useRef<string | null>(null)
  const prevGrain = useRef(grain)
  onFailRef.current = onFail
  collectionRef.current = collection
  modeRef.current = mode
  grainRef.current = grain
  selectedRef.current = selectedId
  onMunRef.current = onSelectMunicipio
  onUfRef.current = onSelectUf

  useEffect(() => {
    const node = ref.current
    if (!node) return
    if (collectionRef.current.features.length === 0) {
      onFailRef.current()
      return
    }
    let failed = false
    const fail = () => {
      if (failed) return
      failed = true
      onFailRef.current()
    }
    configureWorker()
    let map: MapLibreMap
    try {
      map = new MapLibreMap({
        container: node,
        style: MINIMAL_STYLE,
        center: [-54.5, -14.2],
        zoom: 3.55,
        pitch: 0,
        bearing: 0,
        minZoom: 3.1,
        maxZoom: 13,
        maxPitch: 65,
        cooperativeGestures: false,
        attributionControl: { compact: true },
        canvasContextAttributes: { antialias: true },
      })
    } catch {
      fail()
      return
    }
    mapRef.current = map
    map.addControl(new NavigationControl({ visualizePitch: mode === '3d', showCompass: mode === '3d' }), 'top-right')
    const popup = new Popup({ closeButton: false, closeOnClick: false, offset: 12 })

    const onError = (event: { error?: { message?: string } }) => {
      const message = event.error?.message ?? ''
      if (/webgl|context/i.test(message)) fail()
    }
    let pendingFrame = false
    const tryFrame = (animate = false) => {
      const ok = frame(map, collectionRef.current, modeRef.current, grainRef.current, animate)
      pendingFrame = !ok
    }
    const startPaint = () => {
      if (failed || !map.isStyleLoaded()) return
      try {
        paintAtlas(map, collectionRef.current, modeRef.current, selectedRef.current)
      } catch {
        fail()
        return
      }
      map.once('idle', () => {
        if (failed) return
        framedKey.current = collectionKey(collectionRef.current)
        tryFrame(false)
      })
    }
    map.on('error', onError)
    map.on('webglcontextlost', fail)
    if (map.isStyleLoaded()) startPaint()
    else map.once('load', startPaint)

    const pick = (event: MapLayerMouseEvent) => {
      const props = event.features?.[0]?.properties as PaintedProps | undefined
      if (!props) return
      if (props.cd_municipio_tse && props.sg_uf) {
        onMunRef.current?.(String(props.cd_municipio_tse), String(props.sg_uf), props.cd_municipio_ibge ? String(props.cd_municipio_ibge) : undefined)
      } else if (props.sg_uf) {
        onUfRef.current?.(String(props.sg_uf))
      }
    }
    const hover = (event: MapLayerMouseEvent) => {
      map.getCanvas().style.cursor = 'pointer'
      const props = event.features?.[0]?.properties as PaintedProps | undefined
      if (!props?.tooltip) return
      popup.setLngLat(event.lngLat).setText(props.tooltip).addTo(map)
    }
    const leave = () => {
      map.getCanvas().style.cursor = ''
      popup.remove()
    }
    for (const layer of ['atlas-fill', 'atlas-extrusion']) {
      map.on('click', layer, pick)
      map.on('mousemove', layer, hover)
      map.on('mouseleave', layer, leave)
    }

    const resize = () => {
      map.resize()
      if (pendingFrame) tryFrame(false)
    }
    const observer = new ResizeObserver(resize)
    observer.observe(node)
    window.addEventListener('resize', resize)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', resize)
      popup.remove()
      map.off('error', onError)
      map.remove()
      mapRef.current = null
      framedKey.current = null
    }
  }, [mode])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const key = collectionKey(collection)
    const apply = () => {
      if (!map.getSource('atlas') && !map.isStyleLoaded()) return
      paintAtlas(map, collection, mode, selectedId)
      if (framedKey.current !== key) {
        framedKey.current = key
        map.once('idle', () => frame(map, collection, mode, grain, grain !== 'uf'))
      } else if (prevGrain.current === 'local' && grain === 'municipio') {
        frame(map, collection, mode, grain, true)
      }
      prevGrain.current = grain
    }
    if (map.isStyleLoaded()) apply()
    else map.once('load', apply)
  }, [collection, mode, grain, selectedId])

  useEffect(() => {
    const map = mapRef.current
    const target = flyToId || selectedId
    if (!map || !target) return
    const feature = findFlyFeature(collection, target, grain)
    if (!feature) return
    const bounds = new LngLatBounds()
    extendBounds(bounds, feature.geometry)
    if (!bounds.isEmpty()) applyCamera(map, bounds, mode, 'local', true)
  }, [collection, flyToId, selectedId, mode, grain])

  return (
    <div
      ref={ref}
      className="atlas-map h-[38rem] w-full min-w-0 overflow-hidden rounded-2xl border border-slate-200"
      style={{ background: OCEAN }}
    />
  )
}

export function webglAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}
