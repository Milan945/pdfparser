import React, { useRef } from 'react'
import { parseMarkup } from '../lib/parseMarkup'

interface Props {
  markup: string
  filename: string
  onScrollRatio: (ratio: number) => void
}

export function MarkupPanel({ markup, filename, onScrollRatio }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  function handleScroll() {
    const el = ref.current
    if (!el) return
    const max = el.scrollHeight - el.clientHeight
    onScrollRatio(max > 0 ? el.scrollTop / max : 0)
  }

  const segments = parseMarkup(markup)

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Markup Preview</span>
        <a
          className="download-btn"
          href={URL.createObjectURL(new Blob([markup], { type: 'text/plain' }))}
          download={filename}
        >
          Download
        </a>
      </div>
      <div className="panel-body" ref={ref} onScroll={handleScroll}>
        {segments.length === 0 && (
          <p className="empty-notice">No amendment markup detected.</p>
        )}
        {segments.map((seg, i) => {
          if (seg.type === 'deletion') {
            return (
              <span key={i} className="deletion">{seg.text}</span>
            )
          }
          if (seg.type === 'addition') {
            return (
              <span key={i} className="addition">{seg.text}</span>
            )
          }
          return <span key={i}>{seg.text}</span>
        })}
      </div>
    </div>
  )
}
