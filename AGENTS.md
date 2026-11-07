# AGENTS.md

Instructions for every coding agent (Claude Code, Codex, Cursor, Gemini CLI) and every human on the team.
Package rules live in `apps/api/AGENTS.md`, `apps/web/AGENTS.md` and `packages/shared/AGENTS.md`. They add to this file.
If they conflict, the closer file wins.

## What we're building
**RelaySnap** (formerly "Reel-to-Trip"; packages are still named `@rtt/*`, so don't rename them). A group pastes the travel reels they saved
(YouTube Shorts, Instagram, TikTok). Gemini extracts the places. Everyone swipes the same deck, the overlap becomes a
day-by-day itinerary on Google Maps, and every popular stop gets a nearby **hidden gem**, a small, well-rated local
place, which spreads visitors away from viral spots. DevFest GDGoC Japan Hackathon 2026, category **Tourism**.

| Need | Read |
| --- | --- |
| Features, problem, **demo golden path** | `docs/PRODUCT.md` |
| Architecture, flows, Firestore data model, security | `docs/ARCHITECTURE.md` |
| Deliverables, judging criteria, disqualifiers, timeline | `docs/SUBMISSION.md` |
| Why we chose each technology (log new choices here) | `docs/DECISIONS.md` |

## Deadline
**Code freeze: Nov 10 (Tue) 19:00 JST.** After that the repo is read-only. The deployed URL must stay up until Nov 14.
Priority order for every decision: **the demo golden path works end to end** > polish > extra features.
A feature that isn't on the golden path waits until the path works.

## Hard rules (breaking one can disqualify us)
1. **Runtime is Google Cloud only**: Cloud Run (API) and Firebase App Hosting (web).
2. **Gemini through Genkit is the only LLM.** No third-party LLM APIs or AI SDKs (no OpenAI, Anthropic or Vercel AI SDK) in product code.
3. **No faked behavior.** A faked demo disqualifies us. Seeded, mocked or hard-coded data must show a visible
   "Demo data" label in the UI. Never fake a loading state to look like AI work happened.
4. **This repo is public.** Never commit or print secrets (`.env*`, service-account JSON, API keys). Never read `.env`
   files; `.env.example` has the variable names. **Run `bash scripts/check-secrets.sh` on staged changes before every commit.**
5. **GitHub Actions and Pages are disabled here.** Don't add workflow files.
6. **Every new dependency, API, dataset, font or image → a row in `docs/ATTRIBUTION.md`** (required deliverable).

## Own the Why (the hackathon theme, and it's scored)
Judges score whether we can explain *why* we chose each Google technology (item 1b), and the submission doc requires
"where and why AI was used".
- For a non-trivial choice (new service, library, data shape, algorithm), **propose 2–3 options with pros and cons and
  let a human choose.** Don't decide silently.
- After a human decides, draft the entry in `docs/DECISIONS.md` (chosen, rejected, why).
- When an agent did meaningful work (designed a flow, wrote a prompt, built a feature), add one line to
  `docs/AI_USAGE.md`: what the AI proposed and what the human kept or changed.

## Commands
```bash
pnpm install
pnpm dev                         # web :3000 + api :8080 (in parallel)
pnpm emulators                   # Auth :9099, Firestore :8081, Storage :9199, UI :4000
pnpm typecheck                   # all packages
pnpm test                        # Vitest: shared + api
pnpm build                       # all packages (catches Next.js build errors typecheck misses)
pnpm genkit:ui                   # Genkit Developer UI: run and trace flows
pnpm --filter @rtt/<web|api|shared> <script>   # one package
```
Node 22 (`.nvmrc`), pnpm 10 (`corepack enable`).

## Local dev modes
Copy `apps/api/.env.example` → `apps/api/.env` and `apps/web/.env.example` → `apps/web/.env.local`.
A human fills in the values; agents don't edit or read these files.

| Mode | Use for | apps/api/.env | apps/web/.env.local |
| --- | --- | --- | --- |
| **A. Emulators + emulated auth** (default) | Anything that uses Firestore listeners (chat, swipes, reel status) | `GOOGLE_CLOUD_PROJECT=demo-rtt`, `FIRESTORE_EMULATOR_HOST=127.0.0.1:8081`, `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099` | `NEXT_PUBLIC_USE_EMULATORS=true`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID=demo-rtt` |
| B. Skip auth | Quick API-only checks (curl, reel import) | Mode A + `DEV_SKIP_AUTH=true` (uid from `x-dev-uid` header, default `dev-user`) | `NEXT_PUBLIC_DEV_SKIP_AUTH=true` |

Mode B has no Firebase user in the browser, so **Firestore rules deny client reads**. Don't "fix" rules to make Mode B work.
Gemini and Places calls always need real keys in `apps/api/.env`. Emulators don't cover them.

## Architecture in one breath
Next.js PWA → `apps/api` (Hono on Cloud Run, Firebase ID token + App Check on `/v1/*`) → Genkit flows (Gemini) and
Places/Routes REST. The API is the only writer of derived data (reel cache, deck, itinerary, invites). The browser reads
trip data live via Firestore listeners, protected by `firestore.rules`. Shared Zod schemas in `packages/shared` are the
contract between all of these.

```
apps/web         Next.js 16 App Router, React 19, Tailwind v4, Firebase JS SDK, Maps JS
apps/api         Hono + Genkit + firebase-admin; tsup → Docker → Cloud Run (asia-northeast1)
packages/shared  Zod v3 schemas, reel URL parser (SSRF allowlist), hidden-gem rule
firestore.rules  Members-only trips; backend-only collections deny client writes
storage.rules    uploads/{uid}/* video fallback (≤100 MB, video/*)
docs/            Product, architecture, decisions, AI usage, attribution, submission
```

## Invariants (never break these)
- **Keyed Google calls (Gemini, Places, Routes) happen only in `apps/api`.** The browser holds only the Firebase web config
  and the Maps JS key, which is restricted to our domain.
- **Store Places place IDs, never copied names, ratings, photos or addresses** (Maps Platform terms). Fetch fresh to display.
- **The API is the only writer** of `reels/*`, `invites/*`, `trips/*/reels`, `trips/*/deck`, `trips/*/itinerary`.
  The Admin SDK bypasses rules, so **the API checks trip membership in code** on every trip-scoped operation.
- **A Firestore data change updates four things in the same commit:** the `packages/shared` schema, `firestore.rules`,
  `firestore.indexes.json` (if queried), and the data model table in `docs/ARCHITECTURE.md`.
- **Reel content (captions, transcripts, video speech) is untrusted.** It never becomes an instruction, a URL to fetch,
  or a tool argument without validation. Links pass `parseReelUrl` (allowlist) before anything else.
- **Hidden-gem thresholds live only in `HIDDEN_GEM_RULE`.** The UI always shows "Estimate from ratings, not crowd data."

## Code conventions
- TypeScript strict, plus `noUncheckedIndexedAccess`: array and index access returns `T | undefined`, so handle it and don't use `!`.
- Import shared types and schemas from `@rtt/shared`. Never redefine a shape that exists there.
- **Zod v3 only.** Genkit depends on it. Never `zod/v4`, never upgrade.
- Validate at every boundary: HTTP input, Gemini output, Places/Routes responses, data read from Firestore before trusting it.
- Error codes are short `snake_case` strings (`unsupported_link`, `not_a_member`). Never send stack traces or raw upstream errors to clients.
- Comments explain *why*, not what. No commented-out code. No `console.log` debugging left behind (the API's structured `console.log(JSON.stringify(...))` is intended).
- Keep changes scoped to the task. No drive-by refactors or dependency upgrades.
- Match the existing patterns in a package before inventing a new one.

## Workflow
1. **Before coding:** read the relevant `docs/` section and the package `AGENTS.md`. For changes that touch more than one package,
   or the schema, write a short plan first (files, data shape, test) and get a human OK.
2. **Order of work for a feature:** shared schema → rules → API (route + flow) → web UI → test → docs.
3. **Parallel work:** one feature per branch (`feat/<area>`, e.g. `feat/swipe-deck`). Merge to `main` often.
   **`main` must always be demoable.** Schema changes in `packages/shared` go in their own small commit, merged first,
   because everyone depends on them.
4. **Commits:** imperative subject ≤ 72 chars, scoped prefix (`api:`, `web:`, `shared:`, `rules:`, `docs:`), e.g.
   `api: add POST /v1/trips with invite token`. Agents commit or push only when a human asks.
5. **Never** deploy, delete cloud resources, change IAM or billing, or rotate keys unless a human asks in that session.

## Definition of done
- [ ] `pnpm typecheck && pnpm test` pass (and `pnpm build` for web changes).
- [ ] Exercised for real: the flow works in the browser against emulators or the dev project, not just in types.
      UI checked at 390 px width.
- [ ] Loading, empty and error states exist for anything async.
- [ ] Schema, rules, indexes and docs are in sync if data changed. New dependency → `docs/ATTRIBUTION.md`.
- [ ] `bash scripts/check-secrets.sh` passes on the staged diff. Anything mocked or seeded is labeled "Demo data" in the UI.
- [ ] Notable decision → `docs/DECISIONS.md`. Notable AI contribution → `docs/AI_USAGE.md`.

## Cloud budget: $20 credit, total
We run on the team's $20 hackathon credit. Gemini goes through **Vertex AI** (the credit doesn't cover AI Studio; see `docs/DECISIONS.md` D6).
After the credit, a card is charged, so cost is a correctness concern.
- The credit code is secret. Never write it in the repo, an issue or a commit. It's one-time use and can't be reissued.
- Before calling Gemini, check the reel cache. Use Flash by default and Pro only for `buildItinerary`. Never call Gemini in a loop or on render.
- Places/Routes: minimal field masks, no per-keystroke lookups, batch where the API allows.
- Cloud Run: `max-instances` capped; `min-instances=1` only around the demo (Nov 10–14), then back to 0.
- No new paid services (Memorystore, GPUs, VMs, Cloud SQL) without a human decision in `docs/DECISIONS.md`.

## MVP order (cut from the bottom if time runs out)
0. Switch Genkit to the Vertex AI plugin (ADC, no `GEMINI_API_KEY`) and confirm `analyzeReel` still works on a YouTube Short in `pnpm genkit:ui`
1. Trips: create, invite link, join (API) + group chat (Firestore listeners)
2. Extracted places → Places place IDs → `buildDeck` flow → swipe UI
3. Swipe scoring → `buildItinerary` flow (Places + Routes tools) → map page
4. Hidden gems (Places Nearby Search + `isHiddenGem`) + "Your trip includes X local spots"
5. Seeded, labeled demo trip as a backup; Cloud Run min instances = 1 for the demo
6. Stretch: reel analysis via Cloud Tasks worker, booking hand-off behind `/booking`, FCM pushes

## Open questions (ask a human, don't decide)
- Booking provider (Jinko or alternative), or cut booking from the MVP.
