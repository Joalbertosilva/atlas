import { NavLink, Outlet } from 'react-router'
import { BrandLockup, Mark } from './Brand'

const NAV = [
  { to: '/', label: 'Resultados', end: true },
  { to: '/mapa', label: 'Mapa' },
  { to: '/explorar', label: 'Explorar' },
  { to: '/comparar', label: 'Comparar' },
  { to: '/evolucao', label: 'Pesquisas' },
  { to: '/pesquisa', label: 'Busca' },
  { to: '/cobertura', label: 'Cobertura' },
]

function navClass({ isActive }: { isActive: boolean }) {
  return [
    'inline-flex items-center rounded-md px-3 py-1.5 text-sm font-medium',
    isActive ? 'bg-white text-atlas-900' : 'text-slate-200 hover:bg-white/10',
  ].join(' ')
}

export function Layout() {
  return (
    <div className="min-h-screen">
      <a className="skip-link" href="#conteudo">
        Ir para o conteúdo
      </a>
      <header className="border-b border-slate-800 bg-atlas-900 text-white">
        <div className="mx-auto flex max-w-7xl min-w-0 flex-col gap-4 px-4 py-4 sm:px-6">
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-4">
            <BrandLockup />
            <p className="max-w-sm text-xs leading-relaxed text-slate-300">
              Painel independente com dados públicos do TSE e IBGE. Não é um site oficial da Justiça Eleitoral.
            </p>
          </div>
          <nav aria-label="Principal" className="flex flex-wrap items-center gap-1">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main id="conteudo" className="mx-auto max-w-7xl min-w-0 overflow-x-hidden px-4 py-6 sm:px-6">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-4 py-4 text-xs text-slate-600 sm:px-6">
          <Mark className="h-6 w-6" />
          <NavLink to="/privacidade" className="underline-offset-2 hover:underline">
            Privacidade
          </NavLink>
          <NavLink to="/cobertura" className="underline-offset-2 hover:underline">
            Fontes e metodologia
          </NavLink>
          <span>Dados de totalização por turno — não é tempo real.</span>
        </div>
      </footer>
    </div>
  )
}
