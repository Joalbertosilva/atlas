import { CoverageBadge } from '../components/CoverageBadge'
import { ErrorBlock, LoadingBlock } from '../components/QueryState'
import { useCoverage } from '../hooks/useAtlasQueries'
import { formatDateTime, formatInt } from '../lib/format'

export default function CoveragePage() {
  const coverage = useCoverage()
  const data = coverage.data?.data

  return (
    <article className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Fontes, metodologia e cobertura</h1>
      <section className="space-y-2 text-sm leading-6 text-slate-700">
        <p>
          Os resultados vêm dos arquivos de totalização do TSE (Dados Abertos), por turno. Não há atualização contínua:
          a data exibida é a de geração declarada no arquivo e a da importação local.
        </p>
        <p>
          Geometrias municipais e estaduais vêm da API de Malhas do IBGE v3 (qualidade mínima), licença CC-BY.
          O mapa une geometria e resultados pelo código IBGE do município.
        </p>
        <p>
          Percentuais usam denominadores explícitos: comparecimento sobre aptos; votos válidos da opção sobre o total de
          válidos do recorte; nos cargos proporcionais, também sobre os nominais válidos. Branco, nulo e legenda não são
          candidaturas. O ranking não define eleitos: a situação vem do campo oficial DS_SIT_TOT_TURNO.
        </p>
        <p>
          Totais oficiais usam a agregação município/zona. Votos por seção são exibidos à parte e podem não separar
          válidos de anulados sub judice. Exterior (ZZ) entra nos totais da Presidência e fica fora do mapa.
        </p>
      </section>
      {coverage.isPending && <LoadingBlock />}
      {coverage.isError && <ErrorBlock error={coverage.error} />}
      {data && (
        <>
          <CoverageBadge coverage={coverage.data?.meta.coverage} />
          {data.groups && (
            <section>
              <h2 className="mb-2 text-base font-semibold">Grupos de publicação</h2>
              <ul className="grid gap-2 sm:grid-cols-2">
                {data.groups.map((group) => (
                  <li key={group.group} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
                    <p className="font-medium">{group.group}</p>
                    <p>{group.status} · {group.published}/{group.expected}</p>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <section className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <caption className="sr-only">Recortes importados</caption>
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-2 py-2">Recorte</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Linhas</th>
                  <th className="px-2 py-2">Gerado pelo TSE em</th>
                  <th className="px-2 py-2">Importado em</th>
                </tr>
              </thead>
              <tbody>
                {data.scopes.map((scope) => (
                  <tr key={`${scope.scope ?? scope.kind}-${scope.sg_uf ?? ''}`} className="border-t border-slate-100">
                    <td className="px-2 py-1.5">{scope.scope ?? `${scope.kind ?? ''} ${scope.sg_uf ?? ''}`}</td>
                    <td className="px-2 py-1.5">{scope.status}</td>
                    <td className="px-2 py-1.5">{formatInt(scope.rows)}</td>
                    <td className="px-2 py-1.5">{formatDateTime(scope.source_generated_at)}</td>
                    <td className="px-2 py-1.5">{formatDateTime(scope.imported_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section>
            <h2 className="mb-2 text-base font-semibold">Reconciliação</h2>
            <ul className="space-y-1 text-sm">
              {data.reconciliation.map((row) => (
                <li key={row.check_name}>
                  {row.check_name}: {row.ok}/{row.total} ok
                  {row.examples && row.examples.length > 0 ? ` · exemplos: ${row.examples.join(', ')}` : ''}
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h2 className="mb-2 text-base font-semibold">Pendências</h2>
            {data.pending.length === 0 ? (
              <p className="text-sm text-slate-600">Nenhuma pendência listada pela API.</p>
            ) : (
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {data.pending.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </article>
  )
}
