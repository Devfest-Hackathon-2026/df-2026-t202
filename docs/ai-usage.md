# AI usage log

Required in the submission doc: "where and how AI was used, and why there" (PLAN.md 14 rule 10, 18).

## In the product (Gemini on Vertex AI, google-genai SDK)
| Where | Model | What it does | Why AI here |
| --- | --- | --- | --- |
| Concierge (`api/app/agents/concierge.py`) | Flash | Free text → structured slot updates | People answer in free sentences; a fixed form can't read them. Cards cover the structured path |
| Planner (`api/app/agents/planner.py`) | Flash (Pro if quality is low) | Slots + chat → draft day-by-day plan | Creative ordering and themes; verified afterwards with Places and Routes, because LLMs invent places and times |
| Editor (stretch) | Flash | "Make day 2 more relaxed" → revised plan | Natural-language edits |

## In development (coding agents)
One line per meaningful use. Note what the AI proposed and what the team kept or changed.

| Date | Tool | Task | Human decision |
| --- | --- | --- | --- |
| 2026-11-08 | Claude Code | Agent instructions (AGENTS.md / CLAUDE.md) and docs from the kickoff slides and the team spec | Team reviewed |
| 2026-11-08 | Claude Code | Repo base for the revised PLAN.md: FastAPI skeleton, Pydantic models, Kyushu fixtures, Angular skeleton, Firestore rules | Team reviews the PR |
| 2026-11-08 | Claude Code | Person A back end (T1–T5): Firestore helpers, auth, LLM wrapper, step machine, Concierge prompt, trips/share endpoints, rules + tests | Nazmul made every design decision in a Q&A session; see docs/decisions.md |
| 2026-11-08 | Claude Code | Measured Gemini models/regions and thinking levels to pick the fastest setup | Results recorded in docs/decisions.md D18–D19 |
| 2026-11-08 | Claude Code (orchestrator + subagents) | Code review of Person A work, review fixes (message counter, normalized answers, prod guards, tzdata, tests), api/AGENTS.md update, Cloud Run/Firestore/Auth setup | Nazmul approved each cloud change and the message-counter design; fixes re-tested by Claude (59 pytest + 10 rules tests) |
| 2026-11-08 | Claude Code | Person B back end T1: Places (search, local names, retry, policy-compliant cache) and Routes services, with tests and a live check against the real APIs | Raghav made each design decision in Q&A; see docs/decisions.md D35–D40 and person_b_WHY.md |
