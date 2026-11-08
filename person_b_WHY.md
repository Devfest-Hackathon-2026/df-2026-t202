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

---

Team log: decisions 3–6, 9–10 and 11–15 are also in `docs/decisions.md` as D35–D40 and D41–D43. Decisions 7 and 8 are covered there by
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
