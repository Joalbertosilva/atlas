/**
 * Fixtures SINTÉTICAS — apenas para testes automatizados.
 * Não representam resultados, candidaturas nem municípios reais.
 * Nenhum destes valores deve ser usado na interface de produção.
 */

import type {
  Envelope,
  LeaderLegend,
  LeaderMunicipality,
  Office,
  RankingRow,
  SearchHit,
  SectionResults,
  State,
  Summary,
} from '../api/types'

export const SYNTHETIC_OFFICES: Envelope<Office[]> = {
  data: [
    {
      cd_cargo: '1',
      ds_cargo: 'Cargo sintético nacional',
      system: 'majoritario',
      scope: 'nacional',
      cd_eleicao: '0000',
      turnos: [1],
      seats: { BR: 1 },
    },
    {
      cd_cargo: '3',
      ds_cargo: 'Cargo sintético estadual majoritário',
      system: 'majoritario',
      scope: 'estadual',
      cd_eleicao: '0001',
      turnos: [1],
      seats: { XX: 1 },
    },
    {
      cd_cargo: '5',
      ds_cargo: 'Cargo sintético estadual A',
      system: 'majoritario',
      scope: 'estadual',
      cd_eleicao: '0001',
      turnos: [1],
      seats: { XX: 2 },
    },
    {
      cd_cargo: '6',
      ds_cargo: 'Cargo sintético proporcional',
      system: 'proporcional',
      scope: 'estadual',
      cd_eleicao: '0001',
      turnos: [1],
      seats: { XX: 8 },
    },
  ],
  meta: {},
}

export const SYNTHETIC_STATES: Envelope<State[]> = {
  data: [{ sg_uf: 'XX', nm_uf: 'Unidade sintética', cd_uf_ibge: '00', is_exterior: false }],
  meta: {},
}

export const SYNTHETIC_SUMMARY: Envelope<Summary> = {
  data: {
    qt_aptos: 1000,
    qt_comparecimento: 800,
    qt_abstencoes: 200,
    qt_votos: 800,
    qt_total_votos_validos: 700,
    qt_votos_nominais_validos: 700,
    qt_total_votos_leg_validos: 0,
    qt_votos_brancos: 50,
    qt_total_votos_nulos: 50,
    pct_comparecimento: 80,
    pct_abstencao: 20,
    pct_brancos: 6.25,
    pct_nulos: 6.25,
    choices_per_voter: 1,
    exterior: null,
    dt_ultima_totalizacao: '2026-01-01T00:00:00Z',
  },
  meta: {
    source: { source_generated_at: '2026-01-01T12:00:00Z', imported_at: '2026-01-02T12:00:00Z', resources: ['arquivo_sintetico'] },
    coverage: { status: 'completo', published_scopes: 1, expected_scopes: 1, notes: [] },
    denominators: { pct_validos: 'qt_total_votos_validos' },
  },
}

export const SYNTHETIC_SENATOR_SUMMARY: Envelope<Summary> = {
  data: { ...SYNTHETIC_SUMMARY.data, choices_per_voter: 2, qt_votos: 1600, exterior: null },
  meta: {
    ...SYNTHETIC_SUMMARY.meta,
    notes: ['Senador 2026: cada eleitor pôde escolher até 2 candidaturas; total de votos ≠ número de votantes.'],
  },
}

export const SYNTHETIC_RANKING: Envelope<RankingRow[]> = {
  data: [
    {
      rank: 1,
      option_id: 101,
      kind: 'candidatura',
      nr_votavel: '10',
      label: 'Opção sintética Alfa',
      candidacy_id: 1,
      nm_candidato: 'Pessoa sintética Alfa',
      sg_partido: 'PSA',
      sg_federacao: null,
      qt_votos: 400,
      qt_votos_validos: 400,
      pct_validos: 57.1429,
      pct_nominais: null,
      ds_sit_tot_turno: 'situação oficial sintética',
      nm_tipo_destinacao_votos: 'Válido',
      color: '#1d4ed8',
    },
    {
      rank: 2,
      option_id: 102,
      kind: 'candidatura',
      nr_votavel: '20',
      label: 'Opção sintética Beta',
      candidacy_id: 2,
      nm_candidato: 'Pessoa sintética Beta',
      sg_partido: 'PSB',
      sg_federacao: null,
      qt_votos: 300,
      qt_votos_validos: 300,
      pct_validos: 42.8571,
      pct_nominais: null,
      ds_sit_tot_turno: 'situação oficial sintética',
      nm_tipo_destinacao_votos: 'Válido',
      color: '#dc2626',
    },
  ],
  meta: {
    denominators: { pct_validos: 'qt_total_votos_validos' },
    notes: ['Situação (eleito, 2º turno, suplente...) vem do campo oficial DS_SIT_TOT_TURNO; o ranking não define eleitos.'],
    coverage: { status: 'completo' },
  },
}

export const SYNTHETIC_RANKING_TODAS: Envelope<RankingRow[]> = {
  data: [
    ...SYNTHETIC_RANKING.data,
    {
      rank: null,
      option_id: 900,
      kind: 'branco',
      nr_votavel: '95',
      label: 'Branco sintético',
      candidacy_id: null,
      nm_candidato: null,
      sg_partido: null,
      sg_federacao: null,
      qt_votos: 50,
      qt_votos_validos: 0,
      pct_validos: null,
      pct_nominais: null,
      ds_sit_tot_turno: null,
      nm_tipo_destinacao_votos: null,
      color: '#94a3b8',
    },
    {
      rank: null,
      option_id: 901,
      kind: 'nulo',
      nr_votavel: '96',
      label: 'Nulo sintético',
      candidacy_id: null,
      nm_candidato: null,
      sg_partido: null,
      sg_federacao: null,
      qt_votos: 50,
      qt_votos_validos: 0,
      pct_validos: null,
      pct_nominais: null,
      ds_sit_tot_turno: null,
      nm_tipo_destinacao_votos: null,
      color: '#94a3b8',
    },
  ],
  meta: SYNTHETIC_RANKING.meta,
}

