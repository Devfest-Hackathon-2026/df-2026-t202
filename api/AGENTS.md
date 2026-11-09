# api/: Planner API (Python 3.12 + FastAPI on Cloud Run)

Adds to the root `AGENTS.md`. Spec: PLAN.md sections 7–9, 11, 12.

**Two people build this folder in parallel.** Person A owns chat and platform (`main.py`, `auth.py`, `flow.py`,
`routers/trips.py`, `agents/concierge.py`, `services/firestore.py`, `services/llm.py`, `services/limits.py`,
`firestore.rules`, deploy). Person B owns the plan engine (`routers/plan.py`, `pipeline.py`, `agents/planner.py`,
`services/places.py`, `services/routes.py`, `services/youtube.py`, `scripts/precache_demo.py`).
**Only edit the files your person owns.** If a task needs a change in the other person's files, tell the human instead.
`app/models.py` is the **shared contract**: change it only when both agree, and never reformat it (ruff excludes it).

## Layout (✅ exists, ⬜ to build; (A) Person A, (B) Person B)
```
app/main.py            ✅ (A) FastAPI app, CORS, /health (+ /healthz locally; Cloud Run reserves it); includes routers trips (A) and plan (B)
app/config.py          ✅ (A) Settings from env (PLAN.md 12): get_settings(). Refuses to start in production with SKIP_APPCHECK
app/auth.py            ✅ (A) require_user (ID token + App Check), `User` dependency, require_member, require_owner
app/models.py          ✅ (both) Pydantic models for PLAN.md 7 + 8.3 + 9.1. THE contract; change it together with PLAN.md
app/flow.py            ✅ (A) next_step, question_for, card_for, apply_answer, currency_for, merge_updates, answer_text, search_place, search_start
app/routers/trips.py   ✅ (A) create trip, post message, share, join share
app/routers/plan.py    ✅ (B) POST /trips/{id}/plan and the edit routes
app/agents/concierge.py ✅ (A) run(): free text → ConciergeOutput via llm.generate_json
app/agents/planner.py  ✅ (B) slots + chat → draft Plan; fix() → PlanFix (changed days only, D6)
app/services/firestore.py ✅ (A) async helpers: db, now, get_trip, update_trip, list_messages, add_message, save_plan, cache_get, cache_set
app/services/llm.py    ✅ (A) generate_json, MODEL_FAST, MODEL_PLANNER, LLMError
app/services/limits.py ✅ (A) check_plan_limit (per user per day), check_message_limit (per trip)
app/services/places.py ✅ (B) Text Search / Place Details + cache_places
app/services/routes.py ✅ (B) computeRoutes per leg
app/services/youtube.py ✅ (B) search.list + cache_videos (7 days)
app/pipeline.py        ✅ (B) plan pipeline (PLAN.md 9.3), writes progress to the trip doc
app/prompts/*.md       concierge.md ✅ (A); planner.md ✅ (B)
tests/                 ✅ (both) conftest.py, test_flow.py, test_api.py, test_models.py; fixtures/demo_slots.json (demo_plan.json is in app/fixtures/, used by the plan stub)
```

## Helpers Person B imports (signatures from the code)
```python
from app.auth import User, require_member, require_owner   # User = Annotated[str, Depends(require_user)] -> uid
async def require_member(trip_id: str, uid: str) -> dict   # the trip doc; 404 trip_not_found, 403 not_a_member
async def require_owner(trip_id: str, uid: str) -> dict    # 403 owner_only
from app.services.firestore import get_trip, update_trip, save_plan, cache_get, cache_set
async def get_trip(trip_id: str) -> dict | None
async def update_trip(trip_id: str, data: dict) -> None
async def save_plan(trip_id: str, plan: Plan, reason: str = "initial") -> str   # returns planId
async def cache_get(name: str, key: str) -> dict | None    # name: "places" | "videos"
async def cache_set(name: str, key: str, data: dict[str, Any]) -> None
from app.services import llm
async def generate_json[T: BaseModel](model: str, system: str, user: str, schema: type[T],
                                      tools: list | None = None, thinking: str | None = None) -> T  # raises llm.LLMError
from app.services.limits import check_plan_limit
async def check_plan_limit(uid: str) -> None               # 429 plan_limit_reached
```
Use `llm.MODEL_PLANNER` for the Planner and `llm.MODEL_FAST` for small calls.

## Gemini (google-genai SDK on Vertex AI, not ADK)
```python
from app.services import llm

out = await llm.generate_json(  # cached Vertex AI client, JSON mode, validates, retries once, else raises LLMError
    model=llm.MODEL_FAST,
    system=prompt + f"\nWrite all user-facing text in {'English' if lang == 'en' else 'Japanese'}.",
    user=json.dumps({...}),  # user text goes in as data
    schema=ConciergeOutput,
    thinking="MINIMAL",  # optional
)
```
- Agents call `llm.generate_json`, never the SDK directly. It owns the one client. Model IDs only via `llm.MODEL_FAST` / `llm.MODEL_PLANNER`.
- If grounding tools (Google Search / Maps) and `response_schema` can't be used in one call, split: research call, then schema call.
- User text, reel and video titles are **data**. Put them in delimited blocks. They never become instructions, URLs to fetch or tool arguments without validation.
- Never let the model choose the next card. `flow.py` does.

## Places, Routes, YouTube (REST via `httpx.AsyncClient`)
- Places API (New) and Routes API need `X-Goog-Api-Key` and **`X-Goog-FieldMask` with only the fields we use** (the mask sets the price).
- Send `languageCode` = trip language. For `nameLocal`, look up again in the destination language (PLAN.md 9.5).
- Routes: one `computeRoutes` call per leg for TRANSIT (no waypoints). FLIGHT/FERRY or no route → keep the Planner minutes with `estimate: true`.
- YouTube `search.list`: `type=video`, `videoDuration=short`, `maxResults=10`, `regionCode`=destination, query
  `"{name} 観光 shorts"` / `"{name} travel shorts"`, **no `relevanceLanguage`**. Rank travel videos first (PLAN.md 9.4, D12).
  Cache by placeId in `cache_videos` for 7 days. Pre-cache demo spots before recording.
- Run calls in parallel with `asyncio.gather`. Plan quality comes before speed (D4); the Planner draft takes about 30 s, a whole plan 30–45 s (D6).
- Keys are read from `get_settings()` (`SecretStr` → `.get_secret_value()`). Never log them.

## Firestore (Admin SDK bypasses the rules)
- The API is the only writer of `trips`, `messages`, `plans`, `shares`, `cache_places`, `cache_videos`.
- **Check membership in code** (`require_member`) before reading or writing a trip; 403 if not a member, 404 if missing.
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
.venv/bin/uvicorn app.main:app --reload --port 8080 --env-file .env   # --env-file exports the emulator hosts from .env
```
With emulators, set `FIRESTORE_EMULATOR_HOST=127.0.0.1:8081` and `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099` in `.env`.
`SKIP_APPCHECK=1` skips App Check for local use only; `config.py` refuses to start in production with it set.

## Test and deploy
- Tests mock Gemini, Places, Routes and YouTube (no network). From `api/`, with the Firestore emulator on :8081:
  `firebase emulators:exec --only firestore --project demo-trip-planner ".venv/bin/pytest -q"`
- Rules tests (Node 22): `cd rules-tests && npm test`.
- Deploy (only when asked): `gcloud run deploy trip-api --source api --region asia-northeast1 --service-account trip-api@<project>.iam.gserviceaccount.com --set-secrets PLACES_API_KEY=places-api-key:latest ...`
