import { describe, it, expect } from 'vitest'
import { parseMarkup } from './parseMarkup'

describe('parseMarkup', () => {
  it('returns plain segment for plain text', () => {
    expect(parseMarkup('hello world')).toEqual([
      { type: 'plain', text: 'hello world' },
    ])
  })

  it('parses a single deletion', () => {
    expect(parseMarkup('[D>old<D]')).toEqual([
      { type: 'deletion', text: 'old' },
    ])
  })

  it('parses a single addition', () => {
    expect(parseMarkup('[A>new<A]')).toEqual([
      { type: 'addition', text: 'new' },
    ])
  })

  it('parses mixed content', () => {
    expect(parseMarkup('keep [D>del<D] and [A>add<A] end')).toEqual([
      { type: 'plain', text: 'keep ' },
      { type: 'deletion', text: 'del' },
      { type: 'plain', text: ' and ' },
      { type: 'addition', text: 'add' },
      { type: 'plain', text: ' end' },
    ])
  })

  it('handles adjacent tags', () => {
    expect(parseMarkup('[D>a<D][A>b<A]')).toEqual([
      { type: 'deletion', text: 'a' },
      { type: 'addition', text: 'b' },
    ])
  })

  it('handles multiline text inside tags', () => {
    const result = parseMarkup('[A>line one\nline two<A]')
    expect(result).toEqual([{ type: 'addition', text: 'line one\nline two' }])
  })

  it('returns empty array for empty string', () => {
    expect(parseMarkup('')).toEqual([])
  })
})
