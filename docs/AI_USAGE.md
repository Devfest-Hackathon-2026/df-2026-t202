# AI usage log

Required in the submission doc: "where and how AI was used, and why there". Two kinds:

## In the product (Gemini via Genkit)
| Where | Model | What it does | Why AI here |
| --- | --- | --- | --- |
| `analyzeReel` | Gemini Flash | Extracts places, food, activities and vibe from a reel | Understanding video and audio needs a multimodal model |
| `buildDeck` (planned) | Gemini | Picks the next swipe cards | |
| `buildItinerary` (planned) | Gemini Pro + Places/Routes tools | Day-by-day plan with real places | |
| `explainPick` (planned) | Gemini | "Why this pick" line per stop | |

## In development (coding agents)
One line per meaningful use. Note what the AI proposed, what we kept, and what we changed or rejected.

| Date | Tool | Task | Human decision |
| --- | --- | --- | --- |
| 2026-11-08 | Claude Code | Drafted AGENTS.md / CLAUDE.md and docs from the Notion spec and kickoff slides | Team reviews before committing |
