import { useEffect, useMemo, useState, type ReactNode } from 'react'

import { LanguageContext, type LanguageState } from '../lib/i18n'
import { readLanguage, saveLanguage, type Language } from '../lib/language'

/** Holds the language of the interface for the whole app, and remembers it. */
export function LanguageProvider({ children }: { children: ReactNode }) {
  // Read once when the page loads: the saved choice, else the browser's language.
  const [language, setLanguageState] = useState<Language>(readLanguage)

  // The page's language helps screen readers and the browser (hyphenation).
  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  const state = useMemo<LanguageState>(
    () => ({
      language,
      setLanguage: (next: Language) => {
        saveLanguage(next)
        setLanguageState(next)
      },
    }),
    [language],
  )

  return <LanguageContext.Provider value={state}>{children}</LanguageContext.Provider>
}
