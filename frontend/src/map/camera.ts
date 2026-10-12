export type MapGrain = 'uf' | 'municipio' | 'local'

export function cameraFor(mode: '2d' | '3d', grain: MapGrain = 'uf') {
  if (mode === '2d') {
    return {
      pitch: 0,
      bearing: 0,
      padding: grain === 'local' ? 72 : 40,
      maxZoom: grain === 'local' ? 11.2 : grain === 'municipio' ? 8.2 : 5.8,
    }
  }
  return {
    pitch: grain === 'local' ? 42 : grain === 'municipio' ? 48 : 52,
    bearing: grain === 'local' ? -6 : -18,
    padding: grain === 'local' ? 88 : grain === 'municipio' ? 48 : 56,
    maxZoom: grain === 'local' ? 11.4 : grain === 'municipio' ? 7.8 : 5.6,
  }
}

export const EXTRUSION_HEIGHT = [
  'interpolate',
  ['linear'],
  ['zoom'],
  3.2,
  180000,
  5.2,
  90000,
  6.4,
  28000,
  8,
  9000,
  10,
  1800,
  12,
  400,
] as const

export const LINE_WIDTH = [
  'interpolate',
  ['linear'],
  ['zoom'],
  3.2,
  0.7,
  5.5,
  1.1,
  7.2,
  1.6,
  9.5,
  2.2,
  11.5,
  2.8,
] as const
