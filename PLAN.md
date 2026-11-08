# AI Trip Planner — Revised Build Plan (Team Kyu_cat)

GDGoC Japan DevFest Hackathon 2026 · Theme: "Own the Why, Build with Intent" · Category: **Tourism**

This file is the single source of truth for the build. It is written for the team and for Claude Code.
Read the whole file before you write code. Follow the rules in section 2. They can disqualify the team.

- Based on: the teammate's spec "九州旅行AIプランナー 仕様書（Googleハッカソン版）"
- Revised: 2026-11-08 (Sun), 11:15 JST. Later on Nov 8: cache collections renamed, google-genai instead of ADK, back-end split into Person A / Person B with a shared `models.py` contract (7.4), repo layout synced with the code.
- Changes from the original spec: worldwide destinations, English/Japanese language setting, Shorts in any language, smaller scope for the deadline, simpler progress updates (Firestore instead of SSE).

---

## 0. Status and deadline

- Development started: Nov 5 (Thu) 10:00 JST
- **Code freeze and submission: Nov 10 (Tue) 19:00 JST.** After this time the GitHub repo becomes read-only.
- **Internal target: submit by Nov 10 (Tue) 18:00 JST.** Keep one hour as a buffer.
- The deployed URL must keep working until **Nov 14 (Sat)** (Regional Day).
- If the team reaches the finals, development can continue until Demo Day (Nov 27).

---

## 1. Product summary

**Working name:** "AI Trip Planner" (final name: TBD — do not use "Kyushu" in the name, because the app works worldwide).

**One line:** The user answers a few questions from an AI in a chat. The app builds a day-by-day trip plan with a map route and YouTube Shorts for each spot. The user shares the plan with friends by link.

**Problem:** When students plan a trip with friends, LINE messages, Google Maps links and YouTube links get mixed up. Nobody knows who decided what. Nobody checks if travel times are realistic.

**Target users:** University students and people in their 20s who plan trips with friends.

**Scope of destinations:** Anywhere in the world.

**Demo:** A Kyushu trip that starts from Fukuoka (the team lives there and can check plan quality).

**Language:** The user chooses English or Japanese. The UI, chat, plan text, place names and route text follow this setting. YouTube Shorts can be in any language.

---

## 2. Hackathon rules that affect the code (MUST follow)

1. **Runtime:** The app must run on a Google Cloud runtime. We use **Firebase App Hosting** (front end) and **Cloud Run** (back end).
2. **Google tech is the main stack.** Do not build the product around third-party AI tools. Do not show third-party products in the demo or pitch.
3. **No secrets in the repo.** Never commit API keys, service-account JSON or `.env` files. Use Secret Manager and `.gitignore`. This also affects the security score.
4. **Attribution sheet:** Record every library, font, data source and asset with its license (see `ATTRIBUTION.md`, section 15).
5. **No fake demo.** The demo video must show real output from the app. Pre-caching real API results is OK. Faking results is not.
6. **AI coding assistants are allowed.** Record where and why we used AI (see section 16). The submission needs it.
7. **Cloud credits ($20/team) do not cover Google AI Studio.** Call Gemini through **Vertex AI** so credits apply.
8. Set a **budget alert** in Google Cloud Billing. Alerts do not stop spending, so also restrict API keys and add per-user limits.

---

## 3. Scope

### 3.1 MVP — must work end to end by Nov 10, 18:00

| ID | Feature | Done when |
|---|---|---|
| F1 | AI chat with question cards | User completes all steps by tapping cards or typing free text. Answers are saved in Firestore. |
| F2 | Plan generation | Backend returns a day-by-day plan with real places (Places API) and real travel times (Routes API). |
| F3 | Trip page with map | Map shows each day's route in its own color, with numbered pins. Timeline lists the stops. |
| F4 | YouTube Shorts per spot | Each stop shows a Short (or a fallback). A viewer lets the user swipe through them in trip order. |
| F5 | Share link (view only) | Owner creates a link. A friend opens it on a phone without login and sees the plan. |
| F10 | Language setting | User switches English/Japanese. UI and all new AI output follow it. |

### 3.2 Stretch — only after the MVP works (in this order)

1. F6 — Edit by chat ("make day 2 more relaxed"). Strong demo moment. Add first.
2. Editor share links and simple voting (F7).
3. Plan versions and "revert".
4. LINE preview cards (OGP) with SSR.
5. Plan comparison (F8), Google Calendar export (F9).
6. Streaming chat replies (SSE).

### 3.3 Out of scope

- Real prices, live availability, live timetables, booking.
- Native mobile apps.

---

