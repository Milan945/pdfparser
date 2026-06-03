import React, { useEffect, useRef } from 'react'
import * as pdfjsLib from 'pdfjs-dist'

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface Props {
  sessionId: string
  scrollRatio: number
}

export function PdfPanel({ sessionId, scrollRatio }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = bodyRef.current
    if (!container) return
    container.innerHTML = ''

    let cancelled = false
    pdfjsLib.getDocument(`/pdf/${sessionId}`).promise.then(async (pdf) => {
      for (let i = 1; i <= pdf.numPages; i++) {
        if (cancelled) break
        const page = await pdf.getPage(i)
        const viewport = page.getViewport({ scale: 1.2 })
        const canvas = document.createElement('canvas')
        canvas.width = viewport.width
        canvas.height = viewport.height
        canvas.style.display = 'block'
        canvas.style.marginBottom = '8px'
        container.appendChild(canvas)
        await page.render({ canvasContext: canvas.getContext('2d')!, viewport }).promise
      }
    })

    return () => { cancelled = true }
  }, [sessionId])

  useEffect(() => {
    const el = bodyRef.current
    if (!el) return
    const max = el.scrollHeight - el.clientHeight
    el.scrollTop = scrollRatio * max
  }, [scrollRatio])

  return (
    <div className="panel" ref={containerRef}>
      <div className="panel-header">
        <span className="panel-title">PDF Viewer</span>
      </div>
      <div className="panel-body" ref={bodyRef} />
    </div>
  )
}
