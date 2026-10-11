import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { Layout } from './components/Layout'
import { LoadingBlock } from './components/QueryState'
import DashboardPage from './pages/DashboardPage'
import CoveragePage from './pages/CoveragePage'
import PrivacyPage from './pages/PrivacyPage'
import SearchPage, { SearchPollsRedirect } from './pages/SearchPage'
import ComparePage from './pages/ComparePage'
import ExplorePage from './pages/ExplorePage'

const MapPage = lazy(() => import('./pages/MapPage'))

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route
          path="mapa"
          element={
            <Suspense fallback={<LoadingBlock label="Carregando mapa…" />}>
              <MapPage />
            </Suspense>
          }
        />
        <Route path="explorar" element={<ExplorePage />} />
        <Route path="comparar" element={<ComparePage />} />
        <Route path="pesquisa" element={<SearchPage />} />
        <Route path="pesquisas" element={<SearchPollsRedirect />} />
        <Route path="cobertura" element={<CoveragePage />} />
        <Route path="privacidade" element={<PrivacyPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
