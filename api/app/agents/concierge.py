"""Concierge agent: free text → structured slot updates (PLAN.md 8.3, BACKEND_PERSON_A.md T3)."""

import json
from datetime import datetime
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import ConciergeOutput, Slots
from app.services import llm

PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "concierge.md"
LANGUAGE_NAMES = {"en": "English", "ja": "Japanese"}


@cache
def _base_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


def system_prompt(lang: str) -> str:
    return f"{_base_prompt()}\nWrite all user-facing text in {LANGUAGE_NAMES.get(lang, 'English')}."


async def run(slots: Slots, step: str, text: str, lang: str) -> ConciergeOutput:
    """Raises llm.LLMError if Gemini fails twice."""
    user = json.dumps(
        {
            "slots": slots.model_dump(mode="json"),
            "step": step,
            "today": datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat(),
            "text": text,
        },
        ensure_ascii=False,
    )
    # Extraction is simple: minimal thinking keeps the reply around 1 s instead of 3-5 s.
    # The user is waiting in the chat: give up after 15 s and show the fallback message.
    return await llm.generate_json(
        llm.MODEL_FAST, system_prompt(lang), user, ConciergeOutput, thinking="MINIMAL", timeout=15
    )
