import { useEffect, useState } from 'react'
import { tseCandidatePhotoUrl } from '../lib/tsePhoto'

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] ?? ''}${parts[parts.length - 1][0] ?? ''}`.toUpperCase()
}

export function CandidatePhoto({
  name,
  ano,
  cdEleicao,
  sgUe,
  sqCandidato,
  color,
  size = 64,
}: {
  name: string
  ano?: number | string | null
  cdEleicao?: string | null
  sgUe?: string | null
  sqCandidato?: string | null
  color?: string | null
  size?: number
}) {
  const [failed, setFailed] = useState(false)
  const url = tseCandidatePhotoUrl({ ano, cdEleicao, sgUe, sqCandidato })
  useEffect(() => {
    setFailed(false)
  }, [url])
  const dim = { width: size, height: size }
  if (!url || failed) {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
        style={{ ...dim, background: color || '#16325c', fontSize: Math.max(11, size * 0.28) }}
        aria-hidden
      >
        {initials(name)}
      </span>
    )
  }
  return (
    <img
      src={url}
      alt=""
      width={size}
      height={size}
      className="shrink-0 overflow-hidden rounded-full object-cover ring-2 ring-white"
      style={dim}
      onError={() => setFailed(true)}
    />
  )
}
