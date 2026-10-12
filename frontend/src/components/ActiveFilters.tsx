import { useOffices, useStates } from '../hooks/useAtlasQueries'
import { useScopeParams } from '../hooks/useScopeParams'
import { needsUf } from '../lib/scope'

export function ActiveFilters() {
  const { scope, update } = useScopeParams()
  const offices = useOffices()
  const states = useStates()
  const cargoLabel = offices.data?.data.find((o) => o.cd_cargo === scope.cargo)?.ds_cargo ?? `Cargo ${scope.cargo}`
  const ufLabel = scope.uf
    ? (states.data?.data.find((s) => s.sg_uf === scope.uf)?.nm_uf ?? scope.uf)
    : (needsUf(scope.cargo) ? 'Todos os estados' : 'Brasil')
  const chips = [
    { key: 'cargo', label: cargoLabel, clear: undefined },
    { key: 'ano', label: String(scope.ano), clear: scope.ano === 2022 ? () => update({ ano: 2026, option: '' }) : undefined },
    { key: 'turno', label: scope.turno === 2 ? '2º turno' : '1º turno', clear: undefined },
    { key: 'uf', label: ufLabel, clear: scope.uf ? () => update({ uf: '', municipio: '', option: '' }) : undefined },
    scope.municipio
      ? { key: 'municipio', label: `Município ${scope.municipio}`, clear: () => update({ municipio: '' }) }
      : null,
  ].filter(Boolean) as Array<{ key: string; label: string; clear?: () => void }>

  const canClear = Boolean(scope.uf || scope.municipio || scope.turno === 2 || scope.cargo !== '1' || scope.option)

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <p className="font-medium text-slate-800">Recorte ativo</p>
      {chips.map((chip) => (
        <span key={chip.key} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-slate-800">
          {chip.label}
          {chip.clear && (
            <button type="button" className="text-slate-500 hover:text-slate-900" onClick={chip.clear} aria-label={`Limpar ${chip.label}`}>
              ×
            </button>
          )}
        </span>
      ))}
      {canClear && (
        <button
          type="button"
          className="text-xs text-atlas-700 underline"
          onClick={() => update({ cargo: '1', turno: 1, uf: '', municipio: '', option: '', modo: 'leader', ano: 2026 })}
        >
          Limpar filtros
        </button>
      )}
    </div>
  )
}
