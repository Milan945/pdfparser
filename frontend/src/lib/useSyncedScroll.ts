import { useEffect, useRef } from 'react'

/**
 * Keep several scroll containers aligned by proportional position.
 *
 * Each panel calls this with the shared scroll `ratio` (0..1) and a setter. When
 * the panel is scrolled by the user it reports its ratio; when another panel
 * reports, this one follows. An `applying` guard prevents the programmatic
 * scroll from echoing back into a feedback loop.
 */
export function useSyncedScroll(ratio: number, onRatio: (r: number) => void) {
  const ref = useRef<HTMLDivElement>(null)
  const applying = useRef(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const max = el.scrollHeight - el.clientHeight
    const target = ratio * max
    if (Math.abs(el.scrollTop - target) < 1) return
    applying.current = true
    el.scrollTop = target
    requestAnimationFrame(() => {
      applying.current = false
    })
  }, [ratio])

  function handleScroll() {
    if (applying.current) return
    const el = ref.current
    if (!el) return
    const max = el.scrollHeight - el.clientHeight
    onRatio(max > 0 ? el.scrollTop / max : 0)
  }

  return { ref, handleScroll }
}
