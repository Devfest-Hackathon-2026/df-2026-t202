# AGENTS.md

Instructions for every coding agent (Claude Code, Codex, Cursor, Gemini CLI) and every human on team Kyu_cat.
Folder rules live in `api/AGENTS.md` and `web/AGENTS.md`. They add to this file; the closer file wins on conflict.

## Source of truth: `PLAN.md`
**Read `PLAN.md` before starting any task.** It defines the scope, data model (section 7), chat flow (8), API (9),
screens (10), security (11), env vars (12) and schedule (13). Follow it exactly.
If the code needs to differ from PLAN.md, **update PLAN.md in the same commit**, so it never goes stale.

| Need | Where |
| --- | --- |
| What to build, data shapes, API, screens | `PLAN.md` |
| Pydantic models (the code version of PLAN.md 7) | `api/app/models.py` |
| Kyushu demo input and a hand-written plan | `api/tests/fixtures/demo_slots.json`, `demo_plan.json` |
| Judging criteria and disqualifiers (kickoff slides) | `docs/SUBMISSION.md` |
| Libraries and licenses | `ATTRIBUTION.md` |
| Where and why we used AI | `docs/ai-usage.md` |

## Product in one line
AI Trip Planner (name TBD; no "Kyushu" in the name). The user answers question cards in a chat. The server builds a
day-by-day plan with real places (Places API), real travel times (Routes API) and a YouTube Short per stop, then the user
shares a view-only link. Worldwide, English or Japanese. Demo: a Kyushu road trip from Fukuoka.

## Deadline
**Submit by Nov 10 (Tue) 18:00 JST** (hard freeze 19:00). Feature freeze Nov 10 at 12:00. The deployed URL must work until Nov 14.
Priority: the MVP (PLAN.md 3.1, F1–F5 + F10) working end to end > polish > stretch. **Don't start stretch features unless asked.**

## Hard rules (PLAN.md 2; breaking one can disqualify us)
1. **Runtime is Google Cloud only:** Cloud Run (`api/`), Firebase App Hosting (`web/`).
2. **Gemini via Vertex AI with the google-genai SDK is the only AI.** No third-party AI services or LLM APIs, no AI Studio key.
3. **No fake demo.** The video shows real app output. Pre-caching real API results is OK; faking results is not.
4. **This repo is public. Never write secrets** (API keys, service-account JSON, `.env`) in code, tests, docs or commit
   messages. Never read or print `.env` files; `.env.example` lists the names. Run `bash scripts/check-secrets.sh` before every commit.
5. **GitHub Actions and Pages are disabled.** Don't add workflow files.
6. **Every library, font, data source or asset → `ATTRIBUTION.md`** with its license.

## Rules for agents (PLAN.md 14)
1. Follow PLAN.md's data model and API exactly. A change to either updates PLAN.md (and `models.py`) in the same commit.
2. Every AI output is validated with a Pydantic model from `api/app/models.py`. On a parse error, retry once with the error, then fail cleanly (`status: "error"`).
3. **The server decides the next chat step** (`flow.py`). The LLM only turns free text into structured updates. It never picks the card.
4. **No hard-coded UI text.** Every string goes in both `web/public/i18n/en.json` and `ja.json` (a test checks the keys match).
5. Keep it simple and readable. This is a 5-day hackathon. No speculative abstractions, no drive-by refactors.
6. For a non-trivial choice (new library, service, data shape), propose 2–3 options with pros and cons and let a human
   choose. Then add an entry to `docs/decisions.md` (chosen, rejected and why, who decided, date) in the same commit.
   This is the hackathon theme ("Own the Why") and feeds the submission doc's Rationale section.
7. When AI generated a large part of a feature, add a line to `docs/ai-usage.md` (what, where, why).

## Repo layout (PLAN.md 6)
```
PLAN.md            Single source of truth
api/               Python 3.12 + FastAPI on Cloud Run                 → api/AGENTS.md
web/               Angular 21 + Material + AngularFire on App Hosting → web/AGENTS.md
firestore.rules    Members-only reads; no client writes to trips (PLAN.md 11.1)
firebase.json      Firestore config + emulators (Auth :9099, Firestore :8081, UI :4000)
scripts/check-secrets.sh   Scan staged changes for keys before committing
docs/              Submission/judging notes, AI usage log, organizer repo rules
```

## Commands
```bash
# Emulators (repo root)
firebase emulators:start --only auth,firestore

# API (api/)
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8080 --env-file .env   # --env-file exports the emulator hosts from .env
.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check .

# Web (web/), Node >= 22.12, npm 11
npm install            # use npm 11 (npx npm@11 install) if npm 10 crashes with "edgesOut"
npm start              # http://localhost:4200 (writes src/environments/env.generated.ts from web/.env first)
npm run build && npm test
```

## Invariants (never break)
- **Only the API writes trips, messages, plans, shares and caches** (Admin SDK). The web app reads Firestore directly and calls the API for actions.
- Keys for Places, Routes and YouTube stay on the server (Secret Manager). Gemini uses Vertex AI with the service account (no key).
  The Maps JavaScript key is the only browser key, restricted by referrer and API.
- `firestore.rules` changes together with any data model change, in the same commit.
- Cache collections are top-level: `cache_places`, `cache_videos` (not `cache/places`).
- Costs are always ranges with an "Estimate" badge. Estimated legs (`leg.estimate: true`) show "Please check".
- All AI text uses the trip's language (`trips.language`). Every system prompt ends with "Write all user-facing text in {English|Japanese}."
- Field names in Firestore and JSON are exactly PLAN.md's camelCase (`placeId`, `nameLocal`, `videoIds`).

## Workflow
- Work on a branch per task (`feat/<area>`, e.g. `feat/chat-cards`). Open a PR to `main`, merge often. **`main` must always build and deploy.**
- Model or data changes (`models.py`, `firestore.rules`, PLAN.md 7) go in their own small PR first, because everyone depends on them.
- Commit subject: `<area>: <imperative summary>` (`api:`, `web:`, `rules:`, `docs:`), ≤ 72 characters.
- Agents commit, push or deploy only when a human asks in that session. Never change IAM, billing or keys.

## Definition of done
- [ ] API: `pytest`, `ruff check` and `ruff format --check` pass. Web: `npm run build` and `npm test` pass.
- [ ] Tried for real against the emulators or the dev project, not just compiled. Web checked at phone width (390 px).
- [ ] Loading, empty and error states exist. Both languages work.
- [ ] PLAN.md, `models.py`, `firestore.rules` and i18n files are in sync. New dependency → `ATTRIBUTION.md`.
- [ ] `bash scripts/check-secrets.sh` passes on the staged diff.

## Budget ($20 Cloud credit, total)
Flash model by default, Pro only if Planner quality is low. Cache Places (`cache_places`) and YouTube (`cache_videos`, 7 days;
YouTube allows about 100 searches a day). Use minimal field masks on Places and Routes. Respect the abuse limits
(20 plans per user per day, 60 messages per trip). No new paid services without a team decision.
