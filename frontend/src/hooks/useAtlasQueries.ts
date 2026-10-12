import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiGet, apiPost, fetchGeometry, searchPost } from '../api/client'
import type {
  Candidacy,
  CompareResult,
  CoverageData,
  CrossCompareResult,
  PartyCompareResult,
  Election,
  Envelope,
  Health,
  LeaderMunicipality,
  CandidateMunicipality,
  Municipality,
  Office,
  PollingPlace,
  PollLeitura,
  PollStats,
  RankingRow,
  RegisteredPoll,
  SectionResults,
  SectionRow,
  State,
  Summary,
  ZoneRow,
} from '../api/types'
import { canFetchOverview, canFetchResults, scopeQuery, type ScopeState } from '../lib/scope'

const REF_STALE = 30 * 60_000
const DATA_STALE = 5 * 60_000

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<Health>('/health'),
    staleTime: 60_000,
  })
}

export function useOffices() {
  return useQuery({
    queryKey: ['offices'],
    queryFn: () => apiGet<Office[]>('/offices'),
    staleTime: REF_STALE,
  })
}

export function useElections() {
  return useQuery({
    queryKey: ['elections'],
    queryFn: () => apiGet<Election[]>('/elections'),
    staleTime: REF_STALE,
  })
}

export function useStates() {
  return useQuery({
    queryKey: ['states'],
    queryFn: () => apiGet<State[]>('/states'),
    staleTime: REF_STALE,
  })
}

export function useMunicipalities(uf?: string, q?: string, enabled = true) {
  return useQuery({
    queryKey: ['municipalities', uf, q],
    queryFn: () => apiGet<Municipality[]>('/municipalities', { uf, q, page_size: 30 }),
    enabled: enabled && (!!uf || (q !== undefined && q.length >= 2)),
    staleTime: DATA_STALE,
  })
}

export function useSummary(scope: ScopeState) {
  return useQuery({
    queryKey: ['summary', scopeQuery(scope)],
    queryFn: () => apiGet<Summary>('/results/summary', scopeQuery(scope)),
    enabled: canFetchResults(scope),
    staleTime: DATA_STALE,
  })
}

export function useRanking(scope: ScopeState, kind: 'candidatura' | 'todas', page = 1, pageSize = 50) {
  return useQuery({
    queryKey: ['ranking', scopeQuery(scope), kind, page, pageSize],
    queryFn: () =>
      apiGet<RankingRow[]>('/results/ranking', {
        ...scopeQuery(scope),
        kind,
        page,
        page_size: pageSize,
      }),
    enabled: canFetchResults(scope),
    staleTime: DATA_STALE,
  })
}

export function useUfLeaders(scope: ScopeState, enabled = true) {
  return useQuery({
    queryKey: ['uf-leaders', scope.cargo, scope.turno, scope.ano],
    queryFn: () =>
      apiGet<LeaderMunicipality[]>('/results/uf-leaders', {
        cargo: scope.cargo,
        turno: scope.turno,
        ano: scope.ano,
      }),
    enabled: enabled && canFetchOverview(scope),
    staleTime: DATA_STALE,
  })
}

export function useMunicipalityResults(
  scope: ScopeState,
  mode: 'leader' | 'candidate',
  optionId?: string,
  level: 'municipio' | 'uf' = 'municipio',
  enabled = true,
) {
  const candidateOk = mode !== 'candidate' || Boolean(optionId)
  return useQuery({
    queryKey: ['mun-results', scopeQuery(scope), mode, optionId, level],
    queryFn: () =>
      apiGet<LeaderMunicipality[] | CandidateMunicipality[]>('/results/municipalities', {
        cargo: scope.cargo,
        turno: scope.turno,
        uf: scope.uf || undefined,
        ano: scope.ano,
        mode,
        level,
        option_id: mode === 'candidate' ? optionId : undefined,
      }),
    enabled: canFetchResults({ ...scope, municipio: '' }) && candidateOk && enabled,
    staleTime: DATA_STALE,
  })
}

export function usePartyCompare(
  scope: ScopeState,
  metrica: 'nominais' | 'legenda' | 'ambos',
  nrPartido?: string,
) {
  return useQuery({
    queryKey: ['party-compare', scopeQuery(scope), metrica, nrPartido || ''],
    queryFn: () =>
      apiGet<PartyCompareResult>('/results/party-compare', {
        ...scopeQuery(scope),
        metrica,
        nr_partido: nrPartido || undefined,
      }),
    enabled: canFetchResults(scope),
    staleTime: DATA_STALE,
  })
}

export function useCompare(scope: ScopeState, optionIds: string) {
  return useQuery({
    queryKey: ['compare', scopeQuery(scope), optionIds],
    queryFn: () =>
      apiGet<CompareResult>('/results/compare', {
        cargo: scope.cargo,
        turno: scope.turno,
        uf: scope.uf || undefined,
        ano: scope.ano,
        option_ids: optionIds,
      }),
    enabled: canFetchResults({ ...scope, municipio: '' }) && optionIds.split(',').filter(Boolean).length >= 1,
    staleTime: DATA_STALE,
  })
}

