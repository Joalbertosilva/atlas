import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import {
  SYNTHETIC_MUNICIPALITIES,
  SYNTHETIC_OFFICES,
  SYNTHETIC_RANKING,
  SYNTHETIC_STATES,
  SYNTHETIC_SUMMARY,
  SYNTHETIC_UF_LEADERS,
  jsonResponse,
} from '../test/fixtures.synthetic'
import { renderApp } from '../test/render'

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/offices')) return jsonResponse(SYNTHETIC_OFFICES)
      if (url.includes('/states')) return jsonResponse(SYNTHETIC_STATES)
      if (url.includes('/results/summary')) return jsonResponse(SYNTHETIC_SUMMARY)
      if (url.includes('/results/ranking')) return jsonResponse(SYNTHETIC_RANKING)
      if (url.includes('/results/uf-leaders')) return jsonResponse(SYNTHETIC_UF_LEADERS)
      if (url.includes('/results/municipalities')) return jsonResponse(SYNTHETIC_MUNICIPALITIES)
      if (url.includes('/map/geometry')) return jsonResponse({ type: 'FeatureCollection', features: [] })
      return jsonResponse({ error: { code: 'not_found', message: url } }, 404)
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('mapa mostra o recorte Brasil e deixa voltar ao estado sem sair da página', async () => {
  renderApp('/mapa')
  expect(await screen.findByRole('heading', { name: 'Mapa' })).toBeInTheDocument()
  const crumb = screen.getByRole('navigation', { name: 'Recorte do mapa' })
  expect(crumb).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Brasil' })).toBeInTheDocument()
  expect(crumb).not.toHaveTextContent('Acre')
  expect(screen.getByText(/Clique num estado para ver a divisão municipal/)).toBeInTheDocument()
})

test('município aberto no mapa mostra a ficha no mesmo recorte', async () => {
  renderApp('/mapa?uf=XX&municipio=00001')
  expect(await screen.findByRole('button', { name: 'Unidade sintética' })).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: /Cidade sintética Um/ })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Ver seções e locais deste município' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Brasil' }))
  expect(await screen.findByText(/Clique num estado para ver a divisão municipal/)).toBeInTheDocument()
})

test('Enter na busca entra no município sem sair do mapa', async () => {
  renderApp('/mapa?uf=XX')
  const search = await screen.findByLabelText('Buscar município no mapa')
  await userEvent.type(search, 'Cidade sintética Um{Enter}')
  expect(await screen.findByRole('heading', { name: /Cidade sintética Um/ })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Ver seções e locais deste município' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Unidade sintética' })).toBeInTheDocument()
})
