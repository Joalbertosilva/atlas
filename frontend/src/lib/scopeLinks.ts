import { scopeQuery, type ScopeState } from './scope'

export function scopeSearch(scope: ScopeState, extra: Record<string, string> = {}): string {
  const q = new URLSearchParams()
  const base = scopeQuery(scope)
  if (base.cargo && base.cargo !== '1') q.set('cargo', base.cargo)
  if (base.turno && base.turno !== 1) q.set('turno', String(base.turno))
  if (base.uf) q.set('uf', base.uf)
  if (base.municipio) q.set('municipio', base.municipio)
  if (base.ano && base.ano !== 2026) q.set('ano', String(base.ano))
  for (const [key, value] of Object.entries(extra)) {
    if (value) q.set(key, value)
  }
  const qs = q.toString()
  return qs ? `?${qs}` : ''
}
