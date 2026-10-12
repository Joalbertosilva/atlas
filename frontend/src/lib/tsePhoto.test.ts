import { expect, test } from 'vitest'
import { tseCandidatePhotoUrl } from './tsePhoto'

test('monta a URL oficial verificada de foto 2026', () => {
  expect(
    tseCandidatePhotoUrl({ ano: 2026, cdEleicao: '6257', sgUe: 'BR', sqCandidato: '280002551544' }),
  ).toBe('https://resultados.tse.jus.br/oficial/ele2026/6257/fotos/br/280002551544.jpeg')
  expect(
    tseCandidatePhotoUrl({ ano: 2026, cdEleicao: '6259', sgUe: 'SP', sqCandidato: '250002541303' }),
  ).toBe('https://resultados.tse.jus.br/oficial/ele2026/6259/fotos/sp/250002541303.jpeg')
})

test('2022 aponta para o proxy da API (ZIP oficial do CDN), sem inventar URL de 2022 no portal', () => {
  expect(
    tseCandidatePhotoUrl({ ano: 2022, cdEleicao: '544', sgUe: 'BR', sqCandidato: '280001607829' }),
  ).toBe('/api/photos/2022/BR/280001607829')
})

test('recusa código incompleto em vez de inventar caminho', () => {
  expect(tseCandidatePhotoUrl({ ano: 2026, cdEleicao: '6257', sgUe: 'BR', sqCandidato: '' })).toBeNull()
  expect(tseCandidatePhotoUrl({ ano: 2024, cdEleicao: '6257', sgUe: 'BR', sqCandidato: '280002551544' })).toBeNull()
})
