import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import {
  SYNTHETIC_MUNICIPALITIES,
  SYNTHETIC_OFFICES,
  SYNTHETIC_RANKING,
  SYNTHETIC_RANKING_TODAS,
  SYNTHETIC_SENATOR_SUMMARY,
  SYNTHETIC_STATES,
  SYNTHETIC_SUMMARY,
  jsonResponse,
} from '../test/fixtures.synthetic'
import { renderApp } from '../test/render'

function mockApi() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/offices')) return jsonResponse(SYNTHETIC_OFFICES)
      if (url.includes('/states')) return jsonResponse(SYNTHETIC_STATES)
      if (url.includes('/results/summary') && url.includes('cargo=5')) return jsonResponse(SYNTHETIC_SENATOR_SUMMARY)
      if (url.includes('/results/summary')) return jsonResponse(SYNTHETIC_SUMMARY)
      if (url.includes('/results/ranking') && url.includes('kind=todas')) return jsonResponse(SYNTHETIC_RANKING_TODAS)
      if (url.includes('/results/ranking')) return jsonResponse(SYNTHETIC_RANKING)
      if (url.includes('/results/municipalities')) return jsonResponse(SYNTHETIC_MUNICIPALITIES)
      if (url.includes('/map/geometry')) {
        return jsonResponse({ type: 'FeatureCollection', features: [] })
      }
      if (url.includes('/municipalities')) return jsonResponse({ data: [], meta: { pagination: { page: 1, page_size: 30, total: 0 } } })
      return jsonResponse({ error: { code: 'not_found', message: `rota sintética ausente: ${url}` } }, 404)
    }),
  )
}

beforeEach(mockApi)
afterEach(() => {
  vi.unstubAllGlobals()
})

test('dashboard renderiza ranking e mostra denominador', async () => {
  renderApp('/')
  expect(await screen.findByRole('heading', { name: 'Resultados' })).toBeInTheDocument()
  expect(await screen.findByText('Opção sintética Alfa')).toBeInTheDocument()
  expect(screen.getByText('% dos votos válidos = votos válidos da opção / qt_total_votos_validos.')).toBeInTheDocument()
  expect(screen.getByText('Situação oficial (TSE)')).toBeInTheDocument()
  expect(screen.getAllByText('situação oficial sintética').length).toBeGreaterThan(0)
})

test('aviso do Senador quando a API indica duas escolhas', async () => {
  renderApp('/?cargo=5&uf=XX')
  expect(
    await screen.findByText('Cada eleitor pôde votar em até 2 candidaturas; o total de votos não equivale ao número de votantes.'),
  ).toBeInTheDocument()
})

test('branco e nulo não aparecem como candidatura no ranking padrão', async () => {
  renderApp('/')
  expect(await screen.findByText('Opção sintética Alfa')).toBeInTheDocument()
  expect(screen.queryByText('Branco sintético')).not.toBeInTheDocument()
  expect(screen.queryByText('Nulo sintético')).not.toBeInTheDocument()
  await userEvent.click(screen.getByLabelText('Incluir branco, nulo e legenda'))
  await waitFor(() => {
    expect(screen.getByText('Branco sintético')).toBeInTheDocument()
    expect(screen.getByText('Nulo sintético')).toBeInTheDocument()
  })
})