export const SYNTHETIC_MUNICIPALITIES: Envelope<LeaderMunicipality[]> = {
  data: [
    {
      cd_municipio_tse: '00001',
      cd_municipio_ibge: '0000001',
      nm_municipio: 'Cidade sintética Um',
      sg_uf: 'XX',
      is_exterior: false,
      leader: { option_id: 101, label: 'Opção sintética Alfa', color: '#1d4ed8', qt_votos_validos: 10, pct_validos: 60 },
      second: { option_id: 102, label: 'Opção sintética Beta', color: '#dc2626', qt_votos_validos: 6, pct_validos: 40 },
      tie: false,
      tied_option_ids: [],
      margin_votes: 4,
      margin_pp: 20,
      qt_total_votos_validos: 16,
    },
    {
      cd_municipio_tse: '00002',
      cd_municipio_ibge: '0000002',
      nm_municipio: 'Cidade sintética Empate',
      sg_uf: 'XX',
      is_exterior: false,
      leader: { option_id: 101, label: 'Opção sintética Alfa', color: '#374151', qt_votos_validos: 8, pct_validos: 50 },
      second: { option_id: 102, label: 'Opção sintética Beta', color: '#dc2626', qt_votos_validos: 8, pct_validos: 50 },
      tie: true,
      tied_option_ids: [101, 102],
      margin_votes: 0,
      margin_pp: 0,
      qt_total_votos_validos: 16,
    },
    {
      cd_municipio_tse: '00003',
      cd_municipio_ibge: '0000003',
      nm_municipio: 'Cidade sintética Sem Dados',
      sg_uf: 'XX',
      is_exterior: false,
      leader: null,
      second: null,
      tie: false,
      tied_option_ids: [],
      margin_votes: null,
      margin_pp: null,
      qt_total_votos_validos: null,
    },
  ],
  meta: {
    legend: {
      type: 'categorical',
      items: [
        { option_id: 101, label: 'Opção sintética Alfa', color: '#1d4ed8', municipios: 1 },
        { option_id: null, label: 'Empate', color: '#374151', municipios: 1 },
        { option_id: null, label: 'Sem dados', color: '#e5e7eb', municipios: 1 },
      ],
    } satisfies LeaderLegend,
  },
}

export const SYNTHETIC_UF_LEADERS: Envelope<LeaderMunicipality[]> = {
  data: [
    {
      cd_municipio_tse: '',
      cd_municipio_ibge: null,
      nm_municipio: 'Unidade sintética',
      sg_uf: 'XX',
      is_exterior: false,
      leader: {
        option_id: 301,
        label: 'Opção sintética Gama',
        color: '#1d4ed8',
        qt_votos_validos: 90,
        pct_validos: 60,
        sq_candidato: '000000000001',
        cd_eleicao: '0001',
        sg_ue: 'XX',
        ds_sit_tot_turno: 'situação oficial sintética',
      },
      second: { option_id: 302, label: 'Opção sintética Delta', color: '#dc2626', qt_votos_validos: 60, pct_validos: 40 },
      tie: false,
      tied_option_ids: [],
      margin_votes: 30,
      margin_pp: 20,
      qt_total_votos_validos: 150,
    },
  ],
  meta: {
    legend: {
      type: 'categorical',
      items: [{ option_id: 301, label: 'Opção sintética Gama', color: '#1d4ed8', municipios: 1 }],
    } satisfies LeaderLegend,
    coverage: { notes: ['Cada cor é a candidatura com mais votos válidos naquela UF.'] },
  },
}

export const SYNTHETIC_SEARCH_HITS: Envelope<SearchHit[]> = {
  data: [
    {
      title: 'Resultado sintético',
      url: 'https://example.test/sintetico',
      domain: 'example.test',
      snippet: 'Trecho com <script>alert(1)</script> e tags.',
      engines: ['mecanismo-sintetico'],
      published_at: null,
    },
  ],
  meta: {
    query_sent: 'consulta sintetica',
    status: 'parcial',
    providers: [
      { engine: 'mecanismo-sintetico', status: 'ok', reason: null, results: 1 },
      { engine: 'mecanismo-ausente', status: 'indisponivel', reason: 'timeout sintético', results: 0 },
    ],
    cache: { hit: true, fetched_at: '2026-01-03T15:04:00Z', ttl_seconds: 600 },
  },
}

export const SYNTHETIC_SECTION: Envelope<SectionResults> = {
  data: {
    section: {
      section_id: 9,
      nr_zona: '1',
      nr_secao: '1',
      polling_place_id: null,
      nm_local_votacao: null,
      link_status: 'sem_vinculo',
      ds_tipo_secao_agregada: null,
      nr_secao_principal: null,
      qt_eleitor_secao: 10,
    },
    turnout: {
      qt_aptos: 10,
      qt_comparecimento: 8,
      qt_abstencoes: 2,
      qt_votos_nominais: 7,
      qt_votos_brancos: 0,
      qt_votos_nulos: 1,
      qt_votos_legenda: 0,
    },
    results: [
      {
        option_id: 101,
        kind: 'candidatura',
        nr_votavel: '10',
        label: 'Opção sintética Alfa',
        sg_partido: 'PSA',
        qt_votos: 7,
        color: '#1d4ed8',
      },
    ],
  },
  meta: { notes: ['Local não identificado na base para esta seção (ou vínculo não confirmado).'] },
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
