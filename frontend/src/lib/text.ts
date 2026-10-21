// Text extracted from a PDF keeps the line breaks of the page layout: a line
// ends wherever the line ended on paper, often in the middle of a sentence.
// For reading, those breaks are joined, and only the breaks that end a
// sentence or a heading (after . ! ? or :) are kept.

export function readableText(text: string): string {
  return text
    .replace(/\r\n?/g, '\n')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/([^.!?:\n])\n(?!\n)/g, '$1 ')
    .replace(/ {2,}/g, ' ')
    .trim()
}