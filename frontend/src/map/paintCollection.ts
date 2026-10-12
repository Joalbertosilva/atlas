import type { CandidateMunicipality, GeometryProperties, LeaderMunicipality, SequentialLegend } from '../api/types'
import { formatInt, formatPctShort } from '../lib/format'
import { fillForLeaderRow, MAP_NO_DATA, sequentialFill } from '../lib/mapColors'
import type { PaintedProps } from './SvgChoropleth'

export type MapPaintMode = 'leader' | 'candidate' | 'margin'

export function isLeaderRow(row: LeaderMunicipality | CandidateMunicipality): row is LeaderMunicipality {
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

export function toFillGeom(raw: unknown): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
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

function rowTooltip(
  row: LeaderMunicipality | CandidateMunicipality | undefined,
  props: GeometryProperties | undefined,
  uf: string,
): string {
  const name = props?.nm_municipio
    ? `${props.nm_municipio} (${props.sg_uf ?? uf})`
    : (props?.nm_uf ?? uf)
  if (!row) return `${name} — sem dados`
  if (isLeaderRow(row)) {
    if (!row.leader) return `${name} — sem dados`
    if (row.tie) return `${name} — empate (${row.leader.label}, ${formatPctShort(row.leader.pct_validos)})`
    const win = `${row.leader.label}: ${formatInt(row.leader.qt_votos_validos)} (${formatPctShort(row.leader.pct_validos)})`
    const lose = row.second
      ? ` · 2º ${row.second.label}: ${formatPctShort(row.second.pct_validos)}`
      : ''
    return `${name} — ${win}${lose}`
  }
  return `${name} — ${formatInt(row.qt_votos_validos)} (${formatPctShort(row.pct_validos)})`
}

export function mapFill(
  row: LeaderMunicipality | CandidateMunicipality | undefined,
  mode: MapPaintMode,
  bands: SequentialLegend['bands'] | undefined,
  maxMargin: number,
  candidateColor?: string,
): string {
  if (!row) return MAP_NO_DATA
  if (mode === 'leader' && isLeaderRow(row)) return fillForLeaderRow(row)
  if (mode === 'candidate' && !isLeaderRow(row)) return sequentialFill(row.pct_validos, bands ?? [], candidateColor)
  if (mode === 'margin' && isLeaderRow(row)) {
    if (!row.leader) return MAP_NO_DATA
    if (row.tie) return fillForLeaderRow(row)
    return sequentialFill(
      maxMargin > 0 && row.margin_pp != null ? (100 * row.margin_pp) / maxMargin : 0,
      [{ min: 0, max: 20 }, { min: 20, max: 40 }, { min: 40, max: 60 }, { min: 60, max: 80 }, { min: 80, max: 100 }],
      row.leader.color || candidateColor,
    )
  }
  return MAP_NO_DATA
}

export function paintCollection(
  geometry: GeoJSON.FeatureCollection<GeoJSON.Geometry, GeometryProperties>,
  rows: Array<LeaderMunicipality | CandidateMunicipality>,
  mode: MapPaintMode,
  bands?: SequentialLegend['bands'],
  candidateColor?: string,
): GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, PaintedProps> {
  const byIbge = new Map<string, LeaderMunicipality | CandidateMunicipality>()
  const byUf = new Map<string, LeaderMunicipality | CandidateMunicipality>()
  const tally = new Map<string, Map<string, { votes: number; color: string; label: string; row: LeaderMunicipality }>>()
  const candidateVotes = new Map<string, { got: number; total: number; row: CandidateMunicipality }>()
  let maxMargin = 0

  for (const row of rows) {
    if (row.is_exterior) continue
    if (row.cd_municipio_ibge) byIbge.set(String(row.cd_municipio_ibge), row)
    if (row.sg_uf && !row.cd_municipio_ibge) byUf.set(row.sg_uf, row)
    if (isLeaderRow(row) && row.margin_pp != null) maxMargin = Math.max(maxMargin, row.margin_pp)
    if (!row.sg_uf) continue
    if (mode === 'leader' && isLeaderRow(row) && row.leader) {
      const byOpt = tally.get(row.sg_uf) ?? new Map()
      const key = String(row.leader.option_id)
      const cur = byOpt.get(key) ?? {
        votes: 0,
        color: fillForLeaderRow(row),
        label: row.leader.label,
        row,
      }
      cur.votes += row.leader.qt_votos_validos ?? 0
      byOpt.set(key, cur)
      tally.set(row.sg_uf, byOpt)
    } else if (mode === 'candidate' && !isLeaderRow(row)) {
      const cur = candidateVotes.get(row.sg_uf) ?? { got: 0, total: 0, row }
      cur.got += row.qt_votos_validos ?? 0
      cur.total += row.qt_total_votos_validos ?? 0
      candidateVotes.set(row.sg_uf, cur)
    }
  }

  const ufFallback = new Map<string, { color: string; label: string }>()
  if (mode === 'candidate') {
    for (const [uf, value] of candidateVotes) {
      ufFallback.set(uf, {
        color: sequentialFill(value.total > 0 ? (100 * value.got) / value.total : null, bands ?? [], candidateColor),
        label: formatPctShort(value.total > 0 ? (100 * value.got) / value.total : null),
      })
    }
  } else {
    for (const [uf, byOpt] of tally) {
      let best: { votes: number; color: string; label: string; row: LeaderMunicipality } | null = null
      for (const item of byOpt.values()) {
        if (!best || item.votes > best.votes) best = item
      }
      if (best) ufFallback.set(uf, { color: best.color, label: best.label })
    }
  }

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
    const row = ibge ? byIbge.get(ibge) : (uf ? byUf.get(uf) : undefined)
    const ufLead = uf ? ufFallback.get(uf) : undefined
    const tooltip = ibge || row
      ? rowTooltip(row, feature.properties, uf)
      : `${feature.properties?.nm_uf ?? uf}${ufLead ? ` — ${ufLead.label}` : ''}`
    const fill = row
      ? mapFill(row, mode, bands, maxMargin, candidateColor)
      : (ufLead?.color || MAP_NO_DATA)
    features.push({
      type: 'Feature',
      id,
      geometry: shape,
      properties: {
        ...feature.properties,
        cd_municipio_ibge: ibge || undefined,
        sg_uf: uf || feature.properties?.sg_uf,
        fill,
        atlasFill: fill,
        tooltip,
      },
    })
  }
  return { type: 'FeatureCollection', features }
}
