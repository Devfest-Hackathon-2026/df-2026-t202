# web/: Angular app (Firebase App Hosting)

Adds to the root `AGENTS.md`. Spec: PLAN.md section 10. Angular **21** (standalone components, Signals, zoneless),
Angular Material 21, `@angular/google-maps`, AngularFire 21, Transloco. Node ≥ 22.12, npm 11.

## Layout (✅ exists, ⬜ to build)
```
src/app/app.config.ts      ✅ Router, HttpClient, Firebase (Auth, Firestore, App Check if a site key is set), Transloco
src/app/app.routes.ts      ✅ / (S7), /trips/:tripId (S1+S2), /trips/:tripId/plan (S3–S5), /s/:shareId (S6)
src/app/core/env.ts        ✅ build-time config (generated from web/.env or apphosting.yaml by scripts/write-env.mjs)
src/app/core/api.service.ts ✅ post<T>(path, body): the only way to call the API (adds ID token + App Check token)
src/app/core/language.service.ts ✅ en/ja signal, localStorage, reload on change
src/app/core/              ⬜ auth service (Google + anonymous sign-in), trip/messages/plan Firestore services (signals)
src/app/home/              ⬜ S7 My trips          (placeholder page exists)
src/app/chat/ + cards/     ⬜ S1 chat, S2 slots panel, the 8 cards
src/app/plan/              ⬜ S3 trip page, map, timeline, S4 Shorts viewer, S5 share sheet
src/app/share/             ⬜ S6 shared page (anonymous auth, read-only)
public/i18n/en.json, ja.json ✅ UI text (served at /i18n/*.json). Keys must match (src/app/i18n.spec.ts)
apphosting.yaml            ✅ App Hosting env (BUILD availability); REPLACE-* values set by INF
```

## Angular rules
- Standalone components, `ChangeDetectionStrategy.OnPush`, `inject()` instead of constructor injection.
- State = **Signals**. Firestore listeners (`onSnapshot`/AngularFire `docData`/`collectionData`) feed signals; use `toSignal`
  or `effect` cleanup. Temporary card state stays inside the card component.
- New control flow (`@if`, `@for` with `track`), `input()`/`output()` functions, `computed()` for derived values.
- One feature per folder (home/chat/plan/share). Shared pieces go in `core/` (services) or a `shared/` folder (UI).
- Use Angular Material components before writing custom ones. Check the version-21 APIs; don't rely on memory of older versions.

## Data rules (PLAN.md 5 and 11)
- **Read from Firestore, write through the API.** Clients can't write trips, messages, plans or shares (`firestore.rules`).
  Only `users/{uid}` (displayName, photoURL, language, createdAt) is written by the client.
- "My trips" query: `where(\`members.${uid}\`, 'in', ['owner', 'viewer'])`, sorted on the client (matches the read rule).
- The current card is the `ui` field of the last AI message. Card answers are sent as structured data:
  `api.post('/trips/{id}/messages', { type: 'answer', step, value })`. Free text: `{ type: 'text', text }`.
- Shapes are PLAN.md 7 (TypeScript interfaces mirror `api/app/models.py`; keep the names identical).
- The Maps JS key comes from `env.mapsBrowserKey`. Load the Maps script with `language` = UI language. After a language change, the page reloads.
- YouTube: the official IFrame Player only (API terms). Fallback: "Search on YouTube" link + Places photo.

## UI rules (PLAN.md 10.4)
- **Phone first** (390 px), especially the trip page and the shared page. PC: chat left + slots panel right.
- **No hard-coded UI text.** `{{ 'key' | transloco }}` everywhere. Add every key to **both** `en.json` and `ja.json`.
- Use the CSS variables in `src/styles.scss` (`--color-coral`, `--color-sky`, `--day-1..7`, glass tokens). No hard-coded colors.
- Badges: "Estimate" on costs and estimated legs, "Please check" on times, hours, ferries, flights.
- Planning progress from `trips.progress`: "Finding spots → Calculating travel times → Finding videos".
- Every async view has loading, empty and error states. Tap targets ≥ 44 px. Keyboard and screen-reader labels on cards.

## Local dev
```bash
cp .env.example .env     # USE_EMULATORS=true for the emulators; never commit .env
npm install && npm start # http://localhost:4200
```
`npm start`, `npm run build` and `npm test` first run `scripts/write-env.mjs`, which writes `src/environments/env.generated.ts` (git-ignored).

## Test
`npm run build && npm test` (Vitest through `ng test`). Before merging UI work, click through the flow at 390 px in both languages.
