# Person B: why we built the plan engine this way

Hackathon theme: **"Own the Why, Build with Intent."** This file records every important decision in Person B's part
of the back end (the plan engine): what we chose, which options we compared, and why. It feeds the "Rationale /
Pros and Cons" section of the submission document (PLAN.md 16, 18).

How we work: before an important choice, the AI assistant lists 2–3 options with pros and cons, and Person B decides.
Each decision is added here at the time it is made.

---

## Decisions made while building

### 1. Start Person B's branch from `main`
- **Date / task:** 2026-11-08, setup
- **Options considered:**
  - Start from Person A's unmerged `feat/shared-contract` branch. Pro: has the new shared `models.py` right away.
    Con: our PR depends on theirs; both branches create `routers/plan.py`.
  - **Start from `main`** ✅. Pro: an independent branch and a clean PR that only holds Person B's files.
    Con: uses the older `models.py` until Person A's PR is merged, then we merge `main` in.
  - Wait until Person A merges. Pro: no catch-up later. Con: blocks Person B's work.
- **Why:** Person B can start now without depending on unmerged work, and Person A's files stay untouched.
- **Decided by:** Person B

### 2. Function names follow `BACKEND_PERSON_B.md`, not the earlier stub patch
- **Date / task:** 2026-11-08, setup
- **Options considered:**
  - Use the stub patch as written (`draft_plan`, `run_plan`, `compute_leg`). Con: doesn't match the agreed contract.
  - **Use the names in the shared contract** (`planner.draft`, `pipeline.run`, `routes.leg`, …) ✅.
- **Why:** Person A codes against the contract (section 3), so the names must match it, or the two halves won't connect.
- **Decided by:** the team contract

### 3. Ask Places for opening hours
- **Date / task:** 2026-11-08, T1 (`services/places.py`)
- **Options considered:**
  - **Keep opening hours in every search** ✅. Pro: lets us warn "you arrive after this place closes".
    Con: every search moves to Google's most expensive Places tier (roughly $35 vs $32 per 1,000 calls, and fewer free
    calls per month: about 1,000 vs 5,000; check the current pricing page).
  - Drop opening hours. Pro: cheaper, bigger free allowance. Con: plans can send people to closed places.
  - Look them up only for some stops with a second call. Pro: saves money. Con: more code, an extra call per stop.
- **Why:** Realistic plans are the point of the product, and the cost stays small with the cache (about 25 stops per plan).
- **Decided by:** Person B

### 4. Driving times ignore live traffic
- **Date / task:** 2026-11-08, T1 (`services/routes.py`)
- **Options considered:**
  - **`TRAFFIC_UNAWARE`** ✅. Pro: cheapest Routes tier, fastest response.
  - `TRAFFIC_AWARE`. Con: costs more and is slower.
- **Why:** Trips are planned weeks or months ahead. Today's traffic says nothing about the trip day, so live traffic
  would cost more for no gain.
- **Decided by:** Person B

### 5. When Places fails: retry once, then fail loudly
- **Date / task:** 2026-11-08, T1 (`services/places.py`)
- **Options considered:**
  - Fail at once. Pro: simplest; problems get noticed. Con: one short hiccup fails the whole plan.
  - Treat a failure as "place not found". Pro: the plan always finishes.
    Con: a broken key silently produces empty plans, and nobody notices.
  - **Retry once, then fail** ✅. Pro: survives short hiccups but still reports real problems. Con: a little more code.
- **Why:** For a live demo, a short Google hiccup shouldn't break the plan, but a real problem (bad key, quota used up)
  must be visible. We only retry temporary errors (rate limit, server errors 500/502/503/504, network drops), because
  retrying a wrong key or a bad request gives the same error again.
- **Decided by:** Person B

### 6. When Routes fails: keep the AI's estimate and show "Please check"
- **Date / task:** 2026-11-08, T1 (`services/routes.py`)
- **Options considered:**
  - **Return "no route", so the pipeline keeps the Planner's minutes with `estimate: true`** ✅. Pro: the plan still
    finishes, and the UI shows a "Please check" badge on that leg. Con: an API problem shows up as estimates, not as an error.
  - Fail the plan like Places does. Pro: problems are loud. Con: one missing route (for example, no transit data in a
    country) breaks a plan that is otherwise fine.
- **Why:** A missing route is normal (ferries, countries without transit data), and the product already has an honest
  "estimate" badge for this case. Failures are still logged.
