import type { ReactNode } from 'react'
import { useSyncedScroll } from '../lib/useSyncedScroll'

interface Props {
  markup: string
  filename: string
  ratio: number
  onRatio: (r: number) => void
}

const TAG_RE = /\[D>([\s\S]*?)<D\]|\[A>([\s\S]*?)<A\]/g

/** Render one line of raw markup with the tag contents colored and the
 *  [D>../<D] / [A>../<A] brackets dimmed. */
function rawLine(text: string): ReactNode {
  const parts: ReactNode[] = []
  let last = 0
  let m: RegExpExecArray | null
  let k = 0
  TAG_RE.lastIndex = 0
  while ((m = TAG_RE.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    const isDel = m[1] !== undefined
    const inner = isDel ? m[1] : m[2]
    parts.push(
      <span key={k++} className={isDel ? 'raw-del' : 'raw-add'}>
        <span className="tok">{isDel ? '[D>' : '[A>'}</span>
        {inner}
        <span className="tok">{isDel ? '<D]' : '<A]'}</span>
      </span>,
    )
    last = TAG_RE.lastIndex
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts.length ? parts : '​'
}

export function RawMarkupPanel({ markup, filename, ratio, onRatio }: Props) {
  const { ref, handleScroll } = useSyncedScroll(ratio, onRatio)
  const lines = markup.split('\n')

  function download() {
    const blob = new Blob([markup], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    a.click()
  }

  return (
    <div className="panel panel-dark">
      <div className="panel-header">
        <span className="panel-title">Markup</span>
        <button className="download-btn" onClick={download}>Download</button>
      </div>
      <div className="panel-body code-body" ref={ref} onScroll={handleScroll}>
        {lines.map((line, i) => (
          <div className="code-row" key={i}>
            <span className="ln">{i + 1}</span>
            <span className="code-content">{rawLine(line)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
