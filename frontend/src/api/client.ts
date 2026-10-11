import type { Envelope, GeometryProperties, ScopeQuery, SearchBody } from './types'

export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

export class ApiClientError extends Error {
  readonly code: string
  readonly status: number
  readonly details: unknown

  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiClientError'
    this.code = code
    this.status = status
    this.details = details
  }
}

function joinUrl(path: string): string {
  const base = API_BASE.replace(/\/$/, '')
  const suffix = path.startsWith('/') ? path : `/${path}`
  return `${base}${suffix}`
}

function toQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const usp = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    usp.set(key, String(value))
  }
  const qs = usp.toString()
  return qs ? `?${qs}` : ''
}

async function parseJson(res: Response): Promise<unknown> {
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text) as unknown
  } catch {
    throw new ApiClientError('internal_error', 'Resposta inválida da API.', res.status)
  }
}

function isErrorBody(body: unknown): body is { error: { code?: string; message?: string; details?: unknown } } {
  return Boolean(body && typeof body === 'object' && 'error' in body && (body as { error: unknown }).error)
}

function isEnvelope(body: unknown): body is Envelope<unknown> {
  return Boolean(body && typeof body === 'object' && 'data' in body)
}

async function request<T>(path: string, init?: RequestInit): Promise<Envelope<T>> {
  const res = await fetch(joinUrl(path), {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })
  const body = await parseJson(res)
  if (!res.ok || isErrorBody(body)) {
    const err = isErrorBody(body) ? body.error : undefined
    throw new ApiClientError(
      err?.code ?? (res.status === 429 ? 'rate_limited' : 'internal_error'),
      err?.message ?? `Falha ao consultar a API (${res.status}).`,
      res.status,
      err?.details,
    )
  }
  if (isEnvelope(body)) return body as Envelope<T>
  return { data: body as T, meta: {} }
}

export function apiGet<T>(path: string, params?: Record<string, string | number | boolean | undefined | null>) {
  return request<T>(`${path}${toQuery(params ?? {})}`)
}

export function apiPost<T>(path: string, body: unknown) {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) })
}

export function resultsPath(endpoint: 'ranking' | 'municipalities' | 'summary' | 'compare', params: ScopeQuery & Record<string, string | number | undefined>) {
  return `/results/${endpoint}${toQuery(params)}`
}

export function csvUrl(endpoint: 'ranking' | 'municipalities', params: ScopeQuery & Record<string, string | number | undefined>) {
  return joinUrl(resultsPath(endpoint, { ...params, format: 'csv' }))
}

export async function fetchGeometry(level: 'municipio' | 'uf', uf?: string) {
  const res = await fetch(joinUrl(`/map/geometry${toQuery({ level, uf })}`), {
    headers: { Accept: 'application/geo+json, application/json' },
  })
  const body = await parseJson(res)
  if (!res.ok || isErrorBody(body)) {
    const err = isErrorBody(body) ? body.error : undefined
    throw new ApiClientError(err?.code ?? 'internal_error', err?.message ?? 'Falha ao carregar geometria.', res.status)
  }
  const fc =
    body &&
    typeof body === 'object' &&
    (body as { type?: string }).type !== 'FeatureCollection' &&
    isEnvelope(body) &&
    body.data &&
    typeof body.data === 'object' &&
    (body.data as { type?: string }).type === 'FeatureCollection'
      ? (body.data as GeoJSON.FeatureCollection<GeoJSON.Geometry, GeometryProperties>)
      : (body as GeoJSON.FeatureCollection<GeoJSON.Geometry, GeometryProperties>)
  if (!fc || fc.type !== 'FeatureCollection' || !Array.isArray(fc.features)) {
    throw new ApiClientError('internal_error', 'Geometria IBGE em formato inesperado.', res.status)
  }
  return {
    ...fc,
    features: fc.features.map((feature) => {
      const geometry = feature.geometry
      if (typeof geometry !== 'string') return feature
      try {
        return { ...feature, geometry: JSON.parse(geometry) as GeoJSON.Geometry }
      } catch {
        return feature
      }
    }),
  }
}

export function searchPost<T>(path: '/search/web' | '/search/news' | '/search/fact-checks' | '/search/polls', body: SearchBody) {
  return apiPost<T>(path, body)
}
