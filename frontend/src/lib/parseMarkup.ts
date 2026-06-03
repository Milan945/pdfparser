export type Segment = {
  type: 'plain' | 'deletion' | 'addition'
  text: string
}

const TAG_RE = /\[D>([\s\S]*?)<D\]|\[A>([\s\S]*?)<A\]/g

export function parseMarkup(markup: string): Segment[] {
  if (!markup) return []
  const segments: Segment[] = []
  let last = 0
  let match: RegExpExecArray | null

  TAG_RE.lastIndex = 0
  while ((match = TAG_RE.exec(markup)) !== null) {
    if (match.index > last) {
      segments.push({ type: 'plain', text: markup.slice(last, match.index) })
    }
    if (match[1] !== undefined) {
      segments.push({ type: 'deletion', text: match[1] })
    } else {
      segments.push({ type: 'addition', text: match[2] })
    }
    last = TAG_RE.lastIndex
  }

  if (last < markup.length) {
    segments.push({ type: 'plain', text: markup.slice(last) })
  }

  return segments
}