## 4. Tech stack

| Layer | Choice |
|---|---|
| Front-end framework | **Angular** (standalone components, Signals). Fallback: Next.js only if no team member knows Angular. Decide on Nov 8. |
| UI components | Angular Material |
| Map | `@angular/google-maps` + Maps JavaScript API |
| Destination search | Places Autocomplete (Maps JavaScript API, Places library) |
| Video player | YouTube IFrame Player API |
| UI translations | Transloco (runtime switch, JSON files) |
| Firebase SDK | AngularFire (Firestore, Auth, App Check) |
| Front-end hosting | Firebase App Hosting (auto-deploy from GitHub `main`) |
| Back end | Python 3.12 + FastAPI on Cloud Run |
| AI agents | **google-genai SDK** (direct calls with a JSON response schema), Gemini via Vertex AI. Not ADK: less setup for a one-day build (see section 16) |
| Models | A fast "Flash" model for all agents first. Use a "Pro" model for the Planner only if plan quality is low. Read model names from env vars. Check current model names in Vertex AI before setting them. |
| Validation | Pydantic v2 |
| Places | Places API (New) — Text Search, Place Details |
| Routes | Routes API — `computeRoutes` |
| Videos | YouTube Data API v3 — `search.list` |
| Database | Cloud Firestore |
| Auth | Firebase Authentication — Google sign-in + anonymous |
| Abuse protection | Firebase App Check (reCAPTCHA Enterprise) |
| Secrets | Secret Manager |
| Logs | Cloud Logging (automatic on Cloud Run) |
| Local dev | Firebase Emulator Suite (Firestore, Auth) |

---

## 5. Architecture

```
Browser / phone (Angular on Firebase App Hosting)
  ├─ Maps JavaScript API, YouTube IFrame Player   (display only, browser key restricted to our domain)
  ├─ Firebase Auth, App Check
  ├─ Firestore listener  ◄──────────────── real-time trip, messages, plan, progress
  └─ HTTPS (ID token + App Check token)
        │
        ▼
Cloud Run: Planner API (FastAPI + google-genai, Python)
  ├─ Secret Manager (API keys)
  ├─ Cloud Logging
  ├─ Vertex AI Gemini   (Concierge, Planner, Editor agents)
  ├─ Places API (New)   (verify spots, local names, coordinates, hours, photos)
  ├─ Routes API         (travel time and route lines)
  ├─ YouTube Data API   (Shorts search)
  └─ Firestore (Admin SDK) — the ONLY writer of AI fields
```

**Key design rules**
1. All API keys except the Maps browser key stay on the server.
2. The front end **reads** from Firestore directly. The API only **writes** and runs AI work.
3. **Server code decides the next question card.** The AI never decides the flow. The AI only reads free text into structured data.
4. Card answers are sent as structured data, so the AI cannot misread them.
5. Long work (plan generation) writes **progress stages** to Firestore. The front end shows them from its Firestore listener. (No SSE in the MVP.)

---

## 6. Repository structure

```
/
├─ PLAN.md                  ← this file
├─ CLAUDE.md                ← short rules for Claude Code (copy section 2 + section 14)
├─ ATTRIBUTION.md           ← libraries, fonts, data, licenses
├─ README.md                ← setup, run, deploy
├─ firebase.json
├─ firestore.rules
├─ firestore.indexes.json
├─ .gitignore               ← must include .env*, *serviceAccount*.json, node_modules, __pycache__
├─ web/                     ← Angular app (App Hosting root)
│  ├─ apphosting.yaml
│  ├─ src/app/
│  │  ├─ core/              ← auth, api client, firestore services, language service
│  │  ├─ chat/              ← S1 chat page + cards/
│  │  ├─ plan/              ← S3 trip page, map, timeline, shorts viewer
│  │  ├─ share/             ← S6 shared page
│  │  └─ home/              ← S7 my trips
│  └─ public/i18n/          ← en.json, ja.json (Angular CLI serves public/ at the site root)
└─ api/                     ← Cloud Run service
   ├─ Dockerfile
   ├─ requirements.txt
   ├─ app/
   │  ├─ main.py            ← FastAPI app, includes the routers
   │  ├─ config.py          ← env vars (section 12) via pydantic-settings
   │  ├─ routers/
   │  │  ├─ trips.py        ← /trips, /messages, /share, /shares/{id}/join (Person A)
   │  │  └─ plan.py         ← /trips/{id}/plan (Person B)
   │  ├─ auth.py            ← verify Firebase ID token + App Check token
   │  ├─ models.py          ← Pydantic: Slots, Plan, Day, Stop, Leg, Cost, UiCard
   │  ├─ flow.py            ← step machine: which card comes next
   │  ├─ agents/
   │  │  ├─ concierge.py    ← free text → slot updates
   │  │  ├─ planner.py      ← slots + chat → draft plan JSON
   │  │  └─ editor.py       ← (stretch) edit request → revised plan
   │  ├─ services/
   │  │  ├─ places.py       ← resolve spot → placeId, names, lat/lng, hours
   │  │  ├─ routes.py       ← legs: minutes, polyline
   │  │  ├─ youtube.py      ← Shorts search + cache
   │  │  ├─ firestore.py    ← read/write helpers (async client)
   │  │  ├─ llm.py          ← Gemini via Vertex AI: generate_json(model, system, user, schema)
   │  │  └─ limits.py       ← per-user daily plan limit
   │  ├─ pipeline.py        ← plan pipeline (section 9.3)
   │  ├─ prompts/           ← system prompts as .md files
   │  └─ fixtures/          ← demo_plan.json (Kyushu demo plan; ships with the app for the /plan stub)
   └─ tests/
      └─ fixtures/          ← demo_slots.json (Kyushu demo input)
```

