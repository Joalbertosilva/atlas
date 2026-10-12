import { screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { SYNTHETIC_OFFICES, SYNTHETIC_STATES, jsonResponse } from '../test/fixtures.synthetic'
import { renderApp } from '../test/render'

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/offices')) return jsonResponse(SYNTHETIC_OFFICES)
      if (url.includes('/states')) return jsonResponse(SYNTHETIC_STATES)
      if (url.includes('/results/party-compare')) {
        return jsonResponse({
          data: {
            metrica: 'nominais',
            nr_partido: '13',
            level: 'uf',
            years: {
              '2022': { available: false, reason: 'recorte não publicado nesta base', total_validos: null },
              '2026': { available: true, reason: null, total_validos: 1000, ano: 2026 },
            },
            parties: [
              {
                nr_partido: '13',
                sg_partido_2022: null,
                sg_partido_2026: 'PT',
                votos_2022: null,
                votos_2026: 400,
                pct_2022: null,
                pct_2026: 40,
                delta_votos: null,
                delta_pp: null,
                delta_rel_pct: null,
                variacao_relativa: 'indisponivel',
              },
            ],
            places: [],
          },
          meta: {
            denominators: { pct: 'qt_total_votos_validos do recorte' },
            coverage: { notes: ['Arquivos de resultado de 2022 ainda não foram importados nesta base.'] },
          },
        })
      }
      if (url.includes('/map/geometry')) return jsonResponse({ type: 'FeatureCollection', features: [] })
      if (url.includes('/municipalities')) return jsonResponse({ data: [], meta: { pagination: { page: 1, page_size: 30, total: 0 } } })
      return jsonResponse({ error: { code: 'not_found', message: url } }, 404)
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('comparar partidos mostra 2026 real e 2022 ausente sem tratar como zero', async () => {
  renderApp('/comparar?painel=partidos')
  expect(await screen.findByRole('heading', { name: 'Comparar' })).toBeInTheDocument()
  expect(await screen.findByText(/2022 ainda não foi importado/)).toBeInTheDocument()
  expect(screen.getByText('não calculável')).toBeInTheDocument()
  expect(screen.getByText('400')).toBeInTheDocument()
})
