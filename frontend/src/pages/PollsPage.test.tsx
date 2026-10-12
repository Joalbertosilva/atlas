import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { SYNTHETIC_OFFICES, SYNTHETIC_RANKING, SYNTHETIC_STATES, jsonResponse } from '../test/fixtures.synthetic'
import { renderApp } from '../test/render'

const STATS = {
  data: {
    total: 2,
    institutos: 2,
    amostra: 3500,
    dt_primeiro_turno: '2026-10-04',
    dt_segundo_turno: '2026-10-25',
    janela: '2',
    por_mes: [{ mes: '2026-10', n: 2, amostra: 3500 }],
    por_cargo: [{ ds_cargo: 'Presidente', n: 2 }],
    institutos_top: [{ instituto: 'Instituto sintético', n: 2, amostra: 3500 }],
  },
  meta: { notes: ['Registro de pesquisa não é resultado: o cadastro do TSE não traz percentuais de intenção de voto.'] },
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const body = typeof init?.body === 'string' ? init.body : ''
      if (url.includes('/offices')) return jsonResponse(SYNTHETIC_OFFICES)
      if (url.includes('/states')) return jsonResponse(SYNTHETIC_STATES)
      if (url.includes('/search/polls/stats')) return jsonResponse(STATS)
      if (url.includes('/search/polls')) {
        const parsed = body ? (JSON.parse(body) as { page?: number }) : {}
        const page = parsed.page ?? 1
        const proto = page === 2 ? 'BR000022026' : 'BR000012026'
        return jsonResponse({
          data: [
            {
              nr_protocolo_registro: proto,
              sg_uf: 'BR',
              nm_ue: 'BRASIL',
              nm_empresa: page === 2 ? 'Instituto da página 2' : 'Instituto sintético',
              nm_empresa_fantasia: null,
              ds_cargo: 'Presidente',
              dt_registro: '2026-10-10T12:00:00',
              dt_inicio_pesquisa: '2026-10-13',
              dt_fim_pesquisa: '2026-10-15',
              dt_divulgacao: '2026-10-16',
              qt_entrevistado: 2000,
              vr_pesquisa: 1,
              pesqele_url: 'https://www.tse.jus.br/eleicoes/pesquisa-eleitorais/consulta-as-pesquisas-registradas',
              status: 'registro_oficial_encontrado',
            },
          ],
          meta: { pagination: { page, page_size: 10, total: 11 } },
        })
      }
      if (url.includes('/results/ranking')) {
        return jsonResponse({
          ...SYNTHETIC_RANKING,
          data: SYNTHETIC_RANKING.data.map((row, i) => ({
            ...row,
            ds_sit_tot_turno: i < 2 ? '2º TURNO' : row.ds_sit_tot_turno,
          })),
        })
      }
      if (url.includes('/municipalities')) {
        return jsonResponse({ data: [], meta: { pagination: { page: 1, page_size: 30, total: 0 } } })
      }
      return jsonResponse({ error: { code: 'not_found', message: `rota sintética ausente: ${url} ${body}` } }, 404)
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('pesquisas do 2º turno mostram registros e a contagem oficial colorida', async () => {
  renderApp('/evolucao')
  expect(await screen.findByRole('heading', { name: 'Pesquisas registradas' })).toBeInTheDocument()
  expect(await screen.findByText('Registros nesta janela')).toBeInTheDocument()
  expect(screen.getAllByText('2').length).toBeGreaterThan(0)
  expect(await screen.findByText('Quem vai ao 2º turno (urna do 1º)')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'BR000012026' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'BR000012026' })).toHaveAttribute('href', expect.stringContaining('ficha=BR000012026'))
  expect(screen.getByText(/não traz percentuais/i)).toBeInTheDocument()
  expect(screen.getAllByText(/Página 1 de 2/).length).toBeGreaterThan(0)
  await userEvent.click(screen.getAllByRole('button', { name: 'Seguinte' })[0])
  expect(await screen.findByRole('link', { name: 'BR000022026' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'BR000012026' })).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Pesquisas registradas' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '1º turno' }))
  expect(await screen.findByText('Contagem oficial do 1º turno')).toBeInTheDocument()
})