export function useCrossCompare(scope: ScopeState, optionIds: string) {
  const ids = optionIds.split(',').filter(Boolean)
  return useQuery({
    queryKey: ['cross-compare', scopeQuery(scope), optionIds],
    queryFn: () =>
      apiGet<CrossCompareResult>('/results/cross-compare', {
        cargo: scope.cargo,
        turno: scope.turno,
        uf: scope.uf || undefined,
        option_ids: optionIds,
      }),
    enabled: canFetchResults({ ...scope, municipio: '' }) && ids.length === 2,
    staleTime: DATA_STALE,
  })
}

export function useCandidacies(cargo?: string, uf?: string, q?: string) {
  return useQuery({
    queryKey: ['candidacies', cargo, uf, q],
    queryFn: () => apiGet<Candidacy[]>('/candidacies', { cargo, uf, q, page_size: 40 }),
    enabled: !q || q.length >= 2,
    staleTime: DATA_STALE,
  })
}

export function useZones(municipio: string, cargo: string, turno: number) {
  return useQuery({
    queryKey: ['zones', municipio, cargo, turno],
    queryFn: () => apiGet<ZoneRow[]>(`/municipalities/${municipio}/zones`, { cargo, turno }),
    enabled: Boolean(municipio),
    staleTime: DATA_STALE,
  })
}

export function usePollingPlaces(municipio: string, zona?: string, q?: string) {
  return useQuery({
    queryKey: ['places', municipio, zona, q],
    queryFn: () =>
      apiGet<PollingPlace[]>(`/municipalities/${municipio}/polling-places`, {
        zona,
        q,
        page_size: 100,
      }),
    enabled: Boolean(municipio),
    staleTime: DATA_STALE,
  })
}

export function useSections(municipio: string, zona?: string, local?: string) {
  return useQuery({
    queryKey: ['sections', municipio, zona, local],
    queryFn: () =>
      apiGet<SectionRow[]>('/sections', {
        municipio,
        zona,
        local,
        page_size: 100,
      }),
    enabled: Boolean(municipio),
    staleTime: DATA_STALE,
  })
}

export function useSectionResults(sectionId: string, cargo: string, turno: number) {
  return useQuery({
    queryKey: ['section-results', sectionId, cargo, turno],
    queryFn: () => apiGet<SectionResults>(`/sections/${sectionId}/results`, { cargo, turno }),
    enabled: Boolean(sectionId),
    staleTime: DATA_STALE,
  })
}

export function usePollStats(cargoLabel: string | undefined, uf: string, janela: 'todas' | '1' | '2') {
  return useQuery({
    queryKey: ['polls-stats', cargoLabel, uf, janela],
    queryFn: () =>
      apiGet<PollStats>('/search/polls/stats', {
        uf: uf || undefined,
        cargo: cargoLabel,
        janela,
      }),
    staleTime: DATA_STALE,
  })
}

export const POLLS_PAGE_SIZE = 10

export function useRegisteredPolls(
  cargoLabel: string | undefined,
  uf: string,
  janela: 'todas' | '1' | '2',
  page: number,
) {
  return useQuery({
    queryKey: ['polls-list', cargoLabel, uf, janela, page, POLLS_PAGE_SIZE],
    queryFn: () =>
      searchPost<RegisteredPoll[]>('/search/polls', {
        q: '',
        uf: uf || undefined,
        cargo: cargoLabel,
        janela,
        page,
        page_size: POLLS_PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
    staleTime: DATA_STALE,
  })
}

export function usePollDetail(protocolo: string | undefined) {
  return useQuery({
    queryKey: ['poll-detail', protocolo],
    queryFn: () => apiGet<RegisteredPoll>(`/search/polls/${protocolo}`),
    enabled: Boolean(protocolo),
    staleTime: DATA_STALE,
  })
}

export function usePollLeitura(protocolo: string | undefined, cargo?: string) {
  return useQuery({
    queryKey: ['poll-leitura', protocolo, cargo],
    queryFn: () => apiPost<PollLeitura>(`/search/polls/${protocolo}/leitura`, { cargo: cargo || undefined }),
    enabled: Boolean(protocolo),
    staleTime: DATA_STALE,
  })
}

export function useCoverage() {
  return useQuery({
    queryKey: ['coverage'],
    queryFn: () => apiGet<CoverageData>('/coverage'),
    staleTime: DATA_STALE,
  })
}

export function useGeometry(level: 'municipio' | 'uf', uf?: string, enabled = true) {
  return useQuery({
    queryKey: ['geometry', level, uf || 'BR'],
    queryFn: () => fetchGeometry(level, uf),
    enabled,
    staleTime: Infinity,
  })
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'Falha inesperada ao consultar a API.'
}

export type QueryEnvelope<T> = Envelope<T>
