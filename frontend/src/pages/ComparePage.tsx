import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Filters } from '../components/Filters'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../components/QueryState'
import { SourceMeta } from '../components/SourceMeta'
import { useCompare, useRanking } from '../hooks/useAtlasQueries'
import { useScopeParams } from '../hooks/useScopeParams'
import { canFetchResults, needsUf } from '../lib/scope'
import { formatInt, formatPctShort } from '../lib/format'

export default function ComparePage() {
  const { scope, update } = useScopeParams()
  const ranking = useRanking({ ...scope, municipio: '' }, 'candidatura', 1, 80)
  const selected = scope.option.split(',').filter(Boolean).slice(0, 3)
  const compare = useCompare(scope, selected.join(','))
  const ready = canFetchResults({ ...scope, municipio: '' })

  function toggle(id: string) {
    const set = new Set(selected)
    if (set.has(id)) set.delete(id)
    else if (set.size < 3) set.add(id)
    update({ option: [...set].join(',') })
  }

  const chartData = (compare.data?.data.options ?? []).map((opt) => ({
    name: opt.label,
    votos: opt.qt_votos_validos,
    fill: opt.color || '#1d4ed8',
  }))

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Comparar candidaturas</h1>
      <Filters />
      {!ready && needsUf(scope.cargo) && <EmptyBlock>Para este cargo informe a UF.</EmptyBlock>}
      {ranking.isPending && <LoadingBlock />}
      {ranking.isError && <ErrorBlock error={ranking.error} />}
      {ranking.data && (
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Até 3 candidaturas da mesma disputa</legend>
          <div className="grid max-h-64 gap-1 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-sm">
            {ranking.data.data.filter((row) => row.kind === 'candidatura').map((row) => (
              <label key={row.option_id} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={selected.includes(String(row.option_id))}
                  onChange={() => toggle(String(row.option_id))}
                />
                {row.nr_votavel} — {row.label} ({row.sg_partido ?? 's/ partido'})
              </label>
            ))}
          </div>
        </fieldset>
      )}
      {selected.length === 0 && <EmptyBlock>Selecione ao menos uma candidatura para comparar.</EmptyBlock>}
      {compare.isPending && selected.length > 0 && <LoadingBlock />}
      {compare.isError && <ErrorBlock error={compare.error} />}
      {compare.data && (
        <>
          <SourceMeta meta={compare.data.meta} />
          <div className="h-72 rounded-lg border border-slate-200 bg-white p-3" aria-hidden>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip formatter={(value) => formatInt(Number(value))} />
                <Legend />
                <Bar dataKey="votos" name="Votos válidos" fill="#1d4ed8" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <caption className="sr-only">Comparação por município</caption>
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-2 py-2">Município</th>
                  <th className="px-2 py-2">UF</th>
                  {compare.data.data.options.map((opt) => (
                    <th key={opt.option_id} className="px-2 py-2">{opt.label} (% válidos)</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {compare.data.data.municipalities.slice(0, 200).map((mun) => (
                  <tr key={mun.cd_municipio_tse} className="border-t border-slate-100">
                    <td className="px-2 py-1.5">{mun.nm_municipio}</td>
                    <td className="px-2 py-1.5">{mun.sg_uf}</td>
                    {compare.data.data.options.map((opt) => {
                      const value = mun.values[String(opt.option_id)]
                      return (
                        <td key={opt.option_id} className="px-2 py-1.5 tabular-nums">
                          {formatInt(value?.qt_votos_validos)} · {formatPctShort(value?.pct_validos ?? null)}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {compare.data.data.municipalities.length > 200 && (
            <p className="text-xs text-slate-500">Exibindo os 200 primeiros municípios da resposta da API.</p>
          )}
        </>
      )}
    </div>
  )
}
