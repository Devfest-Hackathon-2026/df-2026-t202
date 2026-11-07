@AGENTS.md

## Claude Code specifics
- `AGENTS.md` (above) is the shared source of truth for all agents. Put team rules there, not here.
  Each package's `CLAUDE.md` imports that package's `AGENTS.md`.
- Use plan mode for work touching more than one package, the Firestore schema, or `firestore.rules`.
- Next.js 16 APIs: read `apps/web/node_modules/next/dist/docs/` instead of relying on memory.
- `.claude/settings.json` denies reading `.env` and key files. Don't work around it (e.g. `cat .env`).
- Commit, push or deploy only when asked in this session. Before committing, run `pnpm typecheck && pnpm test`
  and report the result honestly.
- When compacting, keep: the current task and MVP step, files changed, open decisions waiting on a human, and failing checks.
