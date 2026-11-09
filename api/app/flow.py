"""Chat step machine (PLAN.md 8.1).

The server, not the LLM, decides which question comes next. Everything here is pure (no I/O) except
search_place(), so it is easy to unit-test.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.models import STEP_ORDER, Budget, DateRange, People, PlaceRef, Slots, SlotUpdates, UiCard

log = logging.getLogger(__name__)

READY = "ready"
TRANSPORT_OPTIONS = ["shinkansen", "train", "plane", "car", "bus", "ferry", "any"]
PREF_OPTIONS = ["onsen", "food", "views", "history", "walking", "night_view", "nature", "shopping"]
MAX_LIST_ITEMS = 20
MAX_ITEM_LENGTH = 100


class AnswerError(ValueError):
    """The card answer has the wrong shape. The API returns 400 with this message."""


class PlaceLookupError(Exception):
    """Places lookup failed (network, quota, missing key). Not the same as "no such place" (None)."""


# ---------------------------------------------------------------------------
# Texts (fixed per step, no LLM)
# ---------------------------------------------------------------------------

QUESTIONS: dict[str, dict[str, str]] = {
    "dest": {"en": "Where do you want to go?", "ja": "どこに行きたいですか？"},
    "dates": {"en": "When do you want to go?", "ja": "いつ行きますか？"},
    "people": {"en": "How many people are going?", "ja": "何人で行きますか？"},
    "budget": {"en": "What is your budget?", "ja": "予算はどのくらいですか？"},
    "transport": {"en": "How will you get around?", "ja": "現地での移動手段は？"},
    "prefs": {"en": "What kind of trip do you want?", "ja": "どんな旅にしたいですか？"},
    "musts": {"en": "Any places you must visit?", "ja": "必ず行きたい場所はありますか？"},
    READY: {"en": "Your plan is ready to build!", "ja": "プランを作成する準備ができました！"},
}

TEXTS: dict[str, dict[str, str]] = {
    "rebuild": {"en": "Updated. Build the plan again?", "ja": "更新しました。プランを作り直しますか？"},
    "fallback": {
        "en": "Sorry, I didn't catch that. You can use the card below.",
        "ja": "すみません、うまく読み取れませんでした。下のカードから選んでください。",
    },
    "place_not_found": {
        "en": "I couldn't find that place. Could you tell me the city or region?",
        "ja": "その場所が見つかりませんでした。都市名や地域名を教えてください。",
    },
    "place_lookup_failed": {
        "en": "I couldn't look that place up right now. Please try again.",
        "ja": "今は場所を調べられませんでした。もう一度お試しください。",
    },
    "skip": {"en": "Not decided yet", "ja": "まだ決めていない"},
    "none": {"en": "None", "ja": "なし"},
}


def _lang(lang: str) -> str:
    return "ja" if lang == "ja" else "en"


def question_for(step: str, lang: str) -> str:
    return QUESTIONS[step][_lang(lang)]


def text_for(key: str, lang: str) -> str:
    return TEXTS[key][_lang(lang)]


# ---------------------------------------------------------------------------
# Step order and cards
# ---------------------------------------------------------------------------


def next_step(slots: Slots) -> str:
    """The first step whose status is "empty", else "ready"."""
    for step in STEP_ORDER:
        if slots.status.get(step, "empty") == "empty":
            return step
    return READY


def can_answer(slots: Slots, asking: str, step: str) -> bool:
    """A card answer is accepted for the step being asked, or as an edit of a step already answered.
    Steps that haven't been asked yet are rejected."""
    return step == asking or slots.status.get(step) in ("done", "skip")


BUDGET_CHIPS: dict[str, list[int]] = {
    "JPY": [30000, 50000, 80000, 120000],
    "KRW": [300000, 500000, 800000, 1200000],
    "TWD": [8000, 12000, 20000, 30000],
    "THB": [7000, 12000, 20000, 30000],
    "INR": [15000, 25000, 40000, 60000],
}
DEFAULT_BUDGET_CHIPS = [300, 500, 800, 1200]  # USD, EUR, GBP and others


def card_for(step: str, slots: Slots) -> UiCard:
    """The card shown with the question for `step`."""
    if step == "transport":
        return UiCard(type="transport", options=TRANSPORT_OPTIONS)
    if step == "prefs":
        return UiCard(type="prefs", options=PREF_OPTIONS)
    if step == "budget":
        currency = slots.currency or (slots.budget.currency if slots.budget else currency_for(_country(slots)))
        chips = BUDGET_CHIPS.get(currency, DEFAULT_BUDGET_CHIPS)
        return UiCard(type="budget", options=[str(c) for c in chips])
    return UiCard(type=step)  # dest, dates, people, musts, ready


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

