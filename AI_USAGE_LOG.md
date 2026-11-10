# Tripi — AI usage log

Where we used AI, how, and why there: **inside the product** (Gemini on Vertex AI) and **while building it**
(AI coding assistants). The team made every design decision; they are recorded in [`docs/decisions.md`](docs/decisions.md).

## In the product: Gemini on Vertex AI

| Where | Model | What it does | Why AI here |
| --- | --- | --- | --- |
| Concierge (`api/app/agents/concierge.py`) | Gemini Flash, minimal thinking | Turns free text ("4 people, Kyushu, 3 nights, onsen and night views") into structured trip conditions | People answer in their own words; a fixed form can't read them. Answers come back fast (1.1–1.8 s, D5) |
| Planner (`api/app/agents/planner.py`) | Gemini Flash, default thinking | Drafts the day-by-day plan: places, order, times, themes, cost ranges | Choosing and ordering places for a trip needs judgment. We keep full thinking for quality (D4) |
| Planner repair (`planner.fix`) | Gemini Flash, low thinking | Fixes only the days with problems: a place that doesn't exist, a stop closed on arrival, too much driving | Swapping a closed stop for a nearby open one needs judgment; the result is checked again (D6) |

**Where we chose not to use AI:** which question to ask next (server code, D7), whether a place exists and where it is
(Places API), travel times (Routes API), and which video to show (plain ranking rules, D12). These must be correct and
repeatable, so real data and code decide them. Every AI output is validated against a fixed schema, and user text is
passed to the model as data, never as instructions (D13).

## While building: AI coding assistants

We used Claude Code and Codex as pair programmers. The team set the direction, compared the options and made every
decision; the assistants wrote and tested code to that design. Every change was reviewed and run by a team member
before it was merged.

| Area | How AI helped | What the team decided |
| --- | --- | --- |
| Back end: chat and platform | Implementing the API, auth, Firestore helpers and security rules, with tests | Nazmul: the chat flow, data model, security rules and limits |
| Back end: plan engine | Implementing the Places, Routes and YouTube services and the plan pipeline, tested against the real APIs | Raghav: how places are verified, how routes and videos are chosen, quality over speed |
| Front end | Building the Next.js screens from the team's design | Soma: the framework, the one-screen map design and the UI |
| Quality and speed | Running end-to-end checks against real Google APIs and measuring timings | The team chose each fix from the measurements, e.g. faster plans without lowering quality (D6) |
| Security review and hardening | Reviewing the API, prompts and rules for abuse, cost and impossible input, then writing the limits, validation and tests | Nazmul chose the limits, the 14-day cap and the destination cards from the options (D21–D24) |
| Edit by chat and plan updates | Implementing card re-opening, plan requests, the incremental plan update (`pipeline.update`, `planner.revise`) with tests, and the itinerary jump bar | Nazmul chose to revise only changed days and reuse earlier lookups over a full rebuild or code-only patching (D27) |

**Guardrails:** the assistants cannot read secrets (`.env` files are blocked), all keys stay in Secret Manager, and every
commit is scanned for secrets before it is pushed.