---

## 7. Data model (Firestore)

### 7.1 Collections

| Path | Fields |
|---|---|
| `users/{uid}` | `displayName`, `photoURL`, `language` (`"en"`/`"ja"`), `createdAt` |
| `trips/{tripId}` | `ownerUid`, `members` (map uid → `"owner"`/`"viewer"`), `language`, `slots` (7.2), `asking` (current step key), `status` (`"chatting"`/`"planning"`/`"ready"`/`"error"`), `progress` (`"spots"`/`"routes"`/`"videos"`/`"done"`), `currentPlanId`, `shareId`, `messageCount` (messages written so far, for the per-trip limit), `createdAt`, `updatedAt` |
| `trips/{tripId}/messages/{msgId}` | `role` (`"user"`/`"ai"`), `text`, `answer` (card answer object or null), `ui` (card to show, AI messages only), `createdAt` |
| `trips/{tripId}/plans/{planId}` | `version`, `plan` (7.3), `reason`, `createdAt` |
| `shares/{shareId}` | `tripId`, `mode` (`"view"`), `active` (bool), `createdAt` |
| `cache_places/{hash}` | `query`, `placeId`, `nameLocal`, `nameEn`, `nameJa`, `lat`, `lng`, `fetchedAt` |
| `cache_videos/{placeId}` | `videoIds[]`, `fetchedAt` (reuse for 7 days) |

`trips.language` is fixed when the trip is created (copied from `users.language`). All AI text in the trip uses it.

### 7.2 `slots` (conditions collected in chat)

```json
{
  "dest": {"label": "Kyushu, Japan", "placeId": "ChIJ...", "countryCode": "JP"},
  "origin": {"label": "Fukuoka", "placeId": "ChIJ..."},
  "dates": {"start": "2027-03-10", "end": "2027-03-13"},
  "nights": null,
  "people": {"adult": 4, "child": 0, "infant": 0},
  "budget": {"basis": "person", "amount": 50000, "currency": "JPY"},
  "transport": ["car"],
  "prefs": ["onsen", "views", "night_view"],
  "musts": ["Takachiho Gorge", "Mt. Inasa night view"],
  "status": {"dest": "done", "dates": "done", "people": "done", "budget": "skip",
             "transport": "done", "prefs": "done", "musts": "done"}
}
```

- `status` values: `"empty"`, `"done"`, `"skip"` (user said "not decided" → AI decides).
- `transport` values: `"shinkansen"`, `"train"`, `"plane"`, `"car"`, `"bus"`, `"ferry"`, `"any"`.
- Use `dates` or `nights` (one of them).

### 7.3 `plan` (the trip)

```json
{
  "title": "Kyushu 3 nights 4 days road trip",
  "subtitle": "Onsen, views and night views",
  "language": "en",
  "currency": "JPY",
  "days": [{
    "day": 2,
    "date": "2027-03-11",
    "theme": "Kurokawa Onsen → Takachiho Gorge → Nagasaki",
    "stay": "Nagasaki city",
    "stops": [{
      "id": "s-201",
      "time": "09:30",
      "name": "Takachiho Gorge",
      "nameLocal": "高千穂峡",
      "kind": "view",
      "placeId": "ChIJ...",
      "lat": 32.702, "lng": 131.301,
      "note": "Boat ride and Manai Falls",
      "videoIds": ["..."],
      "warn": null,
      "leg": {"mode": "DRIVE", "minutes": 120, "polyline": "...", "estimate": false}
    }]
  }],
  "cost": {"basis": "person", "min": 42000, "max": 55000,
           "items": [{"label": "Hotels, 3 nights", "min": 24000, "max": 33000}]},
  "checks": ["Check the 16:40 ferry from Kuchinotsu and book car space"]
}
```

