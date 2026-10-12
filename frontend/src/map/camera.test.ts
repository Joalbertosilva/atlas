import { expect, test } from 'vitest'
import { cameraFor } from './camera'

test('o 3D deixa aproximar estado e município além do recorte nacional', () => {
  expect(cameraFor('3d', 'uf').maxZoom).toBeLessThan(cameraFor('3d', 'municipio').maxZoom)
  expect(cameraFor('3d', 'municipio').maxZoom).toBeLessThan(cameraFor('3d', 'local').maxZoom)
  expect(cameraFor('3d', 'local').maxZoom).toBeGreaterThan(11)
})
