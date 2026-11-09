"""Pre-cache the Kyushu demo (Person B). BACKEND_PERSON_B.md T5, PLAN.md 2.5 ("no fake demo").

Runs the real Planner and Places steps on tests/fixtures/demo_slots.json a few times (Gemini varies between runs),
then fills cache_videos in Firestore with real YouTube results for every stop. No trip or plan is saved.
Pre-caching real API results is allowed; it saves the YouTube quota (about 100 searches a day) for the recording.

Run from api/ with gcloud ADC and api/.env set (costs Gemini calls and up to ~15 YouTube searches per run):
    .venv/bin/python scripts/precache_demo.py            # 2 runs (person_b_WHY.md decision 28)
    .venv/bin/python scripts/precache_demo.py --runs 3
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import pipeline  # noqa: E402
from app.agents import planner  # noqa: E402
from app.models import Slots  # noqa: E402

SLOTS_FILE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "demo_slots.json"
PRECACHE_SEARCHES = 30  # cache every demo stop, not only the per-plan cap
DEMO_CHAT = [{"role": "user", "text": "Takachiho Gorge and Mt. Inasa night view are a must"}]  # PLAN.md 17 step 3


async def main(runs: int, lang: str) -> None:
    slots = Slots.model_validate_json(SLOTS_FILE.read_text(encoding="utf-8"))
    seen: dict[str, tuple[str, int]] = {}  # placeId -> (name, number of videos)
    for n in range(1, runs + 1):
        print(f"Run {n}/{runs}: drafting...")
        plan = await planner.draft(slots, DEMO_CHAT, lang)
        run = pipeline.Run(
            lang=lang, near=(slots.dest.lat, slots.dest.lng), country=slots.dest.countryCode, default_mode="DRIVE"
        )
        missing = await pipeline.verify(plan, run)
        pipeline.drop(plan, missing, run)
        await pipeline.add_videos(plan, run, max_searches=PRECACHE_SEARCHES)
        for stop in (s for day in plan.days for s in day.stops if s.placeId):
            seen[stop.placeId] = (stop.name, len(stop.videoIds))
        print(f"  {sum(len(d.stops) for d in plan.days)} stops, {len(missing)} not found on Google Maps")

    print(f"\nCached {len(seen)} places:")
    for name, count in sorted(seen.values()):
        print(f"  {count} video(s)  {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--lang", choices=["en", "ja"], default="en")
    args = parser.parse_args()
    asyncio.run(main(args.runs, args.lang))