Rules:
- `leg` is the move from this stop to the next. The last stop of a day has `leg: null`.
- `leg.mode`: `"DRIVE"`, `"TRANSIT"`, `"WALK"`, `"FLIGHT"`, `"FERRY"`.
- `leg.estimate: true` when the Routes API cannot compute it (flights, ferries, countries with no transit data). Gemini fills `minutes`. The UI shows a "please check" badge.
- `time` is local time at the destination (`"HH:MM"`). No time-zone conversion in the MVP.
- Costs are always ranges (`min`/`max`), never one exact number. UI shows an "estimate" badge.
- `nameLocal` is the name in the destination's language. It is used for YouTube search.

### 7.4 `ui` card (on AI messages)

```json
{"type": "transport", "options": ["shinkansen", "train", "plane", "car", "bus", "ferry", "any"]}
```

- `type`: a step key (8.1) or `"ready"`. The server sets it from `next_step()`. The LLM never chooses it.
- `options`: chip values, if any (transport modes, prefs). The front end shows labels from the i18n files.
- **The code version of every shape in section 7 is `api/app/models.py`, the shared contract between the two back-end
  people.** It differs from the JSON above in small ways (dates are `"YYYY-MM-DD"` strings, `PlaceRef` has `lat`/`lng`,
  stops have `stayMinutes`). Change it only when both back-end people agree. Fixtures: `api/tests/fixtures/`.

---

## 8. Chat flow

### 8.1 Steps (server-side step machine in `api/app/flow.py`)

| Order | Step key | AI asks (example) | Card (`ui.type`) | After the answer |
|---|---|---|---|---|
| 1 | `dest` | Where do you want to go? | `dest`: place search box + popular chips | Save `slots.dest` |
| 2 | `dates` | When do you want to go? | `dates`: date range picker + "not decided" → nights chips | Save `dates` or `nights` |
| 3 | `people` | How many people? | `people`: adult/child/infant +/– | Save `people` |
| 4 | `budget` | What is your budget? | `budget`: per person/total switch + amount chips + slider. Currency from destination country. | Save `budget` |
| 5 | `transport` | How do you want to travel? | `transport`: multi-select chips + origin search box | Save `transport`, `origin` |
| 6 | `prefs` | What kind of trip do you want? | `prefs`: multi-select chips + free text | Save `prefs` |
| 7 | `musts` | Any places you must visit? | `musts`: free text + "none" | Save `musts` |
| — | `ready` | Here is your plan! | `ready`: trip card + "See plan" button | Start plan pipeline |

**Flow logic (`next_step(slots)`):** return the first step whose status is `"empty"`. If none, return `"ready"`.

### 8.2 UX rules

1. Ask only one question at a time.
2. After an answer, close the card and keep the answer as a user chat bubble.
3. Every card has "Not decided yet". This sets status `"skip"`. The AI fills it later.
4. Free text can answer several steps at once. The Concierge extracts all of them. The step machine skips finished steps.
5. If the answer is unclear, the AI asks back in one sentence (`clarify`).
6. Each AI reply may add one short useful tip about the destination.
7. The right panel (S2) shows all slots. Tapping one asks that question again.

### 8.3 Concierge agent (free text → structured updates)

Input: current `slots`, current step, user text, trip language.
Output (Pydantic-validated JSON):

```json
{
  "updates": {"people": {"adult": 4}, "budget": {"basis": "person", "amount": 50000}},
  "comment": "Great! March is a good season for onsen.",
  "clarify": "Which days in March?"
}
```

- `comment` and `clarify` are written in the trip language.
- The server merges `updates` into `slots`, then calls `next_step()`.
- Destination text from the Concierge must be resolved with the Places API before it is saved.

---

## 9. Back end (Cloud Run)

### 9.1 API

Every request needs `Authorization: Bearer <Firebase ID token>` and `X-Firebase-AppCheck: <token>`. Verify both in `auth.py` with the Firebase Admin SDK. The shared-page read path uses Firestore directly, not the API.

