"""Plan pipeline (Person B). BACKEND_PERSON_B.md T4, PLAN.md 9.3. Progress goes to the trip doc (no SSE).

1. status="planning", progress="spots"     2. planner.draft
3. verify stops with places.search_text    4. progress="routes", routes.leg per leg
5. re-time each day                        6. warnings (> 300 min driving/day, outside opening hours)
7. >= 3 warnings -> planner.fix once       8. progress="videos", youtube.shorts_for per stop
9. save_plan -> planId                     10. on error: status="error", re-raise as HTTP 500
Run Places / Routes / YouTube calls in parallel (asyncio.gather). Target: under 30 s.
"""

from __future__ import annotations


async def run(trip_id: str) -> str:
    """Run the full pipeline for a trip and return the saved planId."""
    raise NotImplementedError("TODO(B): T4 pipeline")
