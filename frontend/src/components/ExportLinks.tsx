import { EXPORT_FORMATS, exportUrl, type SavedRef } from '../lib/export'
import type { Messages } from '../lib/i18n'

interface ExportLinksProps {
  saved: SavedRef
  t: Messages
}

/** Download links for one saved result: the backend builds the file. */
export function ExportLinks({ saved, t }: ExportLinksProps) {
  return (
    <div className="export">
      <span className="export-label">{t.exportLabel}</span>
      {EXPORT_FORMATS.map((format) => (
        <a
          key={format}
          className="export-link"
          href={exportUrl(saved, format)}
          download
          aria-label={t.exportAria[format]}
        >
          {t.exportNames[format]}
        </a>
      ))}
    </div>
  )
}
