/**
 * Build-time config. Next.js inlines NEXT_PUBLIC_* at build time (PLAN.md 12).
 * Locally these come from web/.env.local; on App Hosting from apphosting.yaml.
 * Everything here reaches the browser: only browser-safe values.
 */
// Trimmed: a value pasted into Secret Manager can end in a newline, and a key with "%0A" on it is
// rejected outright (the map tolerated it, Places photo URLs did not).
const clean = (value: string | undefined, fallback = '') => value?.trim() || fallback;

const projectId = clean(process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID, 'demo-trip-planner');

export const env = {
  firebase: {
    apiKey: clean(process.env.NEXT_PUBLIC_FIREBASE_API_KEY),
    // Every Firebase project has this domain; without one, Google sign-in fails to start.
    authDomain: clean(process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN, `${projectId}.firebaseapp.com`),
    projectId,
    appId: clean(process.env.NEXT_PUBLIC_FIREBASE_APP_ID),
  },
  mapsBrowserKey: clean(process.env.NEXT_PUBLIC_MAPS_BROWSER_KEY),
  apiBaseUrl: clean(process.env.NEXT_PUBLIC_API_BASE_URL, 'http://localhost:8080'),
  recaptchaSiteKey: clean(process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY),
  useEmulators: process.env.NEXT_PUBLIC_USE_EMULATORS === 'true',
} as const;
