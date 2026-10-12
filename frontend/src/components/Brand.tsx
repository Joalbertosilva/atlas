import { Link } from 'react-router'

export function Mark({ className = 'h-8 w-8', title = 'Atlas Eleitoral' }: { className?: string; title?: string }) {
  return (
    <img
      src="/logo-mark.png"
      alt={title}
      width={64}
      height={64}
      className={`bg-transparent object-contain ${className}`}
    />
  )
}

export function Wordmark({ size = 'nav' }: { size?: 'nav' | 'hero' }) {
  const cls = size === 'hero' ? 'h-12 w-auto max-w-[12rem] sm:h-14' : 'h-10 w-auto max-w-[14rem] sm:h-11'
  return (
    <img
      src="/logo-atlas.png"
      alt="Atlas Eleitoral 2026"
      width={640}
      height={160}
      className={`${cls} bg-transparent object-contain object-left`}
    />
  )
}

export function BrandLockup({ to = '/' }: { to?: string }) {
  return (
    <Link to={to} className="inline-flex items-center gap-3 rounded-sm focus-visible:outline focus-visible:outline-2">
      <Mark className="h-10 w-10 shrink-0" title="" />
      <span className="flex flex-col leading-tight">
        <span className="text-sm font-semibold tracking-wide text-white">Atlas Eleitoral</span>
        <span className="text-xs text-slate-300">Eleição 2026</span>
      </span>
    </Link>
  )
}
