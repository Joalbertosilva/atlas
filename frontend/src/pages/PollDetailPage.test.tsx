import { screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { jsonResponse } from '../test/fixtures.synthetic'
import { renderApp } from '../test/render'

const PROTO = 'BR006522026'

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/offices')) return jsonResponse({ data: [], meta: {} })
      if (url.includes('/states')) return jsonResponse({ data: [], meta: {} })
      if (url.includes(`/search/polls/${PROTO}/leitura`)) {
        return jsonResponse({
          data: {
            poll: {
              nr_protocolo_registro: PROTO,
              sg_uf: 'BR',
              nm_ue: 'BRASIL',
              nm_empresa: 'Instituto sintético',
              nm_empresa_fantasia: 'Sintético',
              ds_cargo: 'Presidente',
              dt_registro: '2026-10-10',
              dt_inicio_pesquisa: '2026-10-13',
              dt_fim_pesquisa: '2026-10-15',
              dt_divulgacao: '2026-10-16',
              qt_entrevistado: 2000,
              vr_pesquisa: 1,
              pesqele_url: 'https://www.tse.jus.br/eleicoes/pesquisa-eleitorais/consulta-as-pesquisas-registradas',
              status: 'registro_oficial_encontrado',
              janela: '2',
              ds_metodologia_pesquisa: 'Metodologia sintética de teste.',
            },
            janela: '2',
            cargo_usado: '1',
            mencoes: [
              { option_id: 1, label: 'Opção sintética Alfa', nr_votavel: '22', color: '#F5C400', pct_mencao: 48, trecho: 'Alfa 48%' },
            ],
            urna: [
              {
                option_id: 1, label: 'Opção sintética Alfa', nr_votavel: '22', sg_partido: 'PL',
                qt_votos_validos: 100, pct_validos: 47, ds_sit_tot_turno: '2º TURNO', color: '#F5C400',
              },
              {
                option_id: 2, label: 'Opção sintética Beta', nr_votavel: '13', sg_partido: 'PT',
                qt_votos_validos: 90, pct_validos: 45, ds_sit_tot_turno: '2º TURNO', color: '#E30613',
              },
            ],
            confronto: null,
            hits: [{ title: 'Matéria sintética', url: 'https://example.org/a', domain: 'example.org', snippet: 'Alfa 48%', engines: ['bing'], published_at: null }],
          },
          meta: { notes: ['O cadastro do TSE não contém intenção de voto.'] },
        })
      }
      return jsonResponse({ error: { code: 'not_found', message: url } }, 404)
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('ficha de pesquisa do 2º turno mostra cobertura e urna do 1º', async () => {
  renderApp(`/evolucao/${PROTO}`)
  expect(await screen.findByRole('heading', { name: /Instituto sintético|Sintético/ })).toBeInTheDocument()
  expect(screen.getByText('O que a cobertura diz')).toBeInTheDocument()
  expect(screen.getByText('Urna do 1º turno (quem foi ao 2º)')).toBeInTheDocument()
  expect(screen.getByText('Matéria sintética')).toBeInTheDocument()
  expect(screen.getByText(/não contém intenção de voto/i)).toBeInTheDocument()
})

test('pesquisa de 1º turno confronta cobertura com a urna', async () => {
  const fetchMock = vi.mocked(fetch)
  fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/offices')) return jsonResponse({ data: [], meta: {} })
    if (url.includes('/states')) return jsonResponse({ data: [], meta: {} })
    if (url.includes(`/search/polls/${PROTO}/leitura`)) {
      return jsonResponse({
        data: {
          poll: {
            nr_protocolo_registro: PROTO,
            sg_uf: 'BR',
            nm_ue: 'BRASIL',
            nm_empresa: 'Instituto sintético',
            nm_empresa_fantasia: 'Sintético',
            ds_cargo: 'Presidente',
            dt_registro: '2026-09-20',
            dt_inicio_pesquisa: '2026-09-28',
            dt_fim_pesquisa: '2026-09-30',
            dt_divulgacao: '2026-10-01',
            qt_entrevistado: 2000,
            vr_pesquisa: 1,
            pesqele_url: 'https://www.tse.jus.br/eleicoes/pesquisa-eleitorais/consulta-as-pesquisas-registradas',
            status: 'registro_oficial_encontrado',
            janela: '1',
          },
          janela: '1',
          cargo_usado: '1',
          mencoes: [
            { option_id: 1, label: 'Opção sintética Alfa', nr_votavel: '22', color: '#F5C400', pct_mencao: 49 },
            { option_id: 2, label: 'Opção sintética Beta', nr_votavel: '13', color: '#E30613', pct_mencao: 44 },
          ],
          urna: [
            {
              option_id: 1, label: 'Opção sintética Alfa', nr_votavel: '22', sg_partido: 'PL',
              qt_votos_validos: 100, pct_validos: 47, ds_sit_tot_turno: '2º TURNO', color: '#F5C400',
            },
            {
              option_id: 2, label: 'Opção sintética Beta', nr_votavel: '13', sg_partido: 'PT',
              qt_votos_validos: 90, pct_validos: 45, ds_sit_tot_turno: '2º TURNO', color: '#E30613',
            },
          ],
          confronto: [
            { option_id: 1, label: 'Opção sintética Alfa', nr_votavel: '22', color: '#F5C400', pct_mencao: 49, pct_urna: 47, delta_pp: 2 },
            { option_id: 2, label: 'Opção sintética Beta', nr_votavel: '13', color: '#E30613', pct_mencao: 44, pct_urna: 45, delta_pp: -1 },
          ],
          hits: [],
        },
        meta: { notes: ['O cadastro do TSE não contém intenção de voto.'] },
      })
    }
    return jsonResponse({ error: { code: 'not_found', message: url } }, 404)
  })
  renderApp(`/evolucao/${PROTO}?janela=1`)
  expect(await screen.findByText('Acertos da cobertura × urna')).toBeInTheDocument()
  expect(screen.getByText('Urna oficial do 1º turno')).toBeInTheDocument()
})
