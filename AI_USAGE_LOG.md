# Tripi — AI usage log

Where and how we used AI, and why there. Two parts: AI **inside the product** (Gemini on Vertex AI), and AI
**while building it** (coding agents). Every AI suggestion was reviewed by a human; the options and the person who
decided are in [`docs/decisions.md`](docs/decisions.md).

## In the product (Gemini on Vertex AI, google-genai SDK)
| Where | Model | What it does | Why AI here |
| --- | --- | --- | --- |
| Concierge (`api/app/agents/concierge.py`) | Flash | Free text → structured slot updates | People answer in free sentences; a fixed form can't read them. Cards cover the structured path |
| Planner (`api/app/agents/planner.py`) | Flash, default thinking | Slots + chat → draft day-by-day plan | Creative ordering and themes; verified afterwards with Places and Routes, because LLMs invent places and times |
| Planner repair (`planner.fix`) | Flash, LOW thinking | Unfound places and warnings (closed on arrival, long drives) → only the changed days | Swapping a closed stop for a nearby open one needs judgment; the server checks the result again |

**Where we chose not to use AI:** the next chat question (server code, `flow.py`), travel times (Routes API), places (Places API), video ranking (plain rules). These need to be correct and repeatable.

## In development (coding agents)
One line per meaningful use. Note what the AI proposed and what the team kept or changed.

| Date | Tool | Task | Human decision |
| --- | --- | --- | --- |
| 2026-11-08 | Claude Code | Agent instructions (AGENTS.md / CLAUDE.md) and docs from the kickoff slides and the team spec | Team reviewed |
| 2026-11-08 | Claude Code | Repo base for the revised PLAN.md: FastAPI skeleton, Pydantic models, Kyushu fixtures, Angular skeleton, Firestore rules | Team reviews the PR |
| 2026-11-08 | Claude Code | Person A back end (T1–T5): Firestore helpers, auth, LLM wrapper, step machine, Concierge prompt, trips/share endpoints, rules + tests | Nazmul made every design decision in a Q&A session; see docs/decisions.md |
| 2026-11-08 | Claude Code | Measured Gemini models/regions and thinking levels to pick the fastest setup | Results in docs/decisions.md D3, D5 |
| 2026-11-08 | Claude Code (orchestrator + subagents) | Code review of Person A work, review fixes (message counter, normalized answers, prod guards, tzdata, tests), api/AGENTS.md update, Cloud Run/Firestore/Auth setup | Nazmul approved each cloud change and the message-counter design; fixes re-tested by Claude (59 pytest + 10 rules tests) |
| 2026-11-08 | Claude Code | Person B back end T1: Places (search, local names, retry, policy-compliant cache) and Routes services, with tests and a live check against the real APIs | Raghav made each design decision in Q&A |
| 2026-11-08 | Claude Code | Person B T2 plan stub and T3 Planner agent + prompt, tested against real Gemini (Kyushu demo, en + ja) | Raghav made each design decision in Q&A |
| 2026-11-08 | Claude Code | Person B T4 plan pipeline (Places verification, Routes legs, re-timing, warnings, repair round, /plan guards), tested on real Gemini/Places/Routes | Raghav made each design decision in Q&A |
| 2026-11-08 | Claude Code | Person B T5 YouTube Shorts service and demo pre-cache script, tested on the real YouTube API (36 demo places cached) | Raghav made each design decision in Q&A |
| 2026-11-09 | Claude Code | End-to-end test of Person A + Person B back end on emulators with real Google APIs (101 tests, 10 rules tests, en + ja flows); plan-quality fixes from it | Raghav chose each fix |
| 2026-11-09 | Claude Code (orchestrator + 5 subagents) | Live quality evaluation (45 Concierge cases, 3 real plans, pipeline review) and the fixes: Concierge merge and prompt, YouTube relevance and quota, transit fallback, closed-stop repair, hotel and name checks, planner prompt, cost guard, timeouts, key out of logs | Nazmul asked for the evaluation and fixes; Claude re-ran tests (132) and a live eval (49/49); Person B to review the plan-engine changes |
- **web/ rebuilt on Next.js (2026-11-09, Claude Code):** Claude compared Next.js, Vite + React and staying on Angular against the App Hosting deploy path, then wrote the new skeleton: `app/` routes for S1/S3/S6/S7, `lib/` (env, firebase, api client, i18n) and the cookie-based language switch. Why: the front end had to be rebuilt in the framework the team can write quickly, with a day left. A human chose the framework (`docs/decisions.md` D18).
- 2026-11-09 · Claude Code: end-to-end review of the deployed app and the fixes from it (long walks, `leg.line`, bilingual Shorts search, 5-minute times, trimmed browser keys, Places stubbed in API tests, short web.app link). Reviewed and tested by Nazmul.
- 2026-11-09 · Claude Code: Shorts travel ranking (D12): travel word in the YouTube query, rank by travel words/hashtags in title, description and tags, then views; cache version. Raghav proposed the idea (views + travel hashtags) and chose the option.
- 2026-11-09 · Claude Code: walk-only transit routes treated as no route, and the leg label shows the mode first (D9). Raghav found the bug in testing and chose the options.
- 2026-11-09 · Claude Code: faster plan builds (D6): one combined repair round returning only changed days (`PlanFix`), trimmed repair input, honest progress card with ETA. Measured from production logs and real runs; Nazmul chose to optimize without lowering draft quality.

- 2026-11-09 · Codex: improved itinerary readability in the plan panel, header, and day controls; retained existing data and interactions. Nazmul requested the light-surface design after reviewing alternatives, then requested one shared non-white background; Codex applied the original dusk photo with a scoped slate overlay across the header, tabs, chat, and itinerary.

- 2026-11-10 · Codex: diagnosed missing YouTube suggestions from the saved local plan and API logs (32 stops, zero video IDs; upstream HTTP 429). Nazmul chose to keep normal behavior: show videos when returned, otherwise load the plan without them. Removed the proposed search links and added rendering regression tests for both states.
