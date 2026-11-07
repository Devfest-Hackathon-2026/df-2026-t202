# RelaySnap: system design

Source: Notion "RelaySnap System Design" (Nov 8, 2026). This is the **target** design. Check the status table
before assuming a piece exists. Update the table when you ship something.

## Status (update as you build)
| Piece | Status | Where |
| --- | --- | --- |
| Hono API, auth + App Check middleware, rate limit, structured logs | ✅ built | `apps/api/src/index.ts`, `middleware/` |
| Reel import: allowlist, shared cache, `analyzeReel` flow (inline, not queued) | ✅ built | `routes/reels.ts`, `ai/flows/analyzeReel.ts` |
| Shared schemas, `parseReelUrl`, `isHiddenGem` | ✅ built | `packages/shared` |
| Firestore + Storage rules, emulator config | ✅ built | `firestore.rules`, `storage.rules`, `firebase.json` |
| Web: reel import page, Firebase client, API client | ✅ built | `apps/web/src` |
| Trips: create, invite, join, chat | ⬜ todo | MVP 1 |
| Places lookup, `buildDeck`, swipe UI | ⬜ todo | MVP 2 |
| Swipe scoring, `buildItinerary`, map page | ⬜ todo | MVP 3 |
| Hidden-gem lookup + cards | ⬜ todo | MVP 4 |
| Seeded demo trip, min instances = 1 | ⬜ todo | MVP 5 |
| Cloud Tasks worker, booking, FCM, Cloud Storage video upload flow | ⬜ stretch | MVP 6 |

## Architecture
The web app (PWA on Firebase App Hosting) calls **one Cloud Run API** and listens to **Firestore** for live
chat and swipe results. Reel analysis runs async through **Cloud Tasks** → a Cloud Run worker. The API and
the worker both call Gemini, Places and Routes. Only booking leaves Google, behind a swappable adapter.

```
PWA (Next.js, App Hosting) ──HTTPS + ID token + App Check──▶ Cloud Run API (Hono + Genkit)
   │  ▲                                                        │   │      │
   │  └──── Firestore live listeners (chat, swipes, reels) ◀──┘   │      └─▶ Cloud Tasks ─▶ Cloud Run worker
   └──▶ Maps JS API (browser key)                                 │                          │
                                         Gemini · Places · Routes ◀───────────────────────────┘
                                         Secret Manager · Cloud Storage · Booking adapter (3rd party)
```

## Google services and why
Every core job runs on a Google service, which covers judging item 1 (use of Google tech). Only booking is third-party.

| Layer | Service | Job | Why |
| --- | --- | --- | --- |
| AI | Gemini Flash | Watch reels, pull out places and vibe as JSON | Reads public YouTube links directly; video and audio in one call |
| AI | Gemini Pro + function calling | Itinerary, next swipe cards, explain picks | Calls Places and Routes as tools, so plans use real places |
| Maps | Places API (New) | Card details, hours, ratings, nearby search | Source of rating and review count for the hidden-gem rule |
| Maps | Routes API | Travel time between stops | Orders stops to cut walking and transit time |
| Maps | Maps JavaScript API | Map page with day routes | A map users already know and trust |
| Runtime | Cloud Run | API + reel worker | Required Google Cloud runtime; scales to zero and out |
| Async | Cloud Tasks | One job per reel | Analysis takes seconds; keeps the UI responsive; retries |
| Data | Firestore | Users, trips, chat, swipes | Real-time listeners without our own socket server |
| Files | Cloud Storage | Uploaded video (IG/TikTok fallback) | Gemini reads from storage; lifecycle deletes after 7 days |
| Identity | Firebase Auth | Google sign-in | One tap; ID token verified on every API call |
| Abuse | Firebase App Check | Only our app calls our backend | Stops scripts burning Gemini and Maps quota |
| Secrets | Secret Manager | Maps, booking keys (Gemini uses Vertex AI + service account, so it has no key) | Keys never reach the browser or the repo |
| Hosting | Firebase App Hosting | Web app (PWA) | Git-push deploys, CDN, Cloud Run underneath |
| Ops | Cloud Logging + Monitoring | Logs, error alerts, latency | Catch failures before the demo does |
| Notify | Firebase Cloud Messaging | Invite and "plan ready" pushes | Brings friends back to swipe |

## Key flows

### Reel analysis
1. User pastes a link. The API checks the domain (YouTube, Instagram or TikTok) and rejects anything else.
2. Check the cache by video ID. Already analyzed → return it instantly.
3. New link → write `reels/{id}` as `processing` and queue a Cloud Task.
4. Worker calls Gemini: YouTube by URL; Instagram and TikTok by caption, or by the uploaded file in Cloud Storage.
5. Gemini returns structured JSON: places, food, activities, vibe tags, city.
6. Worker matches each place name to a Places place ID, then marks the reel `done`.
7. The app listens to the reel doc, so results appear without a refresh.

*Current code:* analysis runs synchronously in `POST /v1/reels`. Moving it to Cloud Tasks is MVP step 5.

### Group swipe
1. Organizer creates a trip and shares an invite link (signed token, expires in 7 days).
2. Backend builds **one** deck of about 20 cards from the group's reels plus popular places at the destination.
3. Every member gets the same deck, in the same order.
4. Each swipe is written to `trips/{id}/swipes`.
5. When everyone finishes (or the organizer closes voting), the backend scores each card. Everyone liked it → **Must do**.
   Most liked it → **Options to vote on**. Nobody liked it → dropped.

