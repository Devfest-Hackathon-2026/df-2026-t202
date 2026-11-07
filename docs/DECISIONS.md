# Decision log ("Own the Why")

Feeds the "reasons for technology choices, with pros and cons" section of the submission doc (judging item 1b).
Log every decision a judge might ask "why?" about. **Humans fill in "Considered" and "Why".** Agents
propose the options and draft the entry, and a person confirms it.

Format:
```
## D<n>. <decision> (<date>, <who>)
- Chose: …
- Considered: … (pros/cons)
- Why: …
```

## D1. Gemini through Genkit for all AI work (Nov 2026)
- Chose: Genkit flows with Zod in/out schemas; Gemini Flash for reels, Pro for the itinerary.
- Considered: _TODO_
- Why (from the system design): Gemini reads public YouTube links directly (video and audio in one call). Genkit gives typed flows,
  tool calling, structured output and a tracing UI. Flash is cheap for high volume; Pro runs only once per trip.

## D2. Firestore real-time listeners for chat and swipes
- Chose: Firestore `onSnapshot` from the client; API writes the backend-only collections.
- Considered: _TODO_ (e.g. our own WebSocket server)
- Why: live chat and swipe results with no socket server to run; data split per trip.

## D3. Cloud Tasks for reel analysis
- Chose: queue one task per reel → Cloud Run worker.
- Considered: _TODO_ (e.g. synchronous request, which is the current code)
- Why: analysis takes seconds; retries with backoff; caps concurrent Gemini calls to stay inside quota.

## D4. Hidden gem = rating ≥ 4.3, 20–299 reviews, ≤ 800 m, same category
- Chose: a rule over Places data, with a visible "estimate, not crowd data" disclaimer.
- Considered: _TODO_
- Why: Places gives rating and review count; no crowd data is available, so we say so honestly.

## D5. TypeScript monorepo (Next.js + Hono + shared Zod)
- Chose: pnpm monorepo, one language front to back.
- Considered: _TODO_
- Why: shared types between web, API and Firestore schema; faster pair-debugging before the deadline.

## D6. Gemini through Vertex AI, not AI Studio (2026-11-08, team)
- Chose: Genkit `vertexAI` plugin, authenticated by the Cloud Run service account (ADC).
- Considered: AI Studio API key (already wired up; free tier, but rate-limited and not covered by the credit).
- Why: the organizers' $20 Google Cloud credit covers Vertex AI but not AI Studio. It also removes a secret,
  since there's no Gemini key to store or leak. IAM controls access instead.

## Open
- ~~Product name~~ → RelaySnap (decided 2026-11-08).
- Booking provider (Jinko or an alternative), or cut it.
