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
