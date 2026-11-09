/**
 * Build-time config. Next.js inlines NEXT_PUBLIC_* at build time (PLAN.md 12).
 * Locally these come from web/.env.local; on App Hosting from apphosting.yaml.
 * Everything here reaches the browser: only browser-safe values.
 */
export const env = {
  firebase: {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? '',
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? '',
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? 'demo-trip-planner',
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? '',
  },
  mapsBrowserKey: process.env.NEXT_PUBLIC_MAPS_BROWSER_KEY ?? '',
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8080',
  recaptchaSiteKey: process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY ?? '',
  useEmulators: process.env.NEXT_PUBLIC_USE_EMULATORS === 'true',
} as const;