| Method | Path | Body | What it does |
|---|---|---|---|
| POST | `/trips` | `{language}` | Create a trip. Write the first AI message with the `dest` card. Return `{tripId}`. |
| POST | `/trips/{id}/messages` | `{type:"answer", step, value}` or `{type:"text", text}` | Save the user message. Update slots (directly for answers, via Concierge for text). Write the AI reply with the next card. |
| POST | `/trips/{id}/plan` | `{}` | Run the plan pipeline (9.3). Write progress to the trip doc. Save the plan. Return `{planId}`. |
| POST | `/trips/{id}/share` | `{}` | Create `shares/{shareId}` with a random 22+ character id. Return `{shareId}`. |
| POST | `/trips/{id}/plan/edit` | `{text}` | **Stretch.** Editor agent revises the plan. |
| GET | `/health` | — | Health check. `/healthz` also works locally, but Cloud Run reserves paths ending in `z`. |

Answer examples:

```json
{"type": "answer", "step": "dates", "value": {"start": "2027-03-10", "end": "2027-03-13"}}
{"type": "text", "text": "4 people in March, about 50,000 yen each"}
```

### 9.2 Agents

| Agent | Model | Job |
|---|---|---|
| Concierge | Flash | Free text → slot updates (8.3) |
| Planner | Flash (Pro if needed) | Slots + chat → draft plan JSON. May use Google Search / Google Maps grounding tools. |
| Router | Code (no LLM) | Routes API for each leg. Adds warnings. |
| Media | Code (no LLM) | YouTube Shorts per stop. |
| Editor (stretch) | Flash | Edit request → revised plan, then Router + Media again. |

Implementation notes:
- Every system prompt ends with: "Write all user-facing text in {English|Japanese}."
- Use Pydantic models for every AI output. On a parse error, retry once with the error message. Then fail cleanly (`status: "error"`).
- Call Gemini with the google-genai SDK (`genai.Client(vertexai=True, project=..., location=...)`), passing the Pydantic model as `response_schema` with `response_mime_type="application/json"`, then validate with `Model.model_validate_json`.
- If a model doesn't allow tools (Google Search / Maps grounding) and a strict response schema in the same call, split it: call 1 with tools (research), call 2 with the response schema (JSON).
- Model names come from env vars `GEMINI_MODEL_FAST` and `GEMINI_MODEL_PLANNER`.

### 9.3 Plan pipeline (`pipeline.py`)

1. Set `trips.status = "planning"`, `progress = "spots"`.
2. **Planner** reads slots and the full chat. It returns a draft plan: days, stops (name + time), leg modes, cost ranges, checks.
3. For each stop, call **Places API Text Search** (biased to the destination). Save `placeId`, `lat`, `lng`, official name in the trip language, `nameLocal`, opening hours. Use `cache_places`.
   - If a spot is not found, ask the Planner once for a replacement. If it still fails, remove the stop and add a note to `checks`.
4. Set `progress = "routes"`. For each leg, call **Routes API `computeRoutes`**. Save `minutes` and `polyline`.
   - Transit cannot use waypoints, so compute transit one leg at a time.
   - `FLIGHT` and `FERRY` legs, and legs with no route, keep the Planner estimate with `estimate: true`.
5. Recalculate stop times from the real leg times. Add warnings:
   - Driving more than 5 hours in one day.
   - Arrival outside opening hours.
6. If there are 3 or more warnings, ask the Planner to fix the plan **once**. Repeat steps 3–5 for changed stops only.
7. Set `progress = "videos"`. **Media** gets Shorts for each stop (9.4).
8. Save `trips/{id}/plans/{planId}` (version 1). Set `currentPlanId`, `status = "ready"`, `progress = "done"`.

Target: under 30 seconds. Run Places, Routes and YouTube calls in parallel (`asyncio.gather`).

### 9.4 YouTube Shorts

- `search.list` with `part=snippet`, `type=video`, `videoDuration=short`, `maxResults=5`, `regionCode={destination country}`.
- Query: `"{nameLocal} shorts"`. **Do not set `relevanceLanguage`.** Videos in any language are OK.
- Prefer results whose title contains the spot name.
- Cache by `placeId` for 7 days in `cache_videos/{placeId}`.
- The default quota allows about 100 searches per day. Pre-cache all demo spots before recording.
- Fallback when nothing is found: a "Search on YouTube" link + a Places photo.

### 9.5 Places, Routes, Maps links

- Places API (New) and Routes API need a **field mask** header. Request only the fields we use (lower cost).
- Send `languageCode` = trip language for display names and route text.
- To get `nameLocal`, request the place again with the destination's language (or use the name returned without a language code).
- "Open in Google Maps" uses Maps URLs: `https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=...&travelmode=...`. Max 9 waypoints. Split long days.

### 9.6 Abuse limits