- **Decided by:** Person B

### 7. One `search_text` serves both the plan pipeline and Person A's chat
- **Date / task:** 2026-11-08, T1 (`services/places.py`). Person A asked for `search_text(query, lang)` returning the
  `PlaceRef` shape (`label`, `placeId`, `countryCode`, `lat`, `lng`) to resolve free text like "I want to go to Kyushu".
- **Options considered:**
  - **One function that also returns `label`** ✅. Pro: Person A's code works as is (`PlaceRef` ignores the extra keys);
    one place to fix bugs. Con: chat lookups also pay for opening hours, but that's once per trip.
  - A separate `resolve_place()` with a cheaper field mask. Pro: cleaner split, slightly cheaper.
    Con: Person A changes their import; more code for a tiny saving.
- **Why:** The simplest way to connect the two halves, at almost no extra cost.
- **Decided by:** Person B

### 8. Places errors during chat: keep raising, Person A catches them
- **Date / task:** 2026-11-08, T1. Decision 5 makes `search_text` raise when Google fails twice. Person A's chat code
  didn't expect errors (their temporary copy returned `None`).
- **Options considered:**
  - **Keep raising; Person A wraps the call in `try/except` and shows "couldn't look that up, try again"** ✅.
    Pro: decision 5 stays true in the plan pipeline. Con: Person A must add two lines.
  - Return `None` on failure. Pro: no change for Person A. Con: reverses decision 5, so a broken key silently looks
    like "not found" in plans too.
- **Why:** Each caller knows best how to show a failure: chat can ask again, and the pipeline should stop.
- **Decided by:** Person B. Person A implemented the chat side (`docs/decisions.md` D34).

### 9. Cache only what Google allows: the place ID
- **Date / task:** 2026-11-08, T1. Google's
  [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies) allow storing
  place IDs forever and coordinates for up to 30 days. Names, addresses and opening hours may not be stored. The team
  plan (PLAN.md 7.1) cached full results with no expiry.
- **Options considered:**
  - **Follow Google's rules** ✅. `cache_places` keeps only `query → placeId`. A cache hit looks the place up fresh
    by ID. Pro: compliant (licensing is judged), and repeat runs get exactly the same place. Con: saves few calls; our
    demo volume fits in the monthly free allowance.
  - Cache everything for 30 days. Pro: fewer calls. Con: storing names and hours isn't permitted, even briefly.
  - No Places cache. Pro: simplest. Con: differs from the team plan; repeat runs may pick a different place.
- **Why:** We'd rather pay a few cents than break the terms of the data our product depends on. While building it, we
  dropped the 30-day coordinate cache too: the fresh lookup by ID returns the coordinates anyway, so caching them
  only added expiry code.
- **Decided by:** Person B. PLAN.md 7.1 (`cache_places` fields) needs a small PR agreed with Person A.

### 10. If the cache itself fails, skip it and keep going
- **Date / task:** 2026-11-08, T1. Found when Person A's code merged: without Firestore credentials, the cache read
  raised an error that neither the plan pipeline nor the chat expected.
- **Options considered:**
  - **Skip the cache: log a warning and call Google directly** ✅. Pro: plans and chat keep working through a
    Firestore hiccup. Con: a broken cache is only visible in the logs.
  - Fail like other errors. Pro: simpler, very visible. Con: a cache problem breaks plans even though Places works.
- **Why:** The cache only saves calls; it isn't needed for a correct answer.
- **Decided by:** Person B


