"""Pre-cache the Kyushu demo (Person B). BACKEND_PERSON_B.md T5, PLAN.md 2.5 ("no fake demo").

Runs the pipeline steps for tests/fixtures/demo_slots.json and fills cache_places and cache_videos with
real API results, so recording the demo does not burn live quota.

Run from api/ (with ADC and .env set): .venv/bin/python scripts/precache_demo.py
"""

from __future__ import annotations


def main() -> None:
    raise NotImplementedError("TODO(B): T5 precache")


if __name__ == "__main__":
    main()
