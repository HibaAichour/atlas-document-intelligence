import { describe, expect, it } from 'vitest'

import { readableText } from './text'

describe('readableText', () => {
  it('joins a sentence cut by the end of a line', () => {
    expect(readableText('Either Party may terminate\nthis Agreement.')).toBe(
      'Either Party may terminate this Agreement.',
    )
  })

  it('keeps the break after the end of a sentence or a heading', () => {
    expect(readableText('The term is 24 months.\n4.2 Renewal. The Agreement renews.')).toBe(
      'The term is 24 months.\n4.2 Renewal. The Agreement renews.',
    )
    expect(readableText('Fees:\nUSD 12,500 per month')).toBe('Fees:\nUSD 12,500 per month')
  })

  it('keeps empty lines between paragraphs', () => {
    expect(readableText('First paragraph\n\nSecond paragraph')).toBe(
      'First paragraph\n\nSecond paragraph',
    )
  })

  it('handles Windows line endings and stray spaces', () => {
    expect(readableText('  shall pay all fees  \r\ndue up to the date.  ')).toBe(
      'shall pay all fees due up to the date.',
    )
  })
})