/// <reference types="vite/client" />
/// <reference types="vitest/config" />
/// <reference types="@testing-library/jest-dom" />
/// <reference types="geojson" />

declare module 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url' {
  const workerUrl: string
  export default workerUrl
}

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
