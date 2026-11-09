export type Language = 'en' | 'ja';

/**
 * The language lives in a cookie so the server can render the right text with no flash (PLAN.md 10.3).
 * Named `__session` because Firebase Hosting (tripi.web.app) forwards only that cookie to the server.
 */
export const LANGUAGE_COOKIE = '__session';

export function toLanguage(value: string | undefined | null): Language | null {
  return value === 'en' || value === 'ja' ? value : null;
}

/** "ja,en;q=0.9" -> "ja". Used for the first visit, before the cookie exists. */
export function languageFromHeader(acceptLanguage: string | null): Language {
  return acceptLanguage?.toLowerCase().startsWith('ja') ? 'ja' : 'en';
}
