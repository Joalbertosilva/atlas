import { useMemo, useState } from 'react'
import type { GeometryProperties } from '../api/types'
import { NO_DATA_COLOR } from '../lib/mapColors'

type PaintedProps = GeometryProperties & { fill: string }

type Props = {
  collection: GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, PaintedProps>
  onSelectMunicipio?: (tse: string, uf: string) => void
  onSelectUf?: (uf: string) => void
}

const WIDTH = 900
const HEIGHT = 780
const PAD = 16

function ringsOf(geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon): GeoJSON.Position[][] {
  if (geometry.type === 'Polygon') return geometry.coordinates
  return geometry.coordinates.flat()
}

function boundsOf(collection: Props['collection']): [[number, number], [number, number]] | null {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const feature of collection.features) {
    for (const ring of ringsOf(feature.geometry)) {
      for (const pair of ring) {
        const x = pair[0], y = pair[1]
        if (!Number.isFinite(x) || !Number.isFinite(y)) continue
        if (x < minX) minX = x
        if (y < minY) minY = y
        if (x > maxX) maxX = x
        if (y > maxY) maxY = y
      }
    }
  }
  if (!Number.isFinite(minX)) return null
  return [[minX, minY], [maxX, maxY]]
}

function project(
  lng: number,
  lat: number,
  bounds: [[number, number], [number, number]],
): [number, number] {
  const [[minX, minY], [maxX, maxY]] = bounds
  const dx = maxX - minX || 1
  const dy = maxY - minY || 1
  const x = PAD + ((lng - minX) / dx) * (WIDTH - PAD * 2)
  const y = PAD + ((maxY - lat) / dy) * (HEIGHT - PAD * 2)
  return [x, y]
}

function pathOf(
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon,
  bounds: [[number, number], [number, number]],
): string {
  const parts: string[] = []
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates
  for (const polygon of polygons) {
    for (const ring of polygon) {
      ring.forEach((pair, index) => {
        const [x, y] = project(pair[0], pair[1], bounds)
        parts.push(`${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`)
      })
      parts.push('Z')
    }
  }
  return parts.join(' ')
}

export default function SvgChoropleth({ collection, onSelectMunicipio, onSelectUf }: Props) {
  const [hover, setHover] = useState<string>('')
  const bounds = useMemo(() => boundsOf(collection), [collection])

  if (!bounds || collection.features.length === 0) {
    return (
      <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
        Sem polígonos para desenhar.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full max-h-[36rem] rounded-lg border border-slate-200 bg-slate-50"
        role="img"
        aria-label="Mapa de resultados"
      >
        {collection.features.map((feature) => {
          const props = feature.properties
          const key = String(feature.id ?? props.cd_municipio_ibge ?? props.sg_uf)
          const label = props.nm_municipio
            ? `${props.nm_municipio} (${props.sg_uf ?? ''})`
            : (props.nm_uf ?? props.sg_uf ?? key)
          return (
            <path
              key={key}
              d={pathOf(feature.geometry, bounds)}
              fill={props.fill || NO_DATA_COLOR}
              stroke="#334155"
              strokeWidth={0.8}
              className="cursor-pointer hover:opacity-90"
              onMouseEnter={() => setHover(label)}
              onMouseLeave={() => setHover('')}
              onClick={() => {
                if (props.cd_municipio_tse && props.sg_uf) onSelectMunicipio?.(props.cd_municipio_tse, props.sg_uf)
                else if (props.sg_uf) onSelectUf?.(props.sg_uf)
              }}
            >
              <title>{label}</title>
            </path>
          )
        })}
      </svg>
      <p className="text-sm text-slate-700" aria-live="polite">
        {hover || 'Passe o mouse sobre um estado. Clique para ver os municípios.'}
      </p>
    </div>
  )
}
