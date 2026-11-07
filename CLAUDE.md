# CLAUDE.md

Hackathon project for DevFest Hackathon 2026 (Tourism). Deadline: **Nov 10 (Tue) 19:00 JST**. Deployed URL must stay up through Nov 14.

## Hard rules (from the organizers)
- Google tech must be the core stack; runtime must be Google Cloud. Third-party LLM APIs don't count — use Gemini via Genkit only.
- This repo is **public**. Never commit keys (.env, service-account JSON). GitHub Actions/Pages are disabled here.
- No fabricated demo behavior: if something is mocked, label it in the UI.

## Stack
- pnpm monorepo, TypeScript everywhere. Node 22.
- `apps/web`: Next.js App Router + Tailwind v4, Firebase JS SDK, @vis.gl/react-google-maps, framer-motion.
- `apps/api`: Hono on Cloud Run, Genkit + `@genkit-ai/google-genai` (Gemini), firebase-admin. Bundled with tsup.
- `packages/shared`: Zod **v3** schemas (Genkit depends on zod 3 — don't upgrade to zod 4), reel URL parser, hidden gem rule.

## Conventions
- Every Gemini call is a Genkit flow in `apps/api/src/ai/flows/` with Zod input/output schemas.
- All Maps/Gemini calls with server keys happen in the API, never in the browser.
- Firestore: store Places **place IDs**, not copied place details.
- Backend-only collections (`reels`, `invites`, `trips/*/deck`, `trips/*/itinerary`) are written only by the API; keep `firestore.rules` in sync with any schema change.
- Run `pnpm typecheck && pnpm test` before committing.

## Next steps (MVP order)
1. Trip create + invite link (API) and group chat (Firestore listeners).
2. Places lookup for extracted places → deck builder flow → swipe UI.
3. Swipe scoring → `buildItinerary` flow (tools: Places, Routes) → map page.
4. Hidden gem lookup (Places Nearby Search + `isHiddenGem`).
5. Move reel analysis to Cloud Tasks worker; seed a demo trip.
