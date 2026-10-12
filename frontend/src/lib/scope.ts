import type { MapMode } from '../api/types'

export type ScopeState = {
  cargo: string
  turno: number
  uf: string
  municipio: string
  modo: MapMode
  option: string
  ano: 2022 | 2026
}

export const STATE_CARGOS = new Set(['3', '5', '6', '7', '8'])
export const PROPORTIONAL_CARGOS = new Set(['6', '7', '8'])
export const SENATOR_CARGO = '5'
export const PRESIDENT_CARGO = '1'

export function parseMode(value: string | null): MapMode {
  if (value === 'candidate' || value === 'margin') return value
  return 'leader'
}

export function parseAno(value: string | null): 2022 | 2026 {
  return value === '2022' ? 2022 : 2026
}

export function readScope(params: URLSearchParams): ScopeState {
  const turno = Number(params.get('turno') || '1')
  return {
    cargo: params.get('cargo') || PRESIDENT_CARGO,
    turno: turno === 2 ? 2 : 1,
    uf: (params.get('uf') || '').toUpperCase(),
    municipio: params.get('municipio') || '',
    modo: parseMode(params.get('modo')),
    option: params.get('option') || '',
    ano: parseAno(params.get('ano')),
  }
}

export function writeScope(current: URLSearchParams, patch: Partial<ScopeState>): URLSearchParams {
  const next = new URLSearchParams(current)
  const merged = { ...readScope(current), ...patch }
  setOrDelete(next, 'cargo', merged.cargo === PRESIDENT_CARGO ? '' : merged.cargo)
  setOrDelete(next, 'turno', merged.turno === 1 ? '' : String(merged.turno))
  setOrDelete(next, 'uf', merged.uf)
  setOrDelete(next, 'municipio', merged.municipio)
  setOrDelete(next, 'modo', merged.modo === 'leader' ? '' : merged.modo)
  setOrDelete(next, 'option', merged.option)
  setOrDelete(next, 'ano', merged.ano === 2026 ? '' : String(merged.ano))
  return next
}

function setOrDelete(params: URLSearchParams, key: string, value: string) {
  if (!value) params.delete(key)
  else params.set(key, value)
}

export function needsUf(cargo: string): boolean {
  return STATE_CARGOS.has(cargo)
}

export function isProportional(cargo: string): boolean {
  return PROPORTIONAL_CARGOS.has(cargo)
}

export function scopeQuery(scope: ScopeState) {
  return {
    cargo: scope.cargo,
    turno: scope.turno,
    uf: scope.uf || undefined,
    municipio: scope.municipio || undefined,
    ano: scope.ano,
  }
}

export function canFetchResults(scope: ScopeState): boolean {
  if (needsUf(scope.cargo) && !scope.uf) return false
  if (scope.cargo === '8' && scope.uf && scope.uf !== 'DF') return false
  if (scope.cargo === '7' && scope.uf === 'DF') return false
  if (scope.uf === 'ZZ' && scope.cargo !== PRESIDENT_CARGO) return false
  return true
}

export function canFetchOverview(scope: ScopeState): boolean {
  if (!needsUf(scope.cargo) || scope.uf) return false
  if (scope.uf === 'ZZ') return false
  return true
}
