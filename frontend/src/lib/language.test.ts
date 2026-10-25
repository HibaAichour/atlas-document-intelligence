import { describe, expect, it } from 'vitest'

import { dictionaries } from './i18n'
import {
  LANGUAGE_KEY,
  LANGUAGES,
  isLanguage,
  languageFromBrowser,
  readLanguage,
  saveLanguage,
} from './language'
import type { KeyValueStore } from './sessions'

/** An in-memory stand-in for localStorage. */
function fakeStorage(): KeyValueStore & { values: Map<string, string> } {
  const values = new Map<string, string>()
  return {
    values,
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => void values.set(key, value),
    removeItem: (key) => void values.delete(key),
  }
}

/** A storage that refuses everything, like a browser with storage blocked. */
const brokenStorage: KeyValueStore = {
  getItem: () => {
    throw new Error('blocked')
  },
  setItem: () => {
    throw new Error('blocked')
  },
  removeItem: () => {
    throw new Error('blocked')
  },
}

describe('languageFromBrowser', () => {
  it('picks French for any French variant, English otherwise', () => {
    expect(languageFromBrowser(['fr'])).toBe('fr')
    expect(languageFromBrowser(['fr-FR', 'en'])).toBe('fr')
    expect(languageFromBrowser(['FR-ca'])).toBe('fr')
    expect(languageFromBrowser(['en-GB', 'fr'])).toBe('en')
    expect(languageFromBrowser(['ar-MA'])).toBe('en')
    expect(languageFromBrowser(['fry'])).toBe('en')
    expect(languageFromBrowser([])).toBe('en')
  })
})

describe('readLanguage and saveLanguage', () => {
  it('starts with the browser language, then remembers the choice', () => {
    const storage = fakeStorage()

    expect(readLanguage(storage, ['fr-FR'])).toBe('fr')
    saveLanguage('en', storage)

    expect(storage.values.get(LANGUAGE_KEY)).toBe('en')
    expect(readLanguage(storage, ['fr-FR'])).toBe('en')
  })

  it('ignores an unknown saved value', () => {
    const storage = fakeStorage()
    storage.values.set(LANGUAGE_KEY, 'de')

    expect(readLanguage(storage, ['fr'])).toBe('fr')
  })

  it('never throws without storage', () => {
    expect(readLanguage(brokenStorage, ['fr'])).toBe('fr')
    expect(readLanguage(null, ['en-US'])).toBe('en')
    expect(() => saveLanguage('fr', brokenStorage)).not.toThrow()
    expect(() => saveLanguage('fr', null)).not.toThrow()
  })

  it('knows its languages', () => {
    expect(LANGUAGES).toEqual(['en', 'fr'])
    expect(isLanguage('fr')).toBe(true)
    expect(isLanguage('FR')).toBe(false)
    expect(isLanguage(null)).toBe(false)
  })
})

describe('the French dictionary', () => {
  const en = dictionaries.en
  const fr = dictionaries.fr

  it('has every text of the English one', () => {
    expect(Object.keys(fr).sort()).toEqual(Object.keys(en).sort())
    expect(Object.keys(fr.issueTexts).sort()).toEqual(Object.keys(en.issueTexts).sort())
  })

  it('writes French numbers, dates and plurals', () => {
    expect(fr.dateLocale).toBe('fr-FR')
    expect(fr.answeredIn(5.24)).toBe('Répondu en 5,2\u00a0s.')
    expect(fr.similarity(0.6234)).toBe('Similarité avec la question\u00a0: 0,62')
    expect(fr.messageCount(1)).toBe('1 message')
    expect(fr.messageCount(6)).toBe('6 messages')
    expect(fr.selectionSummary(1, 6)).toBe('Questions\u00a0: 1 document sur 6.')
    expect(fr.selectionSummary(6, 6)).toBe('Questions\u00a0: 6 documents sur 6.')
    expect(fr.extractionCount(1, 4)).toBe('1 champ trouvé sur 4.')
    expect(fr.extractionCount(3, 4)).toBe('3 champs trouvés sur 4.')
  })

  it('translates the field labels, while English keeps the backend labels', () => {
    expect(fr.fieldLabels.invoice_number).toBe('Numéro de facture')
    expect(fr.extractionTitle('invoice.pdf', 'invoice')).toBe('Champs clés de invoice.pdf (facture)')
    expect(fr.extractRequest('invoice.pdf')).toBe('Extraire les champs clés de invoice.pdf')
    expect(en.fieldLabels.invoice_number).toBeUndefined()
  })

  it('keeps the English texts unchanged', () => {
    expect(en.answeredIn(5.24)).toBe('Answered in 5.2 s.')
    expect(en.documentFailed('No text found on any page.')).toBe('No text found on any page.')
    expect(fr.documentFailed('No text found on any page.')).toBe(
      'Lecture impossible\u00a0: No text found on any page.',
    )
  })
})