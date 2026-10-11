export type CargoCode = '1' | '3' | '5' | '6' | '7' | '8'
export type RankingKind = 'candidatura' | 'todas'
export type OptionKind = 'candidatura' | 'legenda' | 'branco' | 'nulo'
export type CoverageStatus = 'completo' | 'parcial' | 'indisponivel' | 'pendente' | string
export type MapMode = 'leader' | 'candidate' | 'margin'

export type ScopeMeta = {
  cd_eleicao?: string
  ds_eleicao?: string
  nr_turno?: number
  cd_cargo?: string
  ds_cargo?: string
  sg_ue?: string
  sg_uf?: string | null
  cd_municipio?: string | null
  system?: 'majoritario' | 'proporcional' | string
  qt_vaga?: number | null
  choices_per_voter?: number
}

export type SourceMeta = {
  source_generated_at?: string | null
  imported_at?: string | null
  resources?: string[]
  resource?: string
}

export type CoverageMeta = {
  status?: CoverageStatus
  published_scopes?: number
  expected_scopes?: number
  notes?: string[]
}

export type PaginationMeta = {
  page: number
  page_size: number
  total: number
}

export type Denominators = Record<string, string | number | null | undefined>

export type EnvelopeMeta = {
  scope?: ScopeMeta
  source?: SourceMeta
  coverage?: CoverageMeta
  pagination?: PaginationMeta
  denominators?: Denominators
  notes?: string[]
  legend?: LeaderLegend | SequentialLegend
  providers?: SearchProvider[]
  query_sent?: string
  category?: string
  cache?: { hit: boolean; fetched_at?: string | null; ttl_seconds?: number }
  status?: string
  allowed_publishers?: Array<{ name: string; domain: string; check_paths?: string[] }>
  municipality?: {
    cd_municipio_tse: string
    nm_municipio: string
    sg_uf: string
    cd_municipio_ibge?: string | null
  }
  link_status_legend?: Record<string, string>
}

export type Envelope<T> = {
  data: T
  meta: EnvelopeMeta
}

