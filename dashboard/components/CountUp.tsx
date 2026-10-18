'use client'

import { useEffect, useRef, useState } from 'react'

/**
 * Animates a number from 0 to `value` over `duration` ms when it first
 * becomes visible. `format` controls rendering (e.g. currency, percent).
 */
export default function CountUp({
  value,
  duration = 1200,
  format = (n: number) => Math.round(n).toString(),
}: {
  value: number
  duration?: number
  format?: (n: number) => string
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const [display, setDisplay] = useState(0)
  const started = useRef(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    let raf = 0
    let fallback: ReturnType<typeof setTimeout>
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting || started.current) return
        started.current = true
        const start = performance.now()
        const tick = () => {
          const t = Math.min((performance.now() - start) / duration, 1)
          // ease-out cubic
          const eased = 1 - Math.pow(1 - t, 3)
          setDisplay(value * eased)
          if (t < 1) raf = requestAnimationFrame(tick)
        }
        raf = requestAnimationFrame(tick)
        // Browsers throttle rAF in occluded/unfocused tabs — guarantee the
        // final value lands regardless of frame delivery.
        fallback = setTimeout(() => setDisplay(value), duration + 200)
        observer.disconnect()
      },
      { threshold: 0.5 },
    )
    observer.observe(el)
    return () => {
      observer.disconnect()
      cancelAnimationFrame(raf)
      clearTimeout(fallback)
    }
  }, [value, duration])

  return <span ref={ref}>{format(display)}</span>
}
