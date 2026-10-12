import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
})

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal('ResizeObserver', ResizeObserverMock)

vi.mock('maplibre-gl', () => {
  class Map {
    constructor() {
      throw new Error('MapLibre indisponível no ambiente de teste sintético')
    }
  }
  class LngLatBounds {
    extend() {
      return this
    }
    isEmpty() {
      return true
    }
  }
  return { Map, NavigationControl: class {}, Popup: class {}, LngLatBounds }
})
