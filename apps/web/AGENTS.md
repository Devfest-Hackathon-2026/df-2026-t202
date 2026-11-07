# apps/web: Next.js PWA (Firebase App Hosting)

Adds to the root `AGENTS.md`. Next.js **16** App Router, React 19, Tailwind CSS **v4**, Firebase JS SDK 13,
`@vis.gl/react-google-maps`, framer-motion.

## Next.js 16 changed APIs, so check before writing
Your training data may be older than this Next.js version. **Before using a routing, data-fetching, caching or config API,
read the bundled docs in `node_modules/next/dist/docs/`.** Known changes:
- `params` and `searchParams` in pages and layouts are **Promises**, so `await` them.
- Middleware is `proxy.ts`, not `middleware.ts`.
- Heed deprecation warnings from `next dev` and `next build`.

## Layout
```
src/app/                 Routes. Server components by default; add "use client" only for state, effects, Firebase, Maps
src/components/          Client and UI components, PascalCase.tsx, one component per file
src/lib/firebase.ts      firebase(): lazy client init (Auth, Firestore, App Check; emulators if NEXT_PUBLIC_USE_EMULATORS)
src/lib/api.ts           api<T>(path, {method, body}): the only way to call apps/api. Attaches ID + App Check tokens,
                         throws ApiError(status, code)
src/app/globals.css      Tailwind v4 entry + design tokens in @theme (there is no tailwind.config file)
public/manifest.webmanifest  PWA manifest
apphosting.yaml          App Hosting runtime + env (secrets referenced by name only)
```
Import alias: `@/*` → `src/*`.

## Design system
- Use the tokens in `globals.css` (`bg-paper`, `text-ink`, `text-muted`, `border-line`, `text-accent`/`bg-accent`,
  `text-gem`/`bg-gem` for hidden gems). Add new tokens to `@theme`. No hard-coded hex values in components.
- **Mobile first:** design at 390 px, then scale up with `sm:`/`md:`. The demo runs as a phone-sized PWA.
  Tap targets ≥ 44 px, safe-area padding at the bottom.
- framer-motion for the swipe deck (drag + spring) and small transitions. Respect `prefers-reduced-motion`.
- Every swipe gesture has a button fallback (like/dislike) with labels. Check accessibility and keyboard use.
- No UI component library is installed yet (Notion plans shadcn/ui). Adding one is a decision for `docs/DECISIONS.md`.

## Data rules
- **Server-side keys never reach the browser.** Client env is `NEXT_PUBLIC_*` only: Firebase web config, API URL,
  `NEXT_PUBLIC_MAPS_BROWSER_KEY` (domain-restricted), App Check site key.
- Call the API only through `src/lib/api.ts`. Validate the response with the `@rtt/shared` schema.
  Map `ApiError.code` to a human message, and never show raw codes.
- **Live data uses Firestore `onSnapshot`** (chat, swipes, reel status, deck, itinerary). Subscribe in `useEffect`
  and return the unsubscribe. Don't poll the API for these.
- Clients write only what `firestore.rules` allows: own `users/{uid}`, trip create (owner = self, `memberIds = [self]`),
  owner edits of trip settings, `messages` (senderId = self, text ≤ 2000), and own `swipes/{uid}_{cardId}`.
  Everything else goes through the API.
- Places details and photos are fetched fresh through the API by place ID. Never persist them client-side.

## Required UI copy and labels
- Hidden-gem card: "Estimate from ratings, not crowd data."
- Itinerary summary: "Your trip includes X local spots." (X = number of gems in the plan)
- Seeded or mocked content: a visible **"Demo data"** badge.
- Maps and Places content: show Google attribution and photo `authorAttributions` as the Maps terms require.

## Every async view has four states
Loading (skeleton or progress; reel analysis takes seconds, so show it), empty (what to do next), error (human message +
retry), success. Never leave a blank screen or an endless spinner.

## Test
- `pnpm --filter @rtt/web typecheck && pnpm --filter @rtt/web build`.
- Check in the browser at 390 px against the emulators (root `AGENTS.md` → Local dev modes, Mode A).
  Golden-path changes: run through the whole demo path in `docs/PRODUCT.md`, not just the screen you changed.
