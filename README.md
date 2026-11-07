# Reel-to-Trip (working name)

Turn the travel reels you and your friends already saved into one group itinerary — with a local **hidden gem** next to every viral spot.

DevFest Hackathon 2026 · Category: **Tourism** · Built on Google Cloud, Firebase, Gemini and Google Maps Platform.

> Deployed URL: _add here before submission_

## What it does

1. **Reel import** — paste YouTube Shorts / Instagram / TikTok links. Gemini extracts places, food, activities and vibe.
2. **Swipe deck** — Tinder-style cards to learn what each person likes.
3. **Group trips** — invite friends, share reels, everyone swipes the same deck; we find the overlap.
4. **Itinerary + map** — day-by-day plan on Google Maps.
5. **Hidden gem card** — next to each popular stop, one nearby local place: rating ≥ 4.3, 20–299 reviews, within ~800 m. An estimate from ratings, not crowd data.
6. **Booking** — hand-off to a booking provider (stretch goal).

## Repo layout

```
apps/web         Next.js (App Router) + Tailwind — the PWA (Firebase App Hosting)
apps/api         Hono + Genkit (Gemini) on Cloud Run
packages/shared  Zod schemas, reel-link parser, hidden gem rule (shared by web + api)
firestore.rules  Security rules (members-only trips)
storage.rules    Upload rules
docs/            Hackathon repo rules (from the organizers)
```

## Google services

| Service | Used for |
| --- | --- |
| Gemini (via Genkit) | Watching reels, planning itineraries, explaining picks |
| Places API (New), Routes API, Maps JavaScript API | Cards, opening hours, hidden gems, travel times, map page |
| Cloud Run | API + reel worker |
| Firestore | Trips, chat, swipes (real-time) |
| Cloud Storage | Video uploads (Instagram/TikTok fallback) |
| Firebase Auth + App Check | Google sign-in, quota protection |
| Secret Manager | API keys |
| Firebase App Hosting | Web app |
| Cloud Tasks | Async reel analysis (next step) |

## Run locally

Requirements: Node 22+, pnpm 10 (`corepack enable`), Firebase CLI (`npm i -g firebase-tools`).

```bash
pnpm install

# API
cp apps/api/.env.example apps/api/.env          # add GEMINI_API_KEY
# Web
cp apps/web/.env.example apps/web/.env.local    # add Firebase web config

# Option A — fastest: no Firebase project yet
#   apps/api/.env      DEV_SKIP_AUTH=true, FIRESTORE_EMULATOR_HOST=127.0.0.1:8081
#   apps/web/.env.local NEXT_PUBLIC_DEV_SKIP_AUTH=true
pnpm emulators        # terminal 1 (Firestore/Auth/Storage emulators, UI on :4000)
pnpm dev              # terminal 2 (web :3000, api :8080)
```

Useful scripts: `pnpm typecheck`, `pnpm test`, `pnpm build`, `pnpm genkit:ui` (Genkit Developer UI to test prompts).

## API

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/healthz` | Health check |
| POST | `/v1/reels` | `{ url, tripId?, caption? }` → Gemini extraction. Requires Firebase ID token. Cached by video id. |

## Deploy (Google Cloud)

```bash
# API → Cloud Run (build from repo root)
gcloud run deploy rtt-api --source . --region asia-northeast1 \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest,MAPS_SERVER_API_KEY=maps-server-key:latest \
  --set-env-vars CORS_ORIGINS=https://YOUR-WEB-DOMAIN,REQUIRE_APP_CHECK=true
# (uses apps/api/Dockerfile — pass --dockerfile or build with Cloud Build)

# Rules
firebase deploy --only firestore:rules,storage

# Web → Firebase App Hosting: create a backend in the console, root dir apps/web
```

## Security notes

- No secrets in this repo — `.env*` files are git-ignored. Keys live in Secret Manager.
- Firestore rules: trips and everything under them are readable only by members.
- The API only accepts YouTube / Instagram / TikTok links (SSRF guard) and treats reel text as data, never instructions.

## License

[MIT](LICENSE)