export type ApiErrorBody = {
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

export type Health = {
  status: 'ok' | 'degradado' | string
  database: 'ok' | 'erro' | string
  searxng: 'ok' | 'erro' | string
}

export type Election = {
  cd_eleicao: string
  ds_eleicao: string
  dt_eleicao: string | null
  tp_abrangencia: string
  turnos: number[]
}

export type Office = {
  cd_cargo: string
  ds_cargo: string
  system: 'majoritario' | 'proporcional' | string
  scope: 'nacional' | 'estadual' | string
  cd_eleicao: string | null
  turnos: number[]
  seats: Record<string, number> | null
}

export type State = {
  sg_uf: string
  nm_uf: string
  cd_uf_ibge: string | null
  is_exterior: boolean
}

export type Municipality = {
  cd_municipio_tse: string
  cd_municipio_ibge: string | null
  nm_municipio: string
  sg_uf: string
  is_exterior: boolean
}

export type CandidacyRound = {
  nr_turno: number
  ds_sit_tot_turno: string | null
  nm_tipo_destinacao_votos: string | null
}

export type Candidacy = {
  candidacy_id: number
  sq_candidato: string
  nr_candidato: string
  nm_urna_candidato: string
  nm_candidato: string
  sg_partido: string | null
  nm_partido: string | null
  sg_federacao: string | null
  nm_coligacao: string | null
  cd_cargo: string
  ds_cargo: string
  sg_ue: string
  ds_situacao_candidatura: string | null
  rounds: CandidacyRound[]
  option_id?: number | null
}

export type TurnoutBlock = {
  qt_aptos: number
  qt_comparecimento: number
  qt_abstencoes: number
  qt_votos: number
  qt_total_votos_validos: number
  qt_votos_nominais_validos: number
  qt_total_votos_leg_validos: number
  qt_votos_brancos: number
  qt_total_votos_nulos: number
  qt_total_votos_anul_subjud?: number
  qt_total_votos_anulados?: number
  qt_total_secoes?: number
  pct_comparecimento: number | null
  pct_abstencao: number | null
  pct_brancos?: number | null
  pct_nulos?: number | null
  choices_per_voter?: number
  dt_ultima_totalizacao?: string | null
}

export type Summary = TurnoutBlock & {
  exterior: TurnoutBlock | null
}

export type RankingRow = {
  rank: number | null
  option_id: number
  kind: OptionKind | string
  nr_votavel: string
  label: string
  candidacy_id: number | null
  nm_candidato: string | null
  sg_partido: string | null
  sg_federacao: string | null
  qt_votos: number
  qt_votos_validos: number
  pct_validos: number | null
  pct_nominais: number | null
  ds_sit_tot_turno: string | null
  nm_tipo_destinacao_votos: string | null
  color: string | null
}

export type LeaderInfo = {
  option_id: number
  label: string
  sg_partido?: string | null
  color: string | null
  qt_votos_validos: number
  pct_validos: number | null
}

export type LeaderMunicipality = {
  cd_municipio_tse: string
  cd_municipio_ibge: string | null
  nm_municipio: string
  sg_uf: string
  is_exterior: boolean
  leader: LeaderInfo | null
  second: LeaderInfo | null
  tie: boolean
  tied_option_ids: number[]
  margin_votes: number | null
  margin_pp: number | null
  qt_total_votos_validos: number | null
}

export type CandidateMunicipality = {
  cd_municipio_tse: string
  cd_municipio_ibge: string | null
  nm_municipio: string
  sg_uf: string
  is_exterior: boolean
  qt_votos_validos: number | null
  pct_validos: number | null
  qt_total_votos_validos: number | null
}

export type LeaderLegendItem = {
  option_id: number | null
  label: string
  color: string
  municipios: number
}

export type LeaderLegend = {
  type: 'categorical'
  items: LeaderLegendItem[]
}

export type SequentialBand = { min: number; max: number }

export type SequentialLegend = {
  type: 'sequential'
  option_id: number
  label: string
  color?: string | null
  bands: SequentialBand[]
  no_data_color?: string
}

export type CompareValue = {
  qt_votos_validos: number
  pct_validos: number | null
}

export type CompareMunicipality = {
  cd_municipio_tse: string
  nm_municipio: string
  sg_uf: string
  qt_total_votos_validos?: number
  values: Record<string, CompareValue>
}

export type CompareResult = {
  options: RankingRow[]
  municipalities: CompareMunicipality[]
}

export type ZoneRow = {
  nr_zona: string
  qt_aptos: number
  qt_comparecimento: number
  qt_total_votos_validos: number
  qt_votos_brancos: number
  qt_total_votos_nulos: number
  leader: LeaderInfo | null
  tie?: boolean
  sections_loaded: number
  sections_registered?: number
}

export type PollingPlace = {
  polling_place_id: number
  nr_zona: string
  nr_local_votacao: string
  nm_local_votacao: string
  ds_tipo_local: string | null
  ds_endereco: string | null
  nm_bairro: string | null
  latitude: number | null
  longitude: number | null
  coord_status: string
  qt_secoes: number
  qt_eleitor: number
}

export type SectionRow = {
  section_id: number
  nr_zona: string
  nr_secao: string
  polling_place_id: number | null
  nm_local_votacao: string | null
  ds_tipo_local?: string | null
  link_status: string
  ds_tipo_secao_agregada: string | null
  nr_secao_principal: string | null
  qt_eleitor_secao: number | null
}

export type SectionTurnout = {
  qt_aptos: number
  qt_comparecimento: number
  qt_abstencoes: number
  qt_votos_nominais: number
  qt_votos_brancos: number
  qt_votos_nulos: number
  qt_votos_legenda: number
  st_secao_instalada?: string | null
  st_secao_anulada?: string | null
  ds_origem_voto?: string | null
}

export type SectionResultRow = {
  option_id: number
  kind: OptionKind | string
  nr_votavel: string
  label: string
  sg_partido: string | null
  qt_votos: number
  color: string | null
}

export type SectionResults = {
  section: SectionRow & {
    cd_municipio_tse?: string
    nm_municipio?: string
    sg_uf?: string
    ds_endereco?: string | null
    nm_bairro?: string | null
    latitude?: number | null
    longitude?: number | null
    coord_status?: string | null
  }
  turnout: SectionTurnout | null
  results: SectionResultRow[]
}

export type CoverageGroup = {
  group: string
  published: number
  expected: number
  status: string
}

export type CoverageScopeRow = {
  kind?: string
  sg_uf?: string | null
  group?: string
  scope?: string
  status: string
  rows: number | null
  source_generated_at: string | null
  imported_at: string | null
  reconciliation_ok?: boolean
  member?: string | null
  note?: string | null
  error?: string | null
}

export type ReconciliationRow = {
  check_name: string
  total: number
  ok: number
  examples?: string[] | null
}

export type CoverageSummary = Record<string, unknown>

export type CoverageData = {
  summary: CoverageSummary
  groups?: CoverageGroup[]
  scopes: CoverageScopeRow[]
  reconciliation: ReconciliationRow[]
  pending: string[]
}

export type SearchHit = {
  title: string
  url: string
  domain: string
  snippet: string
  engines?: string[]
  published_at: string | null
  publisher?: string | null
  status?: string
  rating?: null
}

export type SearchProvider = {
  engine: string
  status: 'ok' | 'indisponivel' | string
  reason: string | null
  results?: number
}

export type RegisteredPoll = {
  nr_protocolo_registro: string
  sg_uf: string | null
  nm_ue: string | null
  nm_empresa: string | null
  nm_empresa_fantasia: string | null
  ds_cargo: string | null
  dt_registro: string | null
  dt_inicio_pesquisa: string | null
  dt_fim_pesquisa: string | null
  dt_divulgacao: string | null
  qt_entrevistado: number | null
  vr_pesquisa: number | null
  pesqele_url: string | null
  status: string
}

export type SearchBody = {
  q: string
  page?: number
  uf?: string
  municipio?: string
  candidato?: string
  cargo?: string
  empresa?: string
  de?: string
  ate?: string
}

export type ScopeQuery = {
  cargo?: string
  turno?: number
  uf?: string
  municipio?: string
  kind?: RankingKind
  mode?: 'leader' | 'candidate'
  option_id?: number | string
  page?: number
  page_size?: number
  format?: 'json' | 'csv'
}

export type GeometryProperties = {
  cd_municipio_ibge?: string
  cd_municipio_tse?: string
  nm_municipio?: string
  sg_uf?: string
  cd_uf_ibge?: string
  nm_uf?: string
}