- Max 20 plan generations per user per day (counter in Firestore).
- Max 60 chat messages per trip (`trips.messageCount`, reserved in a transaction before the Gemini call).

---

## 10. Front end (Angular)

### 10.1 Screens

| Screen | Route | MVP? | Contents |
|---|---|---|---|
| S7 My trips | `/` | Yes | List of my trips, "New trip" button, language switch |
| S1 Chat | `/trips/:tripId` | Yes | Chat bubbles, current card, text input. PC: chat left + S2 right. Phone: tabs "Chat / Plan". |
| S2 Plan summary | right panel of S1 | Yes | Each slot with status (empty / done / skipped). Tap to re-ask. |
| S3 Trip page | `/trips/:tripId/plan` | Yes | Title, day tabs, map, timeline, Shorts thumbnails, "Open in Google Maps", cost range, checks |
| S4 Shorts viewer | overlay on S3 | Yes | Vertical swipe through Shorts in trip order. Label "Day N · time · spot". |
| S5 Share sheet | from S3 | Yes | Copy link, copy plain text for LINE |
| S6 Shared page | `/s/:shareId` | Yes | Same as S3, read-only, no login needed (anonymous auth) |

Design the trip page and the shared page **for phones first**.

### 10.2 State

- The trip document in Firestore is the source of truth. Copy it into Signals for rendering.
- The current card comes from the last AI message's `ui` field.
- Temporary card state (for example, a half-selected date range) stays in the component only.
- During planning, show progress text from `trips.progress`: "Finding spots → Calculating travel times → Finding videos".

### 10.3 Language

- `LanguageService` holds `"en"` or `"ja"`. Save it to `users/{uid}.language` and localStorage (wrapped in try/catch).
- UI text from `assets/i18n/en.json` and `ja.json` via Transloco. Never hard-code UI text.
- The Maps JavaScript API language is set when the script loads. After a language change, reload the page.
- A viewer of a shared trip sees UI in their own language. The plan text stays in the trip's language.

### 10.4 Design

- Background: blue sky and grass photo, frosted-glass panels on top.
- Main buttons and user bubbles: coral. AI icon: blue sparkle.
- Each day's route has its own color. Pins show the order in the day.
- Font: Noto Sans JP (Google Fonts) for both languages.
- Badges: "Estimate" on costs and estimated legs. "Please check" on times, hours, ferries, flights.

---

## 11. Security

### 11.1 Firestore rules (summary — write the full file in `firestore.rules`)

- `users/{uid}`: read/write only by that user.
- `trips/{tripId}`: read if `request.auth.uid in resource.data.members`. **No client writes** (the API writes with the Admin SDK).
- `trips/{tripId}/messages|plans/*`: read by members. No client writes.
- `shares/{shareId}`: read by any signed-in user (anonymous included) if `active == true`.
- Shared trip read: when a viewer opens `/s/:shareId`, the API is not needed. Add the viewer to `members` as `"viewer"` through a small API call, **or** let the rules allow trip reads when a valid active share exists. Choose the first option (simpler rules).
- `cache_places/*`, `cache_videos/*`: no client access. (Top-level collections: `cache/places/{id}` is not a valid document path in Firestore.)

### 11.2 Keys and secrets

- Server keys (Places, Routes, YouTube) live in **Secret Manager** and are mounted as env vars on Cloud Run.
- Gemini uses Vertex AI with the Cloud Run service account (no API key needed).
- The Maps JavaScript key is the only key in the browser. Restrict it by HTTP referrer (App Hosting domain + localhost) and by API (Maps JavaScript + Places only). Load it from `apphosting.yaml` env, not from source code.
- Share ids: random, at least 22 characters, not guessable. Owner can set `active: false`.

---

## 12. Environment variables

**api (Cloud Run)**

| Name | Source |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | Cloud Run default |
| `GOOGLE_CLOUD_LOCATION` | e.g. `asia-northeast1` (check model availability in the region) |
| `GEMINI_MODEL_FAST` | Vertex AI model name (check current names) |
| `GEMINI_MODEL_PLANNER` | Vertex AI model name |
| `PLACES_API_KEY` | Secret Manager |
| `ROUTES_API_KEY` | Secret Manager (can share a key with Places) |
| `YOUTUBE_API_KEY` | Secret Manager |
| `ALLOWED_ORIGINS` | App Hosting URL, localhost |

**web (App Hosting)**

| Name | Source |
|---|---|
| Firebase web config | `apphosting.yaml` env (public by design) |
| `MAPS_BROWSER_KEY` | `apphosting.yaml` env, key restricted as in 11.2 |
| `API_BASE_URL` | Cloud Run URL |
| reCAPTCHA Enterprise site key | `apphosting.yaml` env |

