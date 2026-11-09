# web/: Next.js app (Firebase App Hosting)

Adds to the root `AGENTS.md`. Spec: PLAN.md section 10. **Next.js 16** (App Router), **React 19**, TypeScript,
**Tailwind CSS v4**, `@vis.gl/react-google-maps`, Firebase JS SDK. Node ≥ 22.12, npm 11.
The framework changed from Angular on 2026-11-09 — see `docs/decisions.md` D70.

## Layout

```
app/layout.tsx              language from the `__session` cookie (Firebase Hosting forwards only that one), I18nProvider
app/globals.css             Tailwind import, @theme tokens (--color-ink, --color-accent, --color-day-1..7), glass classes
app/page.tsx                S7 start: sign-in, prompt, suggestion chips, my trips (user menu)
app/trips/[tripId]/page.tsx S1-S5: chat and question cards, then the plan, map, Shorts and share sheet
app/s/[shareId]/page.tsx    S6 shared page, read-only, anonymous auth
components/chat/            chat panel, messages, question cards, photo chat
components/plan/            plan panel (timeline, legs, cost), spot panel (Shorts player), place photo
components/                 map, bottom sheet, day tabs, share sheet, headers, language switch, user menu
lib/env.ts                  NEXT_PUBLIC_* build-time config (trimmed)
lib/firebase.ts             app/auth/firestore singletons, emulators, App Check when a site key is set
lib/api.ts                  post<T>(path, body): the only way to call the API (adds ID token + App Check token)
lib/auth.ts, trip.ts        Google + anonymous sign-in; trip/messages/plan Firestore hooks
lib/i18n.tsx, language.ts   I18nProvider, useT(), useLanguage(), setLanguage(); cookie name
lib/types.ts                PLAN.md 7 shapes (mirror api/app/models.py)
public/i18n/en.json, ja.json UI text. Keys must match (tests/i18n.test.ts)
apphosting.yaml             App Hosting env (BUILD availability)
```

Deploy: `firebase deploy --only apphosting` from the repo root (the backend is not linked to GitHub). The public link
is `https://kyucat-trip.web.app` (Firebase Hosting rewrite to the App Hosting service, `docs/decisions.md` D77).

## React rules

- Server Components by default; add `'use client'` only where you need state, effects or Firebase.
- `lib/firebase.ts` and `lib/api.ts` are client-only. Never import them from a Server Component.
- Route params are a Promise in Next 16: `const { tripId } = use(params)` in a Client Component.
- State = `useState` / `useReducer` fed by Firestore listeners in `useEffect`; always return the unsubscribe.
- One feature per folder. Shared pieces go in `components/`; services and clients go in `lib/`.
- Icons come from `lucide-react` (`<MapPin size={16} />`). Don't hand-write SVG paths; the Google "G" on the sign-in button is the one exception, because their branding requires it.
- No component library. Style with Tailwind utilities; tokens come from `@theme` in `app/globals.css` (`bg-ink`, `text-muted`, `border-line`, `bg-accent`). `desk:` is the 900 px desktop breakpoint.
- One glass recipe everywhere: `border border-white/15 bg-stone-900/50 backdrop-blur-2xl` on panels over a photo or the map (the start-screen prompt sets it), `.frost` for small light chips over the map. `.frost` (over the map) and `.sheet-glass` (the panel) are light, because they carry ink-coloured text; panels on the start photo use the same numbers in dark (`bg-stone-900/50 backdrop-blur-2xl border-white/15`) because their text is white. `.frost`, `.sheet-glass` and `.noscroll` are `@layer components` classes in `app/globals.css`. Day colors are inline `style` because they are data, not a fixed class.

## Data rules (PLAN.md 5 and 11)

- **Read from Firestore, write through the API.** Clients can't write trips, messages, plans or shares (`firestore.rules`).
  Only `users/{uid}` (displayName, photoURL, language, createdAt) is written by the client.
- "My trips" query: `where(\`members.${uid}\`, 'in', ['owner', 'viewer'])`, sorted on the client (matches the read rule).
- The current card is the `ui` field of the last AI message. Card answers are sent as structured data:
  `post('/trips/{id}/messages', { type: 'answer', step, value })`. Free text: `{ type: 'text', text }`.
- Shapes are PLAN.md 7 (TypeScript interfaces mirror `api/app/models.py`; keep the names identical).
- The Maps JS key comes from `env.mapsBrowserKey`. Load the Maps script with `language` = UI language. After a language change, the page reloads.
- YouTube: the official IFrame Player only (API terms). Fallback: "Search on YouTube" link + Places photo.

## UI rules (PLAN.md 10.4)

- **Phone first** (390 px), especially the trip page and the shared page. PC: chat left + slots panel right.
- **No hard-coded UI text.** `t('key')` from `useT()` everywhere. Add every key to **both** `en.json` and `ja.json`.
- Use the token utilities from `@theme`. No hard-coded colors.
- Badges: "Estimate" on costs and estimated legs, "Please check" on times, hours, ferries, flights.
- Planning progress from `trips.progress`: "Finding spots → Calculating travel times → Finding videos".
- Every async view has loading, empty and error states. Tap targets ≥ 44 px. Keyboard and screen-reader labels on cards.

## Local dev

```bash
cp .env.example .env.local   # NEXT_PUBLIC_USE_EMULATORS=true for the emulators; never commit it
npm install && npm run dev   # http://localhost:4200  (npm start is the PRODUCTION server)
```

## Test

`npm run build && npm test` (Vitest). `npm run build` also type-checks. Before merging UI work, click through the
flow at 390 px in both languages.

<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
