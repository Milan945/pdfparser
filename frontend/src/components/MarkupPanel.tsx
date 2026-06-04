import { useEffect, useRef } from 'react'
import { parseMarkup } from '../lib/parseMarkup'
import { useSyncedScroll } from '../lib/useSyncedScroll'

interface Props {
  markup: string
  filename: string
  ratio: number
  onRatio: (r: number) => void
}

const ZWSP = '​'

/** Walk up from a text node to find whether it sits inside a deletion/addition
 *  span, so edits inside a colored run round-trip back to the right tag. */
function classOf(node: Node, root: HTMLElement): 'deletion' | 'addition' | 'plain' {
  let el = node.parentElement
  while (el && el !== root) {
    if (el.classList.contains('deletion')) return 'deletion'
    if (el.classList.contains('addition')) return 'addition'
    el = el.parentElement
  }
  return 'plain'
}

/** Serialize one edited `.render-content` element back into NetScan markup. */
function serializeContent(el: HTMLElement): string {
  let out = ''
  let cur: 'deletion' | 'addition' | 'plain' | null = null
  let buf = ''
  const wrap = (cls: typeof cur, t: string) =>
    cls === 'deletion' ? `[D>${t}<D]` : cls === 'addition' ? `[A>${t}<A]` : t
  const flush = () => {
    if (buf !== '') {
      out += wrap(cur, buf)
      buf = ''
    }
  }
  const walk = (node: Node) => {
    node.childNodes.forEach(child => {
      if (child.nodeType === Node.TEXT_NODE) {
        const t = (child.textContent ?? '').split(ZWSP).join('')
        if (t === '') return
        const cls = classOf(child, el)
        if (cls !== cur) {
          flush()
          cur = cls
        }
        buf += t
      } else if (child.nodeType === Node.ELEMENT_NODE) {
        if ((child as HTMLElement).tagName !== 'BR') walk(child)
      }
    })
  }
  walk(el)
  flush()
  return out
}

/** Editable rendered view: deletions struck through in red, additions in green.
 *  The text is directly editable and edits re-serialize to markup for download. */
export function MarkupPanel({ markup, filename, ratio, onRatio }: Props) {
  const { ref, handleScroll } = useSyncedScroll(ratio, onRatio)
  const editedRef = useRef(markup)

  // Build the editable DOM once per markup. Keyed on `markup` only, so the
  // unrelated re-renders triggered by scroll syncing never clobber edits.
  useEffect(() => {
    editedRef.current = markup
    const body = ref.current
    if (!body) return
    body.replaceChildren()
    markup.split('\n').forEach((line, i) => {
      const row = document.createElement('div')
      row.className = 'render-row'

      const ln = document.createElement('span')
      ln.className = 'ln'
      ln.textContent = String(i + 1)
      ln.contentEditable = 'false'

      const content = document.createElement('span')
      content.className = 'render-content'
      content.contentEditable = 'true'
      content.spellcheck = false
      for (const seg of parseMarkup(line)) {
        if (seg.type === 'plain') {
          content.appendChild(document.createTextNode(seg.text))
        } else {
          const s = document.createElement('span')
          s.className = seg.type
          s.textContent = seg.text
          content.appendChild(s)
        }
      }
      if (line === '') content.appendChild(document.createTextNode(ZWSP))

      row.appendChild(ln)
      row.appendChild(content)
      body.appendChild(row)
    })
  }, [markup, ref])

  function recompute() {
    const body = ref.current
    if (!body) return
    const contents = body.querySelectorAll<HTMLElement>('.render-content')
    editedRef.current = Array.from(contents).map(serializeContent).join('\n')
  }

  function download() {
    recompute()
    const blob = new Blob([editedRef.current], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    a.click()
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Editor</span>
        <button className="download-btn" onClick={download}>Download</button>
      </div>
      <div
        className="panel-body render-body"
        ref={ref}
        onScroll={handleScroll}
        onInput={recompute}
        // Keep one logical line per row so the gutter stays aligned.
        onKeyDown={e => {
          if (e.key === 'Enter') e.preventDefault()
        }}
      />
    </div>
  )
}
