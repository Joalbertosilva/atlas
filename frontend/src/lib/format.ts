const numberFmt = new Intl.NumberFormat('pt-BR')
const percentFmt = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const dateTimeFmt = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'short',
})

export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return numberFmt.format(value)
}

export function formatPct(value: number | null | undefined, suffix = '% dos votos válidos'): string {
  if (value === null || value === undefined) return '—'
  return `${percentFmt.format(value)} ${suffix}`
}

export function formatPctShort(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${percentFmt.format(value)}%`
}

export function formatDateTime(value: string | null | undefined, missing = 'não informado'): string {
  if (!value) return missing
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return missing
  return dateTimeFmt.format(date)
}

export function formatTime(value: string | null | undefined): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

export function titleCaseMunicipio(name: string): string {
  return name
}
