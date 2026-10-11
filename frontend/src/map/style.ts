export const MINIMAL_STYLE = {
  version: 8 as const,
  name: 'atlas-minimo',
  sources: {},
  layers: [
    {
      id: 'background',
      type: 'background' as const,
      paint: { 'background-color': '#f1f5f9' },
    },
  ],
}
