import { useMemo } from 'react'
import type { CandidateMunicipality, GeometryProperties, LeaderMunicipality, SequentialLegend } from '../api/types'
import { NO_DATA_COLOR, TIE_COLOR, fillForLeaderRow, marginFill, sequentialFill } from '../lib/mapColors'
import SvgChoropleth from './SvgChoropleth'

type Props = {
  geometry: GeoJSON.FeatureCollection<GeoJSON.Geometry, GeometryProperties>
  rows: Array<LeaderMunicipality | CandidateMunicipality>
  mode: 'leader' | 'candidate' | 'margin'
  bands?: SequentialLegend['bands']
  onSelectMunicipio?: (tse: string, uf: string) => void
  onSelectUf?: (uf: string) => void
  flyToIbge?: string | null
}

type PaintedProps = GeometryProperties & { fill: string }

function isLeader(row: LeaderMunicipality | CandidateMunicipality): row is LeaderMunicipality {
  return 'leader' in row
}

function parseGeometry(raw: unknown): GeoJSON.Geometry | null {
  if (!raw) return null
  if (typeof raw === 'string') {
    try {
      return parseGeometry(JSON.parse(raw))
    } catch {
      return null
    }
  }
  if (typeof raw !== 'object' || !('type' in raw)) return null
  return raw as GeoJSON.Geometry
}

function toFillGeom(raw: unknown): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  const geometry = parseGeometry(raw)
  if (!geometry) return null
  if (geometry.type === 'Polygon' || geometry.type === 'MultiPolygon') return geometry
  if (geometry.type === 'GeometryCollection') {
    const coords: GeoJSON.Position[][][] = []
    for (const part of geometry.geometries) {
      if (part.type === 'Polygon') coords.push(part.coordinates)
      if (part.type === 'MultiPolygon') coords.push(...part.coordinates)
    }
    if (coords.length === 0) return null
    return { type: 'MultiPolygon', coordinates: coords }
  }
  return null
}

export default function MapView({ geometry, rows, mode, bands, onSelectMunicipio, onSelectUf }: Props) {
  const byIbge = useMemo(() => {
    const map = new Map<string, LeaderMunicipality | CandidateMunicipality>()
    for (const row of rows) {
      if (row.is_exterior || !row.cd_municipio_ibge) continue
      map.set(String(row.cd_municipio_ibge), row)
    }
    return map
  }, [rows])

  const maxMargin = useMemo(() => {
    return rows.reduce((max, row) => {
      if (!isLeader(row) || row.margin_pp == null) return max
      return Math.max(max, row.margin_pp)
    }, 0)
  }, [rows])

  const colorByUf = useMemo(() => {
    const tally = new Map<string, Map<string, { votes: number; color: string }>>()
    const candidateVotes = new Map<string, { got: number; total: number }>()
    for (const row of rows) {
      if (row.is_exterior || !row.sg_uf) continue
      if (mode === 'leader' && isLeader(row) && row.leader) {
        const byOpt = tally.get(row.sg_uf) ?? new Map()
        const key = String(row.leader.option_id)
        const cur = byOpt.get(key) ?? { votes: 0, color: row.leader.color || TIE_COLOR }
        cur.votes += row.leader.qt_votos_validos ?? 0
        byOpt.set(key, cur)
        tally.set(row.sg_uf, byOpt)
      } else if (mode === 'candidate' && !isLeader(row)) {
        const cur = candidateVotes.get(row.sg_uf) ?? { got: 0, total: 0 }
        cur.got += row.qt_votos_validos ?? 0
        cur.total += row.qt_total_votos_validos ?? 0
        candidateVotes.set(row.sg_uf, cur)
      }
    }
    const colors: Record<string, string> = {}
    if (mode === 'candidate') {
      for (const [uf, value] of candidateVotes) {
        colors[uf] = sequentialFill(value.total > 0 ? (100 * value.got) / value.total : null, bands ?? [])
      }
    } else {
      for (const [uf, byOpt] of tally) {
        let best: { votes: number; color: string } | null = null
        for (const item of byOpt.values()) {
          if (!best || item.votes > best.votes) best = item
        }
        colors[uf] = best?.color ?? NO_DATA_COLOR
      }
    }
    return colors
  }, [rows, mode, bands])

  const colorByIbge = useMemo(() => {
    const colors: Record<string, string> = {}
    for (const [ibge, row] of byIbge) {
      if (mode === 'leader' && isLeader(row)) colors[ibge] = fillForLeaderRow(row)
      else if (mode === 'candidate' && !isLeader(row)) colors[ibge] = sequentialFill(row.pct_validos, bands ?? [])
      else if (mode === 'margin' && isLeader(row)) colors[ibge] = marginFill(row.margin_pp, maxMargin)
      else colors[ibge] = NO_DATA_COLOR
    }
    return colors
  }, [byIbge, mode, bands, maxMargin])

  const painted = useMemo(() => {
    const seen = new Set<string>()
    const features: GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon, PaintedProps>[] = []
    for (const feature of geometry.features) {
      const shape = toFillGeom(feature.geometry)
      if (!shape) continue
      const ibge = feature.properties?.cd_municipio_ibge != null
        ? String(feature.properties.cd_municipio_ibge)
        : ''
      const uf = feature.properties?.sg_uf ? String(feature.properties.sg_uf) : ''
      const id = ibge || uf
      if (!id || seen.has(id)) continue
      seen.add(id)
      features.push({
        type: 'Feature',
        id,
        geometry: shape,
        properties: {
          ...feature.properties,
          cd_municipio_ibge: ibge || undefined,
          sg_uf: uf || feature.properties?.sg_uf,
          fill: ibge ? (colorByIbge[ibge] || NO_DATA_COLOR) : (colorByUf[uf] || NO_DATA_COLOR),
        },
      })
    }
    return { type: 'FeatureCollection' as const, features }
  }, [geometry, colorByIbge, colorByUf])

  return (
    <div className="space-y-2">
      <SvgChoropleth
        collection={painted}
        onSelectMunicipio={onSelectMunicipio}
        onSelectUf={onSelectUf}
      />
      <p className="text-xs text-slate-600">
        {painted.features.length > 0
          ? painted.features[0]?.properties?.cd_municipio_ibge
            ? `${painted.features.length} municípios no mapa (malha IBGE).`
            : `${painted.features.length} UFs no mapa (malha IBGE). Clique num estado para ver municípios.`
          : 'Malha sem polígonos.'}
      </p>
      <p className="text-xs text-slate-500">
        Empate em {TIE_COLOR}; sem dados em {NO_DATA_COLOR}. Exterior não entra no mapa.
      </p>
    </div>
  )
}
