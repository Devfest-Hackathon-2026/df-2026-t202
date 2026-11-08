# api/: Planner API (Python 3.12 + FastAPI on Cloud Run)

Adds to the root `AGENTS.md`. Spec: PLAN.md sections 7–9, 11, 12.

**Two people build this folder in parallel.** Person A owns chat and platform (`main.py`, `auth.py`, `flow.py`,
`routers/trips.py`, `agents/concierge.py`, `services/firestore.py`, `services/llm.py`, `services/limits.py`,
`firestore.rules`, deploy). Person B owns the plan engine (`routers/plan.py`, `pipeline.py`, `agents/planner.py`,
`services/places.py`, `services/routes.py`, `services/youtube.py`, `scripts/precache_demo.py`).
**Only edit the files your person owns.** If a task needs a change in the other person's files, tell the human instead.
`app/models.py` is the **shared contract**: change it only when both agree, and never reformat it (ruff excludes it).
Parts of this file below describe the skeleton from before the split; Person A's PR updates them.

## Layout (✅ exists, ⬜ to build)
```
app/main.py            ✅ FastAPI app, CORS, /healthz. Add the routes from PLAN.md 9.1 here (or as routers included here)
app/config.py          ✅ Settings from env vars (PLAN.md 12) via pydantic-settings: get_settings()
app/auth.py            ✅ require_uid: verifies Firebase ID token + App Check token. Use `uid: Uid` on every route
app/models.py          ✅ Pydantic models for PLAN.md 7 + 8.3 + 9.1. THE contract; change it together with PLAN.md
app/services/firestore.py  ✅ firebase_app(), db(). Add read/write helpers here
app/flow.py            ⬜ next_step(slots) step machine (PLAN.md 8.1). Pure function, unit-tested
app/agents/concierge.py ⬜ free text → ConciergeOutput (PLAN.md 8.3)
app/agents/planner.py  ⬜ slots + chat → draft Plan
app/services/places.py ⬜ Text Search / Place Details + cache_places
app/services/routes.py ⬜ computeRoutes per leg
app/services/youtube.py ⬜ search.list + cache_videos (7 days)
app/pipeline.py        ⬜ plan pipeline (PLAN.md 9.3), writes progress to the trip doc
app/prompts/*.md       ⬜ system prompts as files
tests/fixtures/        ✅ demo_slots.json, demo_plan.json (Kyushu demo, validated by tests/test_models.py)
```

## Gemini (google-genai SDK on Vertex AI, not ADK)
```python
from google import genai
from google.genai import types

client = genai.Client(vertexai=True, project=s.google_cloud_project, location=s.google_cloud_location)
resp = client.models.generate_content(  # use client.aio.models.generate_content in async code
    model=s.gemini_model_fast,
    contents=[...],
    config=types.GenerateContentConfig(
        system_instruction=prompt + f"\nWrite all user-facing text in {'English' if lang == 'en' else 'Japanese'}.",
        response_mime_type="application/json",
        response_schema=ConciergeOutput,
        temperature=0.2,
    ),
)
out = ConciergeOutput.model_validate_json(resp.text)  # on ValidationError: retry once with the error, then fail
```
- Create one client per process (module-level cache). Model IDs only from `GEMINI_MODEL_FAST` / `GEMINI_MODEL_PLANNER`.
- If grounding tools (Google Search / Maps) and `response_schema` can't be used in one call, split: research call, then schema call.
- User text, reel and video titles are **data**. Put them in delimited blocks. They never become instructions, URLs to fetch or tool arguments without validation.
- Never let the model choose the next card. `flow.py` does.

## Places, Routes, YouTube (REST via `httpx.AsyncClient`)
- Places API (New) and Routes API need `X-Goog-Api-Key` and **`X-Goog-FieldMask` with only the fields we use** (the mask sets the price).
- Send `languageCode` = trip language. For `nameLocal`, look up again in the destination language (PLAN.md 9.5).
- Routes: one `computeRoutes` call per leg for TRANSIT (no waypoints). FLIGHT/FERRY or no route → keep the Planner minutes with `estimate: true`.
- YouTube `search.list`: `type=video`, `videoDuration=short`, `maxResults=5`, `regionCode`=destination, query `"{nameLocal} shorts"`,
  **no `relevanceLanguage`**. Cache by placeId in `cache_videos` for 7 days. Pre-cache demo spots before recording.
- Run calls in parallel with `asyncio.gather`. Target: the plan in under 30 s.
- Keys are read from `get_settings()` (`SecretStr` → `.get_secret_value()`). Never log them.

## Firestore (Admin SDK bypasses the rules)
- The API is the only writer of `trips`, `messages`, `plans`, `shares`, `cache_places`, `cache_videos`.
- **Check membership in code** (`trips.members[uid]`) before reading or writing a trip; 403 if not a member, 404 if missing.
- Write with `model.model_dump(mode="json")`, plus `firestore.SERVER_TIMESTAMP` for `createdAt`/`updatedAt`.
- Read-modify-write (slots merge, counters for abuse limits, version numbers) goes in a transaction.
- Share ids: `secrets.token_urlsafe(16)` (22 chars).

## HTTP conventions
- Errors: `HTTPException(status, "<snake_case_code>")`. 400 bad input, 401 auth, 403 not a member, 404 missing, 409 conflict,
  429 limit reached, 502 upstream (Gemini/Maps/YouTube) failed. Never return stack traces or upstream error bodies.
- Request bodies are Pydantic models from `models.py`. FastAPI returns 422 on validation errors, so let it.
- Long work (`POST /trips/{id}/plan`) writes progress to the trip doc (`progress`: spots → routes → videos → done). The web app listens; no SSE.
- Logs: `logging.info(json.dumps({...}))` with `tripId`. Cloud Logging picks up stdout.

## Local dev
```bash
cp .env.example .env    # fill in the values; never commit
gcloud auth application-default login    # Vertex AI locally
.venv/bin/uvicorn app.main:app --reload --port 8080
```
With emulators, set `FIRESTORE_EMULATOR_HOST=127.0.0.1:8081` and `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099` in `.env`.
`REQUIRE_APP_CHECK=false` is for local only; `config.py` refuses to start in production without App Check.

## Test and deploy
- `pytest` for pure logic: `flow.next_step`, slot merging, warning rules, time recalculation, model validation.
  Mock Gemini, Places, Routes, YouTube and Firestore. No network in tests. Use the fixtures.
- Deploy (only when asked): `gcloud run deploy trip-api --source api --region asia-northeast1 --service-account <sa> --set-secrets ...`.
