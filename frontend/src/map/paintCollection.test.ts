import { expect, test } from 'vitest'
import type { GeometryProperties, LeaderMunicipality } from '../api/types'
import { SYNTHETIC_MUNICIPALITIES } from '../test/fixtures.synthetic'
import { NO_DATA_COLOR, TIE_COLOR } from '../lib/mapColors'
import { paintCollection } from './paintCollection'
import { atlasStyle, colorIndexCollection } from './style'

const ufGeometry: GeoJSON.FeatureCollection<GeoJSON.Geometry, GeometryProperties> = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { sg_uf: 'XX', nm_uf: 'Unidade sintética', cd_uf_ibge: '00' },
      geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] },
    },
  ],
}

const munGeometry: GeoJSON.FeatureCollection<GeoJSON.Geometry, GeometryProperties> = {
  type: 'FeatureCollection',
  features: SYNTHETIC_MUNICIPALITIES.data.map((row, i) => ({
    type: 'Feature' as const,
    properties: {
      cd_municipio_ibge: row.cd_municipio_ibge ?? undefined,
      cd_municipio_tse: row.cd_municipio_tse,
      nm_municipio: row.nm_municipio,
      sg_uf: row.sg_uf,
    },
    geometry: {
      type: 'Polygon' as const,
      coordinates: [[[i, 0], [i + 1, 0], [i + 1, 1], [i, 1], [i, 0]]],
    },
  })),
}

test('município recebe a cor da candidatura que venceu, empate e vazio fixos', () => {
  const painted = paintCollection(munGeometry, SYNTHETIC_MUNICIPALITIES.data, 'leader')
  const byName = Object.fromEntries(painted.features.map((f) => [f.properties.nm_municipio, f.properties.fill]))
  expect(byName['Cidade sintética Um']).toBe('#1d4ed8')
  expect(byName['Cidade sintética Empate']).toBe(TIE_COLOR)
  expect(byName['Cidade sintética Sem Dados']).toBe(NO_DATA_COLOR)
})

test('UF usa o líder estadual (agg.result_state), não o município', () => {
  const stateRows: LeaderMunicipality[] = [
    {
      cd_municipio_tse: '',
      cd_municipio_ibge: null,
      nm_municipio: 'Unidade sintética',
      sg_uf: 'XX',
      is_exterior: false,
      leader: { option_id: 102, label: 'Opção sintética Beta', color: '#dc2626', qt_votos_validos: 90, pct_validos: 60 },
      second: { option_id: 101, label: 'Opção sintética Alfa', color: '#1d4ed8', qt_votos_validos: 60, pct_validos: 40 },
      tie: false,
      tied_option_ids: [],
      margin_votes: 30,
      margin_pp: 20,
      qt_total_votos_validos: 150,
    },
  ]
  const painted = paintCollection(ufGeometry, stateRows, 'leader')
  expect(painted.features).toHaveLength(1)
  expect(painted.features[0]?.properties.fill).toBe('#dc2626')
  expect(painted.features[0]?.properties.atlasFill).toBe('#dc2626')
  expect(painted.features[0]?.properties.tooltip).toContain('Opção sintética Beta')
  expect(painted.features[0]?.properties.tooltip).toContain('2º Opção sintética Alfa')
})

test('mapa no modo candidatura usa a cor da própria candidatura', () => {
  const painted = paintCollection(
    munGeometry,
    [
      {
        cd_municipio_tse: '00001',
        cd_municipio_ibge: '0000001',
        nm_municipio: 'Cidade sintética Um',
        sg_uf: 'XX',
        is_exterior: false,
        qt_votos_validos: 80,
        pct_validos: 90,
        qt_total_votos_validos: 100,
      },
    ],
    'candidate',
    [{ min: 0, max: 20 }, { min: 20, max: 40 }, { min: 40, max: 60 }, { min: 60, max: 80 }, { min: 80, max: 100 }],
    '#F5C400',
  )
  expect(painted.features[0]?.properties.fill.toLowerCase()).toBe('#f5c400')
})

test('estilo 3D usa extrusão e índice numérico de cor', () => {
  const painted = paintCollection(ufGeometry, [{
    cd_municipio_tse: '',
    cd_municipio_ibge: null,
    nm_municipio: 'Unidade sintética',
    sg_uf: 'XX',
    is_exterior: false,
    leader: { option_id: 102, label: 'Opção sintética Beta', color: '#dc2626', qt_votos_validos: 90, pct_validos: 60 },
    second: null,
    tie: false,
    tied_option_ids: [],
    margin_votes: null,
    margin_pp: null,
    qt_total_votos_validos: 150,
  }], 'leader')
  const indexed = colorIndexCollection(painted)
  expect(indexed.data.features[0]?.properties.ci).toBe(0)
  expect(indexed.colorExpr).toContain('#dc2626')
  const style = atlasStyle(painted, '3d')
  expect(style.layers.some((layer) => layer.type === 'fill-extrusion')).toBe(true)
  expect(style.layers.some((layer) => layer.type === 'fill' && layer.id === 'atlas-fill')).toBe(true)
})
