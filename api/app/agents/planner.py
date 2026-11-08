"""Planner agent (Person B). BACKEND_PERSON_B.md T3, PLAN.md 9.2 / 9.3 step 2.

Slots + full chat -> draft Plan, via services.llm.generate_json(MODEL_PLANNER, ...) with prompts/planner.md.
The output is validated as `Plan` (retry once on a parse error, then fail cleanly).
"""

from __future__ import annotations

from app.models import Plan, Slots


async def draft(slots: Slots, messages: list[dict], lang: str) -> Plan:
    """Return a draft Plan from the collected slots and the chat history."""
    raise NotImplementedError("TODO(B): T3 draft")


async def fix(plan: Plan, warnings: list[str], lang: str) -> Plan:
    """One repair round: return a revised Plan that addresses the warnings."""
    raise NotImplementedError("TODO(B): T3 fix")
