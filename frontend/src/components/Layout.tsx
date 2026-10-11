import { NavLink, Outlet } from 'react-router'

const NAV = [
  { to: '/', label: 'Início', end: true },
  { to: '/mapa', label: 'Mapa' },
  { to: '/explorar', label: 'Explorar' },
  { to: '/comparar', label: 'Comparar' },
  { to: '/pesquisa', label: 'Pesquisa' },
  { to: '/cobertura', label: 'Cobertura' },
]

function navClass({ isActive }: { isActive: boolean }) {
  return [
    'rounded-md px-2.5 py-1.5 text-sm',
    isActive ? 'bg-atlas-800 text-white' : 'text-slate-700 hover:bg-slate-100',
  ].join(' ')
}

export function Layout() {
  return (
    <div className="min-h-screen">
      <a className="skip-link" href="#conteudo">
        Ir para o conteúdo
      </a>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4 sm:px-6">
          <div>
            <p className="text-lg font-semibold tracking-tight text-atlas-800">Atlas Eleitoral 2026</p>
            <p className="text-sm text-slate-600">Painel independente com dados públicos do TSE e IBGE</p>
            <p className="text-xs text-slate-500">Não é um site oficial da Justiça Eleitoral</p>
          </div>
          <nav aria-label="Principal" className="flex flex-wrap gap-1">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main id="conteudo" className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap gap-4 px-4 py-4 text-xs text-slate-600 sm:px-6">
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
