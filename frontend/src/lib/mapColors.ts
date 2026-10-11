import type { LeaderLegend, LeaderMunicipality, SequentialLegend } from '../api/types'

export const TIE_COLOR = '#374151'
export const NO_DATA_COLOR = '#e5e7eb'
export const TIE_LABEL = 'Empate'
export const NO_DATA_LABEL = 'Sem dados'

const SEQUENTIAL_STOPS = ['#dbeafe', '#93c5fd', '#3b82f6', '#1d4ed8', '#1e3a8a']

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

export function sequentialFill(pct: number | null | undefined, bands: SequentialLegend['bands'], base = '#1d4ed8'): string {
  if (pct === null || pct === undefined || bands.length === 0) return NO_DATA_COLOR
  const idx = bands.findIndex((band, i) => pct >= band.min && (pct < band.max || i === bands.length - 1))
  if (idx < 0) return NO_DATA_COLOR
  return SEQUENTIAL_STOPS[Math.min(idx, SEQUENTIAL_STOPS.length - 1)] ?? base
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
  const items = bands.map((band, i) => ({
    label: `${band.min.toLocaleString('pt-BR')}–${band.max.toLocaleString('pt-BR')}% dos votos válidos`,
    color: SEQUENTIAL_STOPS[Math.min(i, SEQUENTIAL_STOPS.length - 1)] ?? '#1d4ed8',
  }))
  items.push({ label: NO_DATA_LABEL, color: legend?.no_data_color || NO_DATA_COLOR })
  return items
}
