import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { SYNTHETIC_SEARCH_HITS, jsonResponse } from '../test/fixtures.synthetic'
import { renderApp } from '../test/render'

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  fetchMock.mockResolvedValue(jsonResponse(SYNTHETIC_SEARCH_HITS))
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('página de pesquisa envia POST e não coloca a consulta na URL', async () => {
  const user = userEvent.setup()
  renderApp('/pesquisa')
  expect(await screen.findByText(/Confirme notícias sobre candidatos/)).toBeInTheDocument()
  const input = await screen.findByLabelText('Consulta')
  await user.type(input, 'consulta sintetica privada')
  await user.click(screen.getByRole('button', { name: 'Buscar' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalled())
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(url).toMatch(/\/search\/news$/)
  expect(init.method).toBe('POST')
  expect(String(init.body)).toContain('consulta sintetica privada')
  expect(window.location.search.includes('consulta')).toBe(false)
  expect(document.location.href.includes('consulta sintetica privada')).toBe(false)
})

test('trechos com HTML são exibidos como texto', async () => {
  const user = userEvent.setup()
  renderApp('/pesquisa')
  await user.type(await screen.findByLabelText('Consulta'), 'abc')
  await user.click(screen.getByRole('button', { name: 'Buscar' }))
  const snippet = await screen.findByText(/Trecho com/)
  expect(snippet.textContent).toContain('<script>alert(1)</script>')
  expect(snippet.querySelector('script')).toBeNull()
})

test('estado de provedor indisponível é exibido', async () => {
  const user = userEvent.setup()
  renderApp('/pesquisa')
  await user.type(await screen.findByLabelText('Consulta'), 'abc')
  await user.click(screen.getByRole('button', { name: 'Buscar' }))
  expect(await screen.findByText(/Provedor mecanismo-ausente: indisponivel/)).toBeInTheDocument()
  expect(screen.getByText(/timeout sintético/)).toBeInTheDocument()
})

test('datas ausentes mostram data não informada', async () => {
  const user = userEvent.setup()
  renderApp('/pesquisa')
  await user.type(await screen.findByLabelText('Consulta'), 'abc')
  await user.click(screen.getByRole('button', { name: 'Buscar' }))
  expect(await screen.findByText('data não informada')).toBeInTheDocument()
})
