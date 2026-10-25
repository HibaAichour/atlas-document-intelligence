// The language of the interface: English or French, chosen by the user and
// remembered by the browser. On a first visit, the browser's language decides.

import type { KeyValueStore } from './sessions'

export type Language = 'en' | 'fr'

export const LANGUAGES: readonly Language[] = ['en', 'fr']

/** Key under which the browser remembers the chosen language. */
export const LANGUAGE_KEY = 'atlas.language'

export function isLanguage(value: unknown): value is Language {
  return value === 'en' || value === 'fr'
}

/** French when the browser's preferred language is French ("fr", "fr-FR"...),
 * English otherwise: English is the language of the demo and of the README. */
export function languageFromBrowser(preferred: readonly string[]): Language {
  const first = preferred[0]?.toLowerCase() ?? ''
  return first === 'fr' || first.startsWith('fr-') ? 'fr' : 'en'
}

/** The browser's localStorage, or null where it cannot be used. */
function browserStorage(): KeyValueStore | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** The languages the browser prefers, most preferred first ([] outside a browser). */
function browserLanguages(): readonly string[] {
  try {
    return navigator.languages.length > 0 ? navigator.languages : [navigator.language]
  } catch {
    return []
  }
}

/** The language to start with: the one chosen at a previous visit, else the
 * browser's. Never throws. */
export function readLanguage(
  storage: KeyValueStore | null = browserStorage(),
  preferred: readonly string[] = browserLanguages(),
): Language {
  try {
    const saved = storage?.getItem(LANGUAGE_KEY)
    if (isLanguage(saved)) {
      return saved
    }
  } catch {
    // Storage blocked: fall back to the browser's language.
  }
  return languageFromBrowser(preferred)
}

/** Remember the chosen language. Never throws: without storage the choice
 * simply lasts until the page is reloaded. */
export function saveLanguage(
  language: Language,
  storage: KeyValueStore | null = browserStorage(),
): void {
  try {
    storage?.setItem(LANGUAGE_KEY, language)
  } catch {
    // Storage full or blocked: nothing to do.
  }
}