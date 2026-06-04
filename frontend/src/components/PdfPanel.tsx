import { useEffect } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
// Vite resolves the worker bundle to a served URL via the `?url` suffix. The
// previous `new URL('pdfjs-dist/build/...', import.meta.url)` form does NOT
// resolve a bare package specifier under Vite, so the worker 404'd and every
// getDocument() silently rejected -> blank panel.
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc

interface Props {
  sessionId: string
  ratio: number
  onRatio: (r: number) => void
}

import { useSyncedScroll } from '../lib/useSyncedScroll'

export function PdfPanel({ sessionId, ratio, onRatio }: Props) {
  const { ref, handleScroll } = useSyncedScroll(ratio, onRatio)

  useEffect(() => {
    const container = ref.current
    if (!container) return
    container.innerHTML = ''

    let cancelled = false
    pdfjsLib
      .getDocument({ url: `/pdf/${sessionId}` })
      .promise.then(async (pdf) => {
        for (let i = 1; i <= pdf.numPages; i++) {
          if (cancelled) break
          const page = await pdf.getPage(i)
          const viewport = page.getViewport({ scale: 1.4 })
          const canvas = document.createElement('canvas')
          canvas.width = viewport.width
          canvas.height = viewport.height
          canvas.className = 'pdf-page'
          container.appendChild(canvas)
          const ctx = canvas.getContext('2d')!
          await page.render({ canvas, canvasContext: ctx, viewport }).promise
        }
      })
      .catch((err) => {
        // Surface failures instead of leaving a silent blank panel.
        container.innerHTML = `<div class="panel-error">Could not render PDF: ${err?.message ?? err}</div>`
      })

    return () => {
      cancelled = true
    }
  }, [sessionId])

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">PDF Source</span>
      </div>
      <div className="panel-body pdf-body" ref={ref} onScroll={handleScroll} />
    </div>
  )
}
