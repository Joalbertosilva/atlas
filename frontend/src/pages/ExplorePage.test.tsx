import { screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { SYNTHETIC_OFFICES, SYNTHETIC_SECTION, SYNTHETIC_STATES, jsonResponse } from '../test/fixtures.synthetic'
import { renderApp } from '../test/render'

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/offices')) return jsonResponse(SYNTHETIC_OFFICES)
      if (url.includes('/states')) return jsonResponse(SYNTHETIC_STATES)
      if (url.includes('/sections/9/results')) return jsonResponse(SYNTHETIC_SECTION)
      if (url.includes('/zones')) return jsonResponse({ data: [], meta: {} })
      if (url.includes('/polling-places')) return jsonResponse({ data: [], meta: {} })
      if (url.includes('/sections')) return jsonResponse({ data: [], meta: {} })
      if (url.includes('/municipalities')) return jsonResponse({ data: [], meta: { pagination: { page: 1, page_size: 50, total: 0 } } })
      return jsonResponse({ error: { code: 'not_found', message: url } }, 404)
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('exploração mostra Local não identificado na base quando aplicável', async () => {
  renderApp('/explorar?uf=XX&municipio=00001&zona=1&secao=9')
  expect(await screen.findByText('Local não identificado na base')).toBeInTheDocument()
})
