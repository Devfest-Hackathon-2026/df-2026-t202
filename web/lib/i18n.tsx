'use client';

import { createContext, useContext, type ReactNode } from 'react';
import en from '@/public/i18n/en.json';
import ja from '@/public/i18n/ja.json';
import { LANGUAGE_COOKIE, type Language } from './language';

// Both files are tiny, so they are bundled instead of fetched: no loading state, no flash.
const DICTIONARIES = { en, ja };

const LanguageContext = createContext<Language>('en');

export function I18nProvider({ lang, children }: { lang: Language; children: ReactNode }) {
  return <LanguageContext.Provider value={lang}>{children}</LanguageContext.Provider>;
}

export function useLanguage(): Language {
  return useContext(LanguageContext);
}

/** t('plan.badge.estimate'). Returns the key itself if it is missing, so a typo is visible. */
export function useT(): (key: string) => string {
  const lang = useLanguage();
  return (key: string) => {
    const value = key.split('.').reduce<unknown>((node, part) => {
      return node && typeof node === 'object' ? (node as Record<string, unknown>)[part] : undefined;
    }, DICTIONARIES[lang]);
    return typeof value === 'string' ? value : key;
  };
}

/**
 * Switching reloads the page: the Maps JavaScript API fixes its language when its script loads,
 * and the server renders from the cookie (PLAN.md 10.3).
 */
export function setLanguage(lang: Language): void {
  document.cookie = `${LANGUAGE_COOKIE}=${lang}; path=/; max-age=31536000; samesite=lax`;
  location.reload();
}
