export type Language = 'en' | 'ja';

/** The language lives in a cookie so the server can render the right text with no flash (PLAN.md 10.3). */
export const LANGUAGE_COOKIE = 'language';

export function toLanguage(value: string | undefined | null): Language | null {
  return value === 'en' || value === 'ja' ? value : null;
}

/** "ja,en;q=0.9" -> "ja". Used for the first visit, before the cookie exists. */
export function languageFromHeader(acceptLanguage: string | null): Language {
  return acceptLanguage?.toLowerCase().startsWith('ja') ? 'ja' : 'en';
}
