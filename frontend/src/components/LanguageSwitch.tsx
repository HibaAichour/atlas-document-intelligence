import { useLanguage, useMessages } from '../lib/i18n'
import { LANGUAGES } from '../lib/language'

/** EN | FR in the header: the same small control as Ask / Extract. */
export function LanguageSwitch() {
  const t = useMessages()
  const { language, setLanguage } = useLanguage()

  return (
    <div className="mode-switch language-switch" role="group" aria-label={t.languageLabel}>
      {LANGUAGES.map((option) => (
        <button
          key={option}
          type="button"
          className={option === language ? 'mode-option mode-option-on' : 'mode-option'}
          aria-pressed={option === language}
          // Each language is named in its own language, for every reader.
          aria-label={t.languageNames[option]}
          title={t.languageNames[option]}
          lang={option}
          onClick={() => setLanguage(option)}
        >
          {t.languageShort[option]}
        </button>
      ))}
    </div>
  )
}