EURO_COUNTRIES = {
    "AT", "BE", "HR", "CY", "EE", "FI", "FR", "DE", "GR", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PT", "SK",
    "SI", "ES",
}  # fmt: skip
CURRENCY_BY_COUNTRY = {"JP": "JPY", "US": "USD", "KR": "KRW", "TW": "TWD", "TH": "THB", "GB": "GBP", "IN": "INR"}


def currency_for(country_code: str | None) -> str:
    code = (country_code or "").upper()
    if code in EURO_COUNTRIES:
        return "EUR"
    return CURRENCY_BY_COUNTRY.get(code, "USD")


def _country(slots: Slots) -> str | None:
    return slots.dest.countryCode if slots.dest else None


def _sync_currency(slots: Slots, old_country: str | None) -> None:
    """When the destination changes, the budget currency follows it, unless the user already set an amount.
    Exception: an amount set before any destination got the placeholder currency_for(None); the new
    destination's currency replaces it (the amount was meant in local money, not USD)."""
    if slots.currency:  # the user picked a currency in settings: it never follows the destination
        slots.budget = (slots.budget or Budget()).model_copy(update={"currency": slots.currency})
        return
    b = slots.budget
    if slots.status.get("budget") == "done" and b and b.amount is not None:
        if old_country or b.currency != currency_for(None):
            return
    currency = currency_for(_country(slots))
    slots.budget = (slots.budget or Budget()).model_copy(update={"currency": currency})


# ---------------------------------------------------------------------------
# Applying card answers
# ---------------------------------------------------------------------------


def apply_answer(slots: Slots, step: str, value: Any) -> Slots:
    """Return new slots with the card answer for `step` applied. "skip" leaves the step to the AI.
    Raises AnswerError if `value` has the wrong shape."""
    new = slots.model_copy(deep=True)
    if value == "skip":
        new.status[step] = "skip"
        return new
    try:
        _APPLY[step](new, value)
    except (ValidationError, ValueError, TypeError, KeyError, AttributeError) as e:
        raise AnswerError(f"invalid answer for {step}: {e}") from None
    new.status[step] = "done"
    return new


def answer_value(step: str, slots: Slots) -> Any:
    """The normalized slot value a card answer produced, as JSON (stored in the user message's `answer`)."""
    data = slots.model_dump(mode="json")
    if step == "dates":
        return {"dates": data["dates"], "nights": data["nights"]}
    if step == "transport":
        return {"transport": data["transport"], "origin": data["origin"]}
    return data[step]


def _set_dest(slots: Slots, value: Any) -> None:
    place = _place(value)
    if not place.label:
        raise ValueError("label is empty")
    old_country = _country(slots)
    slots.dest = place
    _sync_currency(slots, old_country)


def _set_dates(slots: Slots, value: Any) -> None:
    """value: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} or {"nights": n}."""
    if isinstance(value, dict) and "nights" in value:
        nights = int(value["nights"])
        if not 0 <= nights <= 60:
            raise ValueError("nights must be 0-60")
        slots.nights, slots.dates = nights, None
        return
    dates = DateRange.model_validate(value)
    start, end = date.fromisoformat(dates.start), date.fromisoformat(dates.end)
    if end < start:
        raise ValueError("end is before start")
    if (end - start).days > 60:
        raise ValueError("trip longer than 60 days")
    slots.dates, slots.nights = dates, None


def _set_people(slots: Slots, value: Any) -> None:
    people = People.model_validate(value)
    counts = (people.adult, people.child, people.infant)
    if min(counts) < 0 or max(counts) > 50 or people.adult + people.child < 1:
        raise ValueError("need 1-50 travellers")
    slots.people = people


def _set_budget(slots: Slots, value: Any) -> None:
    """value: {"basis": "person" | "total", "amount": n, "currency"?: "JPY"}. Currency defaults to the destination's."""
    if not isinstance(value, dict):
        raise TypeError("budget must be an object")
    currency = (
        slots.currency
        or value.get("currency")
        or (slots.budget.currency if slots.budget else currency_for(_country(slots)))
    )
    budget = Budget.model_validate({**value, "currency": currency})
    if budget.amount is not None and budget.amount < 0:
        raise ValueError("amount must be >= 0")
    slots.budget = budget


