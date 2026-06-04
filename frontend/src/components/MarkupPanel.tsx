import { parseMarkup } from '../lib/parseMarkup'
import { useSyncedScroll } from '../lib/useSyncedScroll'

interface Props {
  markup: string
  filename: string
  ratio: number
  onRatio: (r: number) => void
}

/** Rendered preview: deletions struck through in red, additions in green, with a
 *  line-number gutter aligned to the raw markup panel. */
export function MarkupPanel({ markup, filename, ratio, onRatio }: Props) {
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
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Preview</span>
        <button className="download-btn" onClick={download}>Download</button>
      </div>
      <div className="panel-body render-body" ref={ref} onScroll={handleScroll}>
        {lines.map((line, i) => (
          <div className="render-row" key={i}>
            <span className="ln">{i + 1}</span>
            <span className="render-content">
              {parseMarkup(line).map((seg, j) => {
                if (seg.type === 'deletion')
                  return <span key={j} className="deletion">{seg.text}</span>
                if (seg.type === 'addition')
                  return <span key={j} className="addition">{seg.text}</span>
                return <span key={j}>{seg.text}</span>
              })}
              {line === '' && '​'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
