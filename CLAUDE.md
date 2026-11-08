@AGENTS.md

## Claude Code specifics
- `AGENTS.md` (above) holds the shared rules for all agents, and `PLAN.md` is the spec. Read PLAN.md before any task.
  `api/CLAUDE.md` and `web/CLAUDE.md` import the folder's `AGENTS.md`.
- Use plan mode for work that touches both `api/` and `web/`, `models.py`, `firestore.rules` or PLAN.md section 7.
- `.claude/settings.json` denies reading `.env` and key files. Don't work around it.
- Commit, push or deploy only when asked in this session. Before committing, run the checks in AGENTS.md → Definition of done
  and report the results honestly.
- When compacting, keep: the current task and milestone (PLAN.md 13), files changed, decisions waiting on a human, and failing checks.
