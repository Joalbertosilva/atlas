import { expect, test } from 'vitest'
import { PL_YELLOW, PT_RED, partyColor } from './partyColors'

test('PT é vermelho e PL é amarelo', () => {
  expect(partyColor('PT', '13')).toBe(PT_RED)
  expect(partyColor('PL', '22')).toBe(PL_YELLOW)
  expect(partyColor(null, '22')).toBe(PL_YELLOW)
  expect(partyColor('MISSÃO')).toBe('#C2410C')
})
