import { expect, test } from 'vitest'
import { SYNTHETIC_MUNICIPALITIES } from '../test/fixtures.synthetic'
import {
  NO_DATA_COLOR,
  NO_DATA_LABEL,
  TIE_COLOR,
  TIE_LABEL,
  fillForLeaderRow,
  leaderLegendItems,
} from './mapColors'
import type { LeaderLegend } from '../api/types'

test('empate e sem dados usam cores fixas na função de preenchimento', () => {
  const [leader, tie, empty] = SYNTHETIC_MUNICIPALITIES.data
  expect(fillForLeaderRow(leader)).toBe('#1d4ed8')
  expect(fillForLeaderRow(tie)).toBe(TIE_COLOR)
  expect(fillForLeaderRow(empty)).toBe(NO_DATA_COLOR)
  expect(fillForLeaderRow(undefined)).toBe(NO_DATA_COLOR)
  expect(TIE_COLOR).toBe('#374151')
  expect(NO_DATA_COLOR).toBe('#e5e7eb')
})

test('legenda do mapa inclui Empate e Sem dados', () => {
  const items = leaderLegendItems(SYNTHETIC_MUNICIPALITIES.meta.legend as LeaderLegend, SYNTHETIC_MUNICIPALITIES.data)
  expect(items.some((item) => item.label === TIE_LABEL && item.color === TIE_COLOR)).toBe(true)
  expect(items.some((item) => item.label === NO_DATA_LABEL && item.color === NO_DATA_COLOR)).toBe(true)
})
