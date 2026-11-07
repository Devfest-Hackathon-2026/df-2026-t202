# packages/shared: the contract between web, API and Firestore

Adds to the root `AGENTS.md`. Shipped as TypeScript source (`main: ./src/index.ts`, no build). Next transpiles it
(`transpilePackages`), and tsup inlines it into the API bundle.

## Contents
- `src/schemas.ts`: Zod schemas and types for Gemini output (`ReelExtraction`), API requests, and Firestore docs
  (`Trip`, `DeckCard`, `Swipe`, `ItineraryDay`), plus `HIDDEN_GEM_RULE` and `isHiddenGem`.
- `src/reelUrl.ts`: `parseReelUrl(input) → { platform, videoId, cacheKey, canonicalUrl } | null`. The domain allowlist
  (YouTube, Instagram, TikTok) **is our SSRF guard**.
- `src/index.ts`: re-exports. Export every new module from here.
- `src/shared.test.ts`: Vitest.

## Rules
- **Zod v3 only.** Never `zod/v4`, never upgrade, because Genkit breaks.
- Runtime dependencies: zod only. No Node-only (`fs`, `crypto`) or browser-only (`window`) APIs, since both apps import this.
- Imports inside this package have no file extension (`./schemas`).
- Naming: `export const FooSchema = z.object(...)` + `export type Foo = z.infer<typeof FooSchema>`.
- Schemas that Gemini fills: `.describe()` every field (the model reads it), `.max()` every array and string that comes
  from the model, enums over free strings where possible.
- Firestore doc schemas describe what is stored. Timestamps are written by the server, so keep them out of client
  write schemas.
- **A change to a Firestore doc schema** must update `firestore.rules`, `docs/ARCHITECTURE.md` (data model) and every
  reader and writer in the same commit. Renaming a field breaks existing documents, so prefer adding fields.
- Hidden gem: rating ≥ 4.3, 20–299 reviews, ≤ 800 m, same category. Change values only in `HIDDEN_GEM_RULE`.
- Every change to `parseReelUrl`, `isHiddenGem` or any scoring helper needs tests, including edge cases (lookalike hosts
  like `youtube.com.evil.com`, missing IDs, boundary values 4.3 / 20 / 300).

## Test
`pnpm --filter @rtt/shared typecheck && pnpm --filter @rtt/shared test`