### 11. Only the trip owner can generate a plan
- **Date / task:** 2026-11-08, T2 (`routers/plan.py`)
- **Options considered:** **Owner only (`require_owner`)** ✅ · Any member (`require_member`, the spec's wording).
- **Why:** Shared links are view only (PLAN.md F5). With "any member", a friend with the link could overwrite the plan
  and use up the owner's 20 plans a day.
- **Decided by:** Person B (differs from the spec's wording; Person A told)

### 12. The stub returns the existing 4-day demo plan
- **Options considered:** **Keep the 4-day `demo_plan.json`** ✅ · Write the small 2-day plan from the spec.
- **Why:** It's already valid and gives the front end real cases to design for: 4 day colors, a ferry leg marked
  "Please check", Japanese local names.
- **Decided by:** Person B

### 13. The stub steps through the progress stages
- **Options considered:** **spots → routes → videos, about 1 s each** ✅ · Save instantly.
- **Why:** The front end can build the progress screen now instead of waiting for T4. The pauses go away in T4.
- **Decided by:** Person B

### 14. Stub calls don't count toward the daily plan limit
- **Options considered:** **Don't count** ✅ · Count them now.
- **Why:** The stub calls no paid API, so front-end developers can test freely. T4 adds `check_plan_limit`.
- **Decided by:** Person B

### 15. `demo_plan.json` moves into `app/fixtures/`
- **Found:** the Cloud Run image only copies `app/` (`tests/` is excluded), so the stub would crash once deployed.
- **Options considered:** **Move the file into `app/`** ✅ · Person A changes the Dockerfile to copy `tests/fixtures`
  (touches their files, puts test files in production) · The stub works locally only.
- **Why:** It works on Cloud Run without touching Person A's files. Only path references change.
- **Decided by:** Person B


### 16. Planner model: `gemini-3.5-flash`
- **Date / task:** 2026-11-08, T3 (`agents/planner.py`)
- **Options considered:** **gemini-3.5-flash** ✅ (fast in Tokyo, cheap; Person A's D18) · a Pro model (slower,
  pricier, may not be in Tokyo).
- **Why:** PLAN.md says Flash first, Pro only if plan quality is low. The Kyushu test plans were good with Flash.
- **Decided by:** Person B

### 17. Plan quality over the 30-second target: the model's default thinking
- **Options considered:** **Default thinking** ✅ · LOW · MINIMAL (Person A uses it for the Concierge).
- **Why:** A good plan matters more than speed. Measured on the Kyushu demo: the draft takes **27–31 s** with default
  thinking, so the whole pipeline will take longer than 30 s. The front end shows progress meanwhile.
- **Decided by:** Person B. PLAN.md 9.3 and api/AGENTS.md updated to match.

### 18. No Google Search grounding (for now)
- **Options considered:** **No grounding** ✅ · Google Search grounding.
- **Why:** Google requires apps to display its "Search Suggestions" with every grounded result, which needs a new
  field in the shared `models.py` plus front-end work. It's also billed per search query. Places and Routes already
  verify every stop and travel time in T4. We can add it later if plans name closed places.
- **Decided by:** Person B (first chose grounding, then changed after reading Google's display rule)

### 19. No hotel stops; the hotel area goes in `stay`
- **Found in the first test run:** Gemini added made-up hotels ("Takachiho Ryokan") that Google Maps can't verify.
- **Options considered:** **Area only** ✅ · Gemini names a real hotel each night.
- **Why:** Only real, verifiable places on the timeline. Naming a hotel looks like a recommendation we can't stand
  behind (price, availability), and booking is out of scope.
- **Decided by:** Person B

### 20. Meals are specific real restaurants
- **Found in the first test run:** vague stops like "Lunch near Dazaifu" can't be found on Google Maps.
- **Options considered:** **Specific well-known restaurants** ✅ · Food areas or markets.
- **Why:** Most useful for travelers, and each meal gets a video. Places verification in T4 catches names that don't
  exist. Result: the second run named real places (Shippoku Hamakatsu, Katsuretsutei, Kokutei ramen).
- **Decided by:** Person B


### 21. Missing places: one Planner replacement round, then drop with a note
- **Date / task:** 2026-11-08, T4 (`pipeline.py`)
- **Options considered:** **Ask the Planner to replace only the missing stops** ✅ (the spec) · Drop them at once.
- **Why:** Better plans. It only costs time and money when something is missing; a stop that still isn't found is
  removed and listed in `checks`.
- **Decided by:** Person B

### 22. Reject Places matches in another country
- **Options considered:** **Same country as the destination** ✅ · Distance from the destination · No check.
- **Why:** Simple, works worldwide, catches the worst mix-ups. Skipped when the destination has no single country.
- **Decided by:** Person B

### 23. /plan refuses double runs and unfinished chats
- **Options considered:** **409 when a run is in progress or the chat isn't at "ready"** ✅ · Only block double runs ·
  No guards.
- **Why:** Each run costs Gemini and Maps money and counts toward the daily limit; a double tap would pay twice and save
  two plans. A "planning" status older than 10 minutes counts as a crashed run, so a trip can't get stuck.
- **Decided by:** Person B

### 24. Search Places near the Planner's rough location, reject matches over 30 km away
- **Found in the first real pipeline run:** Gemini named a restaurant "かじ屋" in Saga; Places matched a different
  "かじ屋" near Kumamoto, 100 km away (same country, so decision 22 didn't catch it). The detour added 3+ hours.
- **Options considered:** **Planner gives rough lat/lng; search near it; > 30 km away = wrong match** ✅ · Search
  near the previous stop (sequential, slower, errors spread) · Leave it.
- **Why:** Gemini knows roughly where places are, so this costs no extra calls and works worldwide. Places still sets
  the exact coordinates. Re-run: every stop in the right town, 31 s, no repair round needed.
- **Decided by:** Person B


### 25. A separate API key for YouTube
- **Date / task:** 2026-11-08, T5 (`services/youtube.py`)
- **Options considered:** **New key restricted to YouTube Data API v3** ✅ · Add YouTube to the Maps key.
- **Why:** If one key leaks, the other APIs stay safe, and usage is easier to see per key.
- **Decided by:** Person B

### 26. Shorts for every stop except start, end and transport
- **Options considered:** **All except start/end/transport** ✅ · Sights only, no food · Every stop.
- **Why:** YouTube allows about 100 searches a day. Stations, ports and rental-car offices give weak videos;
  restaurants are worth a video. About 15 searches per new plan.
- **Decided by:** Person B

### 27. Skip "Made for Kids" videos
- **Found:** YouTube's developer policy (III.E.4.j) requires checking each video's Made for Kids status and turning
  off tracking for those.
- **Options considered:** **Drop them with one cheap `videos.list` call** ✅ · Keep them and have the front end turn off
  tracking (needs a `models.py` field and front-end work).
- **Why:** Compliant with no contract change; travel Shorts are rarely made for kids.
- **Decided by:** Person B

### 28. The demo pre-cache runs the pipeline twice
- **Options considered:** One run (the spec) · **Two or three runs** ✅ (default 2, `--runs 3` possible).
- **Why:** Gemini varies between runs, so two runs cover more of the stops the live demo may pick. Result: 36 places
  cached with real videos, about a third of one day's YouTube quota. The cache lasts 7 days (YouTube allows 30).
- **Decided by:** Person B


### 29. Night views never move earlier than the Planner's time
- **Date / task:** 2026-11-09, end-to-end test. Found: recalculating times from real legs put Mt. Inasa at 16:55,
  in daylight.
- **Options considered:** **Never earlier than Gemini's time; the stop before gets the extra time** ✅ · Calculate
  sunset from coordinates (needs a time-zone guess per country, can be an hour off) · Only warn.
- **Why:** Gemini already schedules night views after sunset; this keeps that with 3 lines and works worldwide.
  Re-run: Mt. Inasa at 20:45.
- **Decided by:** Person B

### 30. One rental-car branch for pickup and return
- **Found:** trips started at one rental company and ended at another, because Maps matched a vague "rental car at the
  airport" to random companies; some names showed in Japanese in English plans.
- **Options considered:** Start and end at the station or airport (car in `note` and `checks`) · **One specific
  rental-car branch at both ends, same name** ✅.
- **Why:** More concrete for travelers. Same name → same Maps result at both ends. We keep Gemini's names for start
  and end stops (Google called the pickup branch "... Car Return") and Gemini's English name when Maps only has a
  Japanese one. Japanese plans may show the branch in English (Gemini's name); left as is: cosmetic only.
- **Decided by:** Person B

### 31. No cities or regions as stops
- **Found:** "Nagasaki" (the whole city) appeared as a stop.
- **Options considered:** **Prompt rule + code check** ✅ (a Places result typed as a city/region and not as a place
  goes to the replacement round; needs the `types` field) · Prompt only.
- **Why:** Reliable: Gemini may still slip; the check catches it.
- **Decided by:** Person B


### 32. YouTube: at most 4 searches at once; stop searching once the daily quota is used up
- **Date / task:** 2026-11-09, end-to-end rerun. Found: YouTube answered 429 for many stops. First I thought it was
  too many parallel searches, but the error said **"Search Queries per day"**: our test runs had used up the daily
  quota (about 100 searches).
- **Options considered:** **Keep 4 at a time, no retry; on a quota error stop searching until YouTube's reset
  (midnight Pacific = 17:00 JST)** ✅ · 4 at a time + retry once (each retry just fails again when the quota is gone)
  · Revert.
- **Why:** No wasted calls or waiting when the quota is gone: tested, 3 stops → 1 YouTube call in 0.2 s. The demo
  stops are pre-cached, so they need no quota. Lesson: tests with an empty cache spend real quota, so keep them few.
- **Decided by:** Person B

### 33. Shorts: search for travel videos, rank travel first, then views
- **Date / task:** 2026-11-09, testing the deployed app. Found: many Shorts named the spot but were not about visiting
  it (not useful for planning a trip).
- **My idea:** (a) sort by views, popular travel Shorts first; (b) prefer travel hashtags (`#japantravel`, `#旅行`,
  `#osakatravel`, `#osakacastle`), i.e. look for `#<place>travel` first.
- **Options considered:** **One search with a travel word (`大阪城 観光 shorts` / `Osaka Castle travel shorts`), 10
  results, then rank by travel signs in title, description and tags, then views** ✅ · Exact hashtag search first, then
  a plain search (often empty for small spots, up to 2× quota) · Views only (`order=viewCount` brings viral clips that
  only share a word with the spot). Second choice: keep videos without a travel sign but rank them last ✅ · drop them
  (more stops with no Short).
- **Why:** Same quota per plan: a search costs 100 units for 5 or 10 results, and the `videos.list` call we already make
  for "Made for Kids" (1 unit) also returns tags, description and views. Views only break ties, because a popular
  non-travel clip is still non-travel. The hashtag idea becomes a ranking signal instead of a search that can be empty.
  Old cache entries are re-searched (cache version `v: 2`), so the demo must be pre-cached again.
- **Decided by:** Person B (team log: D81)

### 34. A "train" route that only walks is no route; legs always name the mode
- **Date / task:** 2026-11-09, testing the deployed app. Found: Day 2 Osaka, Osaka Castle → Kuromon Market showed
  "Osaka Metro Chuo Line · 59 min". Unclear if 59 min is walking or riding, and nobody walks 59 min.
- **Cause:** Routes has no transit data for Japan and answered the TRANSIT request with a walk-only route (59 min).
  With no line on it, we fell back to the Planner's line name, so a walk looked like a metro ride, and the
  "walk over 30 min becomes a ride" rule (D78) never ran.
- **Options considered (ride time when there is no real train route):** **The Planner's train time, marked
  "about"** ✅ · Car time + 10 min (a road time, not a train time). **Label:** **Mode first, then line, then time** ✅
  · Mode icon + line · Icon + mode + line.
- **Why:** The Planner named the line, so its time for that line fits; it is marked as an estimate either way. The
  mode word makes walking vs riding obvious in both the timeline and the shared text.
- **Decided by:** Person B (team log: D82)

---

Team log: decisions 3–6, 9–10 and 11–15, 16–20, 21–24, 25–28, 29–32 are also in `docs/decisions.md` as D35–D40, D41–D43, D44–D46, D47–D50, D51–D53 and D54–D57. Decisions 7 and 8 are covered there by
Person A's D21 and D34.

---

## Coming up (to decide in T3)
- **Gemini model for the Planner.** Person A measured `gemini-3.5-flash` in `asia-northeast1` (Tokyo) at about 1.6 s
  per call. `gemini-3.8-flash` isn't available in Tokyo and is slower on the global endpoint.
- **Thinking level for the Planner.** `generate_json(..., thinking=)`: `"MINIMAL"` is about 3x faster. `None`
  (the model's default) is better for plan quality.

---

## Decisions from the team plan (BACKEND_PERSON_B.md section 8)

These were decided when the team split the work. They shape everything above.

| Decision | Option we rejected | Why |
| --- | --- | --- |
| AI writes a draft first, then Places and Routes verify it | Trust the AI's plan | LLMs invent places and travel times. Checking against real data makes plans realistic. |
| Router and Media are plain code, not AI agents | Let an LLM call the APIs | Deterministic, fast, cheap. |
| Flights and ferries are estimates with a badge | Compute them | No Google API computes flights or ferries. The badge is honest. |
| Shorts are searched by the local name, any language | Match the video language to the user | Many spots only have local-language videos, and a video shows a place well without words. |
| Cache Places and YouTube results | Call the APIs every time | Quota (YouTube allows about 100 searches a day) and cost. |
| Only one repair round for warnings | Repair until no warnings remain | Keeps plan generation under 30 seconds. |
| REST calls with `httpx` | Google's client libraries | One small dependency for Places, Routes and YouTube, with full control over field masks (which set the price). |