### Itinerary
1. Gemini gets the Must-do list, dates, budget and the group's vibe tags.
2. Gemini calls tools: Places (hours, location) and Routes (travel time).
3. Output: days → ordered stops, each with a time slot, a "why this pick" line, and the reel it came from.
4. Backend validates it: every stop has a real place ID, and no stop is closed at its slot. A failed check triggers one regeneration.
5. Saved to `trips/{id}/itinerary`; the map page draws it.

### Hidden gem
1. For each popular stop, run Places Nearby Search in the same category, within ~800 m (about a 10-minute walk).
2. Keep places with rating ≥ 4.3 and < 300 reviews, plus ≥ 20 reviews so one 5-star review can't qualify.
3. Pick the best-rated one. Skip any place already in the plan.
4. Show it as a card beside the stop, with the "Estimate from ratings, not crowd data." note.

## Data model (Firestore)

| Collection | Key fields | Read / write |
| --- | --- | --- |
| `users/{uid}` | name, homeCountry, language | Owner only |
| `trips/{tripId}` | destination, dates, budget, ownerId, memberIds[], status | Members read; owner edits settings |
| `trips/{tripId}/messages/{id}` | senderId, text, reelId?, createdAt | Members read and create; no edits |
| `trips/{tripId}/reels/{id}` | url, platform, addedBy, reelRef | Members read; **API writes** (validated link) |
| `trips/{tripId}/deck/{cardId}` | placeId, title, photoRef, sourceReelId, order | Members read; API writes |
| `trips/{tripId}/swipes/{uid_cardId}` | uid, cardId, liked | Member writes only their own |
| `trips/{tripId}/itinerary/{dayN}` | stops[]: placeId, slot, why, sourceReelId, gemPlaceId | Members read; API writes |
| `reels/{videoId}` (shared cache) | status, extracted JSON, placeIds[] | API only |
| `invites/{token}` | tripId, expiresAt, maxUses | API only |

- Store Places **place IDs**, not copied names or ratings. Fetch fresh details when showing them (Maps Platform terms).
- Swipe doc ID is `uid_cardId`, so a member can't double-vote.
- Note: the Notion table says members *create* `trips/*/reels`. `firestore.rules` makes it API-only so every link
  passes the allowlist. The rules file is authoritative.

## Security
**Identity and access**
- Firebase Auth on every request. Cloud Run verifies the ID token before anything else.
- Rules: a trip and everything under it is readable only if `request.auth.uid in memberIds`.
- Backend-only collections are written by the service account, never by clients. The Admin SDK bypasses rules, so the API checks membership in code.
- Invite links are signed, single-trip, expire in 7 days, and have a use cap.

**Keys and quota**
- Places and booking keys live in Secret Manager. Gemini runs on Vertex AI with the service account (IAM, no key). Only that service account can read the secrets.
- The browser gets only a Maps JS key, restricted to our domain and the Maps JS API.
- App Check on Firestore and the API. Per-user rate limits (e.g. 20 reel imports per hour).
- Budget alerts on the Google Cloud project. The credit is only $20.

**Untrusted input**
- Link allowlist: youtube.com, youtu.be, instagram.com, tiktok.com. The backend never fetches arbitrary URLs (SSRF).
- Captions and transcripts are data. Gemini returns a fixed JSON schema. Reel text never becomes an instruction or a tool call.
- Uploaded videos: size and type checks, private bucket, deleted after 7 days.

**Privacy**
- Store only what the plan needs: name, trips, swipes. No contacts, no location history.
- No payment data touches our servers. Booking uses the provider's hosted checkout.

## Scale, reliability, cost
- The API and the worker scale separately, so a burst of reel imports doesn't slow chat or the map.
- Cloud Tasks caps concurrent Gemini calls, so we stay inside quota instead of failing.
- Shared reel cache by video ID: a viral reel is analyzed once. This is the biggest cost saver.
- Flash for reels (high volume); Pro only for the itinerary (once per trip).
- Cloud Tasks retries with backoff. After 3 failures the reel shows "couldn't read this one".
- If Gemini is down, the swipe deck still works from popular Places results.
- Demo day: Cloud Run min instances = 1 (no cold start), plus a labeled pre-analyzed demo trip as backup.
- Prompts and hidden-gem thresholds live in config, not scattered through code.
- Booking sits behind one adapter interface.
- Observability: structured JSON logs per request with tripId; alerts on error rate and Gemini latency.

## Tech stack
| Layer | Choice |
| --- | --- |
| Language | TypeScript everywhere |
| Frontend | Next.js App Router + React, Tailwind CSS (+ shadcn/ui planned), framer-motion swipe |
| Maps UI | @vis.gl/react-google-maps |
| Client SDK | Firebase JS SDK (Auth, Firestore, App Check, FCM) |
| API | Node.js + Hono on Cloud Run |
| AI | Genkit + Google GenAI plugin. Flows: `analyzeReel`, `buildDeck`, `buildItinerary`, `explainPick` |
| Validation | Zod v3 (Gemini output, API input, Firestore docs) |
| Server SDKs | firebase-admin; Places (New) and Routes over REST |
| Queue / data | Cloud Tasks; Firestore + Cloud Storage |
| Hosting | Firebase App Hosting (web), Cloud Run (API + worker) |
| Repo | pnpm monorepo: `apps/web`, `apps/api`, `packages/shared` |
| Local dev | Firebase Emulator Suite, Genkit Developer UI |
| Testing | Vitest (units); Playwright demo-flow smoke test planned |
| CI/CD | Notion says GitHub Actions → Artifact Registry → Cloud Run. **Actions are disabled in this repo**, so deploy manually with `gcloud`/`firebase`, or use Cloud Build triggers |
