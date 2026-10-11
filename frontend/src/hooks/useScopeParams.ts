import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { readScope, writeScope, type ScopeState } from '../lib/scope'

export function useScopeParams() {
  const [params, setParams] = useSearchParams()
  const scope = useMemo(() => readScope(params), [params])

  const update = useCallback(
    (patch: Partial<ScopeState>) => {
      setParams(writeScope(params, patch), { replace: true })
    },
    [params, setParams],
  )

  return { scope, update, searchParams: params, setSearchParams: setParams }
}
