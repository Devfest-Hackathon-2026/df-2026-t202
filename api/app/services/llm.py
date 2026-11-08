"""Gemini through Vertex AI (google-genai SDK). BACKEND_PERSON_A.md 3.5.

generate_json() asks for JSON that matches a Pydantic model, validates it, and retries once with the
validation error. Use it for every agent, so every AI output is validated (PLAN.md 14 rule 4).
"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import get_settings

log = logging.getLogger(__name__)

MODEL_FAST: str = get_settings().gemini_model_fast
MODEL_PLANNER: str = get_settings().gemini_model_planner or MODEL_FAST

TIMEOUT_SECONDS = 60


class LLMError(Exception):
    """Gemini failed or returned JSON that doesn't match the schema, even after one retry."""


@lru_cache
def client() -> genai.Client:
    s = get_settings()
    return genai.Client(vertexai=True, project=s.google_cloud_project, location=s.google_cloud_location)


def _config(
    system: str, schema: type[BaseModel], tools: list | None, thinking: str | None
) -> types.GenerateContentConfig:
    thinking_config = types.ThinkingConfig(thinking_level=thinking) if thinking else None
    if tools:
        # Some models can't combine tools with a strict response schema. Describe the schema in the
        # prompt instead, and still validate the answer with Pydantic.
        schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        return types.GenerateContentConfig(
            system_instruction=f"{system}\n\nReply with only a JSON object matching this JSON Schema:\n{schema_text}",
            tools=tools,
            temperature=0.2,
            thinking_config=thinking_config,
        )
    return types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.2,
        thinking_config=thinking_config,
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


async def generate_json[T: BaseModel](
    model: str,
    system: str,
    user: str,
    schema: type[T],
    tools: list | None = None,
    thinking: str | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> T:
    """Call Gemini and return a validated `schema` instance. Raises LLMError.

    `thinking`: optional Gemini thinking level ("MINIMAL", "LOW", "MEDIUM", "HIGH"). None = the model default.
    "MINIMAL" makes simple extraction (the Concierge) about 3x faster.
    `timeout`: seconds per Gemini call (each of the two attempts).
    """
    if not model:
        raise LLMError("model name is empty; set GEMINI_MODEL_FAST / GEMINI_MODEL_PLANNER")
    config = _config(system, schema, tools, thinking)
    contents = [types.Content(role="user", parts=[types.Part(text=user)])]

    for attempt in (1, 2):
        try:
            resp = await asyncio.wait_for(
                client().aio.models.generate_content(model=model, contents=contents, config=config),
                timeout=timeout,
            )
        except Exception as e:  # network, quota, timeout, safety block
            log.warning(json.dumps({"msg": "llm_call_failed", "model": model, "attempt": attempt, "err": str(e)}))
            raise LLMError(str(e)) from e

        text = _strip_fences(resp.text or "")
        try:
            return schema.model_validate_json(text)
        except ValidationError as e:
            log.warning(json.dumps({"msg": "llm_invalid_json", "model": model, "attempt": attempt}))
            if attempt == 2:
                raise LLMError(f"invalid JSON after retry: {e.errors()[:3]}") from e
            contents += [
                types.Content(role="model", parts=[types.Part(text=text)]),
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"That JSON was invalid:\n{e}\nReply again with corrected JSON only.")],
                ),
            ]
    raise AssertionError("unreachable")