---

## 13. Build schedule (now → Nov 10, 18:00)

Owners: **FE** = front end, **BE** = back end, **INF** = infra and data, **DES** = design and pitch. One person can hold two roles.

### Sun Nov 8 — afternoon: M0 Setup (everyone, by 17:00)
- [ ] INF: GCP project, billing, budget alert, enable APIs (Vertex AI, Maps JS, Places New, Routes, YouTube Data v3, Secret Manager, Cloud Run, Firestore).
- [ ] INF: Firebase project, Auth (Google + anonymous), Firestore, App Check.
- [ ] INF: Create API keys, restrict them, store server keys in Secret Manager.
- [ ] FE: Angular skeleton, deploy "hello" to App Hosting.
- [ ] BE: FastAPI skeleton with `/healthz`, deploy to Cloud Run (`gcloud run deploy --source`).
- [ ] DES: Name the app. Simple mockups of S1 and S3.
- **Check:** both URLs work on a phone.

### Sun Nov 8 — evening: M1 Chat (by 24:00)
- [ ] BE: `models.py`, `flow.py`, `POST /trips`, `POST /trips/{id}/messages` (card answers only).
- [ ] BE: Concierge agent for free text.
- [ ] FE: Login, S7 list, S1 chat with all 7 cards, S2 panel.
- [ ] INF: `firestore.rules`, emulator tests for member-only reads.
- [ ] FE: Language switch + `en.json` / `ja.json`.
- **Check:** a user finishes all steps in both languages. Slots are correct in Firestore.

### Mon Nov 9 — morning to afternoon: M2 Plan (by 16:00)
- [ ] BE: `places.py`, `routes.py`, Planner agent, `pipeline.py`, `POST /trips/{id}/plan`.
- [ ] BE: Warnings and one fix round.
- [ ] FE: Progress display during planning.
- **Check:** the Kyushu demo input gives a realistic 4-day plan in under 30 seconds.

### Mon Nov 9 — evening: M3 Trip page + Shorts (by 24:00)
- [ ] FE: S3 map with colored routes and numbered pins, timeline, cost, checks, badges.
- [ ] BE: `youtube.py` with cache. Pre-cache demo spots.
- [ ] FE: S4 Shorts viewer.
- **Check:** full flow from "New trip" to swiping Shorts works on a phone.

### Tue Nov 10 — morning: M4 Share + polish (by 12:00)
- [ ] BE + FE: `POST /trips/{id}/share`, S6 shared page with anonymous login.
- [ ] FE: "Copy text for LINE", "Open in Google Maps".
- [ ] DES: Visual polish.
- [ ] **Stretch only if all checks pass:** F6 edit by chat.
- **Check:** a second phone opens the share link without login.

### Tue Nov 10 — afternoon: M5 Freeze and submit (12:00 → 18:00)
- [ ] 12:00 **Feature freeze.** Bug fixes only.
- [ ] Record the demo video (real app, section 17).
- [ ] Write the product description document (official template), including "Rationale / Pros and Cons" (section 16).
- [ ] Finish `ATTRIBUTION.md` and the attribution sheet.
- [ ] Check: no secrets in the git history (`git log -p | grep -i key` and a secret scanner).
- [ ] Drive folder: document, video, attribution sheet (+ slides if in-person). Set "Anyone with the link can view".
- [ ] 18:00 Submit the GitHub URL and Drive folder in the venue's Google Form.
- [ ] Keep Cloud Run, App Hosting and credits alive until Nov 14.

---

## 14. Rules for Claude Code (copy into CLAUDE.md)

1. Read `PLAN.md` before starting a task. Follow its data model and API exactly. If a change is needed, update `PLAN.md` in the same commit.
2. Never write API keys or secrets in code, tests, docs or commit messages. Use env vars.
3. Never add a third-party AI service or LLM API. Gemini via Vertex AI only.
4. Every AI output must be validated with a Pydantic model.
5. The server decides the next chat step. Do not let the LLM decide the flow.
6. Never hard-code UI text. Use the i18n files for both `en` and `ja`.
7. When you add a library, font or asset, add it to `ATTRIBUTION.md` with its license.
8. Keep the MVP scope (section 3.1). Do not start stretch features unless asked.
9. Prefer simple, readable code. This is a 5-day hackathon project.
10. Add a short note to `docs/ai-usage.md` when AI generated a large part of a feature (what, where, why).

---

## 15. Attribution sheet (start list)