def _set_transport(slots: Slots, value: Any) -> None:
    """value: {"transport": [...], "origin": PlaceRef | null}, or just a list of modes."""
    if isinstance(value, list):
        slots.transport = Slots.model_validate({"transport": value or ["any"]}).transport
        return
    modes = value.get("transport")
    slots.transport = Slots.model_validate({"transport": modes or ["any"]}).transport
    # The card's start-point question is the answer: a place, or null for "not decided yet"
    # (an area was already turned into null by the lookup). It replaces any earlier start.
    if "origin" in value:
        origin = value.get("origin")
        slots.origin = _place(origin) if origin else None


def _place(value: Any) -> PlaceRef:
    place = PlaceRef.model_validate(value)
    place.label = place.label.strip()[:MAX_ITEM_LENGTH]
    return place


def _set_prefs(slots: Slots, value: Any) -> None:
    slots.prefs = _string_list(value)


def _set_musts(slots: Slots, value: Any) -> None:
    slots.musts = [] if value in ("none", None) else _string_list(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise TypeError("expected a list of strings")
    items = [str(v).strip()[:MAX_ITEM_LENGTH] for v in value if str(v).strip()]
    return list(dict.fromkeys(items))[:MAX_LIST_ITEMS]  # drop duplicates, keep order


_APPLY = {
    "dest": _set_dest,
    "dates": _set_dates,
    "people": _set_people,
    "budget": _set_budget,
    "transport": _set_transport,
    "prefs": _set_prefs,
    "musts": _set_musts,
}


# ---------------------------------------------------------------------------
# Merging Concierge updates (free text)
# ---------------------------------------------------------------------------


def merge_updates(
    slots: Slots, updates: SlotUpdates, dest: PlaceRef | None = None, origin: PlaceRef | None = None
) -> Slots:
    """Merge Concierge updates. `dest`/`origin` are the free-text places already resolved with Places
    (unresolved ones are left out). Each field that is set marks its step "done".

    Unlike card answers, partial values overlay the current ones (people, budget) and prefs/musts are
    added to the current lists: the prompt tells Gemini to send only what changed. Removing an item is
    done with the card, which replaces the list."""
    new = slots.model_copy(deep=True)

    if dest is not None:
        old_country = _country(new)
        new.dest = dest
        new.status["dest"] = "done"
        _sync_currency(new, old_country)
    if origin is not None:
        new.origin = origin
    if updates.dates is not None:
        _try(new, "dates", updates.dates.model_dump())
    elif updates.nights is not None:
        _try(new, "dates", {"nights": updates.nights})
    if updates.people is not None:
        _try(new, "people", _overlay(new.people, updates.people))
    if updates.budget is not None:
        # Only the fields Gemini set, so the destination's currency is kept unless the user named one.
        _try(new, "budget", _overlay(new.budget, updates.budget))
        if new.currency and new.budget:  # the settings currency wins over one named in the chat
            new.budget = new.budget.model_copy(update={"currency": new.currency})
    if updates.transport is not None:
        _try(new, "transport", updates.transport)
    if updates.prefs is not None:
        _try(new, "prefs", new.prefs + updates.prefs)  # _string_list dedupes and caps
    if updates.musts is not None:
        _try(new, "musts", new.musts + updates.musts)
    for step in updates.skip:
        if new.status.get(step) == "empty":
            new.status[step] = "skip"
    return new


def _overlay(current: BaseModel | None, update: BaseModel) -> dict:
    """The current value with only the fields Gemini set replaced ({"child": 1} keeps the adults)."""
    base = current.model_dump() if current else {}
    return {**base, **update.model_dump(exclude_unset=True)}


def _try(slots: Slots, step: str, value: Any) -> None:
    """Apply one Concierge value. Ignore it if invalid; the user can still answer with the card."""
    try:
        _APPLY[step](slots, value)
        slots.status[step] = "done"
    except (ValidationError, ValueError, TypeError, KeyError, AttributeError) as e:
        log.info(f'{{"msg": "concierge_value_ignored", "step": "{step}", "err": "{type(e).__name__}"}}')


# ---------------------------------------------------------------------------
# User bubble text for a card answer
# ---------------------------------------------------------------------------


def answer_text(step: str, value: Any, slots: Slots, lang: str) -> str:
    """Short text for the user's chat bubble, from the slots after the answer was applied."""
    ja = _lang(lang) == "ja"
    if value == "skip":
        return text_for("skip", lang)
    if step == "dest" and slots.dest:
        return slots.dest.label
    if step == "dates":
        if slots.dates:
            return f"{slots.dates.start} – {slots.dates.end}"
        return f"{slots.nights}泊" if ja else f"{slots.nights} nights"
    if step == "people" and slots.people:
        return _people_text(slots.people, ja)
    if step == "budget" and slots.budget:
        return _budget_text(slots.budget, ja)
    if step == "transport":
        modes = ", ".join(slots.transport)
        if not slots.origin:
            return modes
        return f"{modes}（{slots.origin.label}から）" if ja else f"{modes}, from {slots.origin.label}"
    if step == "prefs":
        return ", ".join(slots.prefs) or text_for("none", lang)
    if step == "musts":
        return ", ".join(slots.musts) or text_for("none", lang)
    return ""


def _people_text(p: People, ja: bool) -> str:
    if ja:
        parts = [f"大人{p.adult}人"]
        parts += [f"子ども{p.child}人"] if p.child else []
        parts += [f"幼児{p.infant}人"] if p.infant else []
        return "・".join(parts)
    parts = [f"{p.adult} adults"]
    parts += [f"{p.child} children"] if p.child else []
    parts += [f"{p.infant} infants"] if p.infant else []
    return ", ".join(parts)


def _budget_text(b: Budget, ja: bool) -> str:
    if b.amount is None:
        amount = "未定" if ja else "Not set"
    else:
        amount = f"{b.amount:,} {b.currency}"
    if ja:
        return f"{amount}（{'1人あたり' if b.basis == 'person' else '合計'}）"
    return f"{amount} {'per person' if b.basis == 'person' else 'total'}"


# ---------------------------------------------------------------------------
# Free-text place lookup (temporary until Person B's places.search_text exists)
# ---------------------------------------------------------------------------

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = "places.id,places.displayName,places.location,places.addressComponents"


async def search_place(query: str, lang: str) -> PlaceRef | None:
    """Resolve free text like "Kyushu" to a place. Uses Person B's places.search_text when it exists.

    Returns None when no place matches. Raises PlaceLookupError when the lookup itself fails
    (search_text raises httpx.HTTPError after its retries, or RuntimeError when the key is missing).
    """
    try:
        from app.services.places import search_text  # Person B
    except ImportError:
        search_text = _search_text_fallback
    try:
        result = await search_text(query, lang)
        return PlaceRef.model_validate(result) if result else None
    except (httpx.HTTPError, RuntimeError, ValidationError) as e:
        log.warning(json.dumps({"msg": "place_lookup_failed", "err": type(e).__name__}))
        raise PlaceLookupError from e


# Google Places types that describe an area, not a spot you can stand at.
AREA_TYPES = {
    "country",
    "administrative_area_level_1",
    "administrative_area_level_2",
    "administrative_area_level_3",
    "locality",
    "sublocality",
    "sublocality_level_1",
    "postal_town",
    "neighborhood",
    "colloquial_area",
    "archipelago",
    "continent",
    "political",
    "geocode",
}


def is_area(place: dict) -> bool:
    """True for a city, state, region or country; False for an airport, station, hotel or address."""
    primary = place.get("primaryType")
    if primary:
        return primary in AREA_TYPES
    types = set(place.get("types") or [])
    return bool(types) and types <= AREA_TYPES


async def search_start(query: str, lang: str) -> PlaceRef | None:
    """Resolve where the trip starts. Only a specific place counts (airport, station, hotel, address):
    Day 1 begins there. A city, state or region returns None, so Day 1 begins at the first attraction.
    Raises PlaceLookupError when the lookup itself fails, like search_place."""
    try:
        from app.services.places import search_text
    except ImportError:
        search_text = _search_text_fallback
    try:
        result = await search_text(query, lang)
        if not result or is_area(result):
            return None
        return PlaceRef.model_validate(result)
    except (httpx.HTTPError, RuntimeError, ValidationError) as e:
        log.warning(json.dumps({"msg": "place_lookup_failed", "err": type(e).__name__}))
        raise PlaceLookupError from e


async def _search_text_fallback(query: str, lang: str) -> dict | None:
    key = get_settings().places_api_key
    if key is None:
        raise RuntimeError("PLACES_API_KEY is not set")
    headers = {"X-Goog-Api-Key": key.get_secret_value(), "X-Goog-FieldMask": FIELD_MASK}
    body = {"textQuery": query[:200], "languageCode": _lang(lang), "pageSize": 1}
    async with httpx.AsyncClient(timeout=10) as http:  # errors raise; search_place handles them
        resp = await http.post(TEXT_SEARCH_URL, json=body, headers=headers)
        resp.raise_for_status()
    places = resp.json().get("places") or []
    if not places:
        return None
    p = places[0]
    components = p.get("addressComponents", [])
    country = next((c.get("shortText") for c in components if "country" in c.get("types", [])), None)
    return {
        "label": p.get("displayName", {}).get("text") or query,
        "placeId": p.get("id"),
        "countryCode": country,
        "lat": p.get("location", {}).get("latitude"),
        "lng": p.get("location", {}).get("longitude"),
    }
