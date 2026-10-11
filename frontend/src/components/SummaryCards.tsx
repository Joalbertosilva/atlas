import type { Summary, TurnoutBlock } from '../api/types'
import { formatInt, formatPctShort } from '../lib/format'
import { SENATOR_CARGO } from '../lib/scope'

function Card({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

function TurnoutGrid({ block, title }: { block: TurnoutBlock; title?: string }) {
  return (
    <section>
      {title && <h3 className="mb-2 text-sm font-semibold text-slate-800">{title}</h3>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Card label="Aptos" value={formatInt(block.qt_aptos)} hint="Denominador do comparecimento" />
        <Card
          label="Comparecimento"
          value={formatInt(block.qt_comparecimento)}
          hint={`${formatPctShort(block.pct_comparecimento)} dos aptos`}
        />
        <Card
          label="Abstenção"
          value={formatInt(block.qt_abstencoes)}
          hint={`${formatPctShort(block.pct_abstencao)} dos aptos`}
        />
        <Card
          label="Votos válidos"
          value={formatInt(block.qt_total_votos_validos)}
          hint="Nominais válidos + legenda válida"
        />
        <Card
          label="Brancos"
          value={formatInt(block.qt_votos_brancos)}
          hint={`${formatPctShort(block.pct_brancos)} dos votos (não é candidatura)`}
        />
        <Card
          label="Nulos"
          value={formatInt(block.qt_total_votos_nulos)}
          hint={`${formatPctShort(block.pct_nulos)} dos votos (não é candidatura)`}
        />
      </div>
    </section>
  )
}

export function SummaryCards({ data, cargo }: { data: Summary; cargo: string }) {
  const twoChoices = data.choices_per_voter === 2 || cargo === SENATOR_CARGO
  return (
    <div className="space-y-4">
      {twoChoices && (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          Cada eleitor pôde votar em até 2 candidaturas; o total de votos não equivale ao número de votantes.
        </p>
      )}
      <TurnoutGrid block={data} />
      {data.exterior && <TurnoutGrid block={data.exterior} title="Exterior" />}
    </div>
  )
}