| Item | Type | License / terms |
|---|---|---|
| Angular, Angular Material, @angular/google-maps | Library | MIT |
| AngularFire, Transloco | Library | MIT |
| FastAPI, Pydantic, Uvicorn | Library | MIT / BSD |
| google-genai, firebase-admin | Library | Apache 2.0 |
| Noto Sans JP | Font | SIL Open Font License |
| Google Maps / Places / Routes data and photos | Data | Google Maps Platform Terms (show attribution) |
| YouTube videos | Content | YouTube API Services Terms (official player only) |
| Background photo | Image | TBD — record source and license |

Check each license at the source before submission.

---

## 16. Decisions log ("Own the Why" — use for "Rationale / Pros and Cons")

| Decision | Alternatives considered | Why we chose it |
|---|---|---|
| Chat with question cards | Free chat only; a long form | Cards give structured data the AI cannot misread. Free text is still allowed. One question at a time keeps it easy on phones. |
| Server decides the next step | Let the LLM drive the flow | Predictable flow, easier to test, no loops. |
| Real data check (Places + Routes) after the AI draft | Trust the AI's plan | LLMs invent places and travel times. Verification makes plans realistic. |
| Worldwide destinations, Kyushu demo | Kyushu only | Google Maps data is global, so the extra cost is small. We demo Kyushu because we live in Fukuoka and can judge plan quality. |
| User language setting (EN/JA) | Detect from browser | Many international students in Japan use a Japanese browser but prefer English. |
| Shorts in any language, searched by local name | Match video language to the user | Many spots only have local-language videos. Videos show a place well without the words. |
| YouTube Shorts as spot previews | Instagram/TikTok reels | Official API and embed player. Keeps the stack Google-only (hackathon rule). |
| Firestore progress updates | SSE streaming | Simpler, works with the real-time listener we already need. SSE moved to stretch. |
| Angular | React / Next.js, Flutter | Google framework, supported by App Hosting, has SSR for future LINE previews. |
| Cloud Run + FastAPI (Python) | Cloud Functions; Node.js backend | Pydantic gives strict validation of AI output. Cloud Run handles 30-second jobs well. |
| google-genai SDK directly, not ADK | Agent Development Kit (ADK) | Our agents are single calls with a JSON schema; the flow is decided by server code. ADK adds setup time we don't have with one day left. Can switch if a member knows ADK well. |
| Firestore | Cloud SQL | Real-time sync for shared trips, no server to manage, free tier. |
| Gemini via Vertex AI | Google AI Studio API key | Cloud credits apply. No API key in the server. |
| Flash first, Pro only if needed | Pro for all agents | Faster replies (target: first reply under 2 s) and lower cost. |
| Cost as ranges with "estimate" badges | Exact prices | We do not have live price data. Ranges are honest. |

Add a row whenever the team makes a new choice. **Detailed technical decisions (options compared, measurements, who decided) are in [`docs/decisions.md`](docs/decisions.md).**

---

## 17. Demo script (about 3 minutes, Kyushu)

1. Open the app on a phone. Choose English (or Japanese).
2. Type "I want to go to Kyushu". Pick dates in the calendar. Answer people, budget, transport and style by tapping.
3. Type "Takachiho Gorge and Mt. Inasa night view are a must". The AI makes the plan. Progress text shows each stage.
4. Show the map with each day's route. Swipe through the Shorts.
5. Show a real warning (for example, long driving on day 2). If F6 is done, fix it with "make day 2 more relaxed".
6. Copy the share link. Open it on a second phone without login.
7. (Optional, 10 s) Switch the language, or show a real plan for another city, to prove "anywhere".

Everything in the video must be real app output.

---

## 18. Submission checklist (due Nov 10, 19:00 — target 18:00)

- [ ] GitHub repository (no secrets in history)
- [ ] Product description document (official template), including:
  - [ ] Problem and target users, with evidence (for example, a short survey of friends)
  - [ ] Rationale / Pros and Cons (section 16)
  - [ ] Architecture diagram (use official Google Cloud icons)
  - [ ] Where and how we used AI, and why (required)
  - [ ] What we learned (required)
- [ ] Demo video (for the online track, this is also the pitch)
- [ ] Attribution and licensing sheet
- [ ] Pitch slides (in-person venues only)
- [ ] Drive folder set to "Anyone with the link can view"
- [ ] Deployed URL works until Nov 14

---

## 19. Open questions

- [ ] Final app name
- [ ] Team members and roles (FE / BE / INF / DES)
- [ ] Angular confirmed? (fallback: Next.js)
- [ ] Track: in-person venue or online?
- [ ] Evidence for the problem (survey?)
