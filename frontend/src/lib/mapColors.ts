import type { LeaderLegend, LeaderMunicipality, SequentialLegend } from '../api/types'

export const TIE_COLOR = '#374151'
export const NO_DATA_COLOR = '#e5e7eb'
export const MAP_NO_DATA = '#edf2f7'
export const MAP_TIE = '#94a3b8'

/** Mistura a cor da candidatura com branco para o mapa (ainda reconhecível). */
export const MAP_COLOR_WHITE_MIX = 0.18

export function softenHex(hex: string | null | undefined, white = MAP_COLOR_WHITE_MIX): string {
  const raw = (hex || '').replace('#', '')
  if (!/^[0-9a-fA-F]{6}$/.test(raw)) return MAP_NO_DATA
  const r = Number.parseInt(raw.slice(0, 2), 16)
  const g = Number.parseInt(raw.slice(2, 4), 16)
  const b = Number.parseInt(raw.slice(4, 6), 16)
  const mix = (c: number) => Math.round(c * (1 - white) + 255 * white)
  return `#${[mix(r), mix(g), mix(b)].map((n) => n.toString(16).padStart(2, '0')).join('')}`
}
export const TIE_LABEL = 'Empate'
export const NO_DATA_LABEL = 'Sem dados'

export function sequentialStops(hex: string | null | undefined): string[] {
  const base = hex && /^#[0-9a-fA-F]{6}$/.test(hex) ? hex : '#1d4ed8'
  return [0.78, 0.58, 0.38, 0.18, 0].map((white) => softenHex(base, white))
}

export type MapLegendItem = {
  label: string
  color: string
  municipios?: number
}

export function fillForLeaderRow(row: LeaderMunicipality | undefined): string {
  if (!row || !row.leader) return NO_DATA_COLOR
  if (row.tie) return TIE_COLOR
  return row.leader.color || TIE_COLOR
}

export function sequentialFill(
  pct: number | null | undefined,
  bands: SequentialLegend['bands'],
  base = '#1d4ed8',
): string {
  if (pct === null || pct === undefined || bands.length === 0) return NO_DATA_COLOR
  const idx = bands.findIndex((band, i) => pct >= band.min && (pct < band.max || i === bands.length - 1))
  if (idx < 0) return NO_DATA_COLOR
  const stops = sequentialStops(base)
  return stops[Math.min(idx, stops.length - 1)] ?? base
}

export function marginFill(marginPp: number | null | undefined, maxAbs: number): string {
  if (marginPp === null || marginPp === undefined || maxAbs <= 0) return NO_DATA_COLOR
  const t = Math.min(1, Math.max(0, marginPp / maxAbs))
  const stops = ['#f1f5f9', '#cbd5e1', '#64748b', '#334155', '#0f172a']
  return stops[Math.min(stops.length - 1, Math.floor(t * (stops.length - 1)))] ?? NO_DATA_COLOR
}

export function leaderLegendItems(legend: LeaderLegend | undefined, rows: LeaderMunicipality[]): MapLegendItem[] {
  const fromApi = legend?.items ?? []
  const items = fromApi.map((item) => ({
    label: item.label,
    color: item.color,
    municipios: item.municipios,
  }))
  const hasTie = items.some((item) => item.label.toLowerCase() === 'empate') || rows.some((row) => row.tie)
  const hasNoData =
    items.some((item) => item.label.toLowerCase().includes('sem dados')) ||
    rows.some((row) => !row.leader)
  if (hasTie && !items.some((item) => item.label.toLowerCase() === 'empate')) {
    items.push({
      label: TIE_LABEL,
      color: TIE_COLOR,
      municipios: rows.filter((row) => row.tie).length,
    })
  }
  if (hasNoData && !items.some((item) => item.label.toLowerCase().includes('sem dados'))) {
    items.push({
      label: NO_DATA_LABEL,
      color: NO_DATA_COLOR,
      municipios: rows.filter((row) => !row.leader).length,
    })
  }
  return items.map((item) => {
    if (item.label.toLowerCase() === 'empate') return { ...item, color: TIE_COLOR }
    if (item.label.toLowerCase().includes('sem dados')) return { ...item, color: NO_DATA_COLOR }
    return item
  })
}

export function sequentialLegendItems(legend: SequentialLegend | undefined): MapLegendItem[] {
  const bands = legend?.bands ?? []
  const stops = sequentialStops(legend?.color)
  const items = bands.map((band, i) => ({
    label: `${band.min.toLocaleString('pt-BR')}–${band.max.toLocaleString('pt-BR')}% dos votos válidos`,
    color: stops[Math.min(i, stops.length - 1)] ?? legend?.color ?? '#1d4ed8',
  }))
  items.push({ label: NO_DATA_LABEL, color: legend?.no_data_color || NO_DATA_COLOR })
  return items
}
