"""Pydantic models for the Firestore data and AI outputs in PLAN.md section 7.

Field names are camelCase on purpose: they must match the Firestore documents and the
JSON the web app reads, exactly as written in PLAN.md. Don't rename them to snake_case.

Use `model.model_dump(mode="json")` before writing to Firestore (dates → "YYYY-MM-DD").
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Shared literals
# ---------------------------------------------------------------------------

Language = Literal["en", "ja"]
SlotStatus = Literal["empty", "done", "skip"]
StepKey = Literal["dest", "dates", "people", "budget", "transport", "prefs", "musts"]
CardType = Literal["dest", "dates", "people", "budget", "transport", "prefs", "musts", "ready"]
Transport = Literal["shinkansen", "train", "plane", "car", "bus", "ferry", "any"]
LegMode = Literal["DRIVE", "TRANSIT", "WALK", "FLIGHT", "FERRY"]
CostBasis = Literal["person", "total"]

# Step order for the chat flow (PLAN.md 8.1). flow.py uses this.
STEP_ORDER: tuple[StepKey, ...] = ("dest", "dates", "people", "budget", "transport", "prefs", "musts")

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"
CURRENCY = r"^[A-Z]{3}$"


class _Model(BaseModel):
    # Reject unknown keys, so AI output with invented fields fails validation and gets retried.
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 7.2 Slots: trip conditions collected in chat
# ---------------------------------------------------------------------------


class PlaceRef(_Model):
    """A place picked by the user, resolved with the Places API before it is saved."""

    label: str = Field(min_length=1, max_length=200)
    placeId: str | None = None
    countryCode: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")


class DateRange(_Model):
    start: dt.date
    end: dt.date

    @model_validator(mode="after")
    def _end_not_before_start(self) -> DateRange:
        if self.end < self.start:
            raise ValueError("dates.end must be on or after dates.start")
        return self


class People(_Model):
    adult: int = Field(default=1, ge=0, le=50)
    child: int = Field(default=0, ge=0, le=50)
    infant: int = Field(default=0, ge=0, le=50)


class Budget(_Model):
    basis: CostBasis
    amount: int | None = Field(default=None, ge=0)
    # The server fills the currency from the destination country if the user didn't say it.
    currency: str | None = Field(default=None, pattern=CURRENCY)


class SlotStatuses(_Model):
    dest: SlotStatus = "empty"
    dates: SlotStatus = "empty"
    people: SlotStatus = "empty"
    budget: SlotStatus = "empty"
    transport: SlotStatus = "empty"
    prefs: SlotStatus = "empty"
    musts: SlotStatus = "empty"


class Slots(_Model):
    dest: PlaceRef | None = None
    origin: PlaceRef | None = None
    dates: DateRange | None = None
    nights: int | None = Field(default=None, ge=0, le=60)
    people: People | None = None
    budget: Budget | None = None
    transport: list[Transport] = Field(default_factory=list)
    prefs: list[str] = Field(default_factory=list, max_length=20)
    musts: list[str] = Field(default_factory=list, max_length=20)
    status: SlotStatuses = Field(default_factory=SlotStatuses)

    @model_validator(mode="after")
    def _dates_or_nights(self) -> Slots:
        if self.dates is not None and self.nights is not None:
            raise ValueError("use either dates or nights, not both")
        return self


# ---------------------------------------------------------------------------
# 7.3 Plan: the trip
# ---------------------------------------------------------------------------


class Leg(_Model):
    """The move from a stop to the next stop of the same day."""

    mode: LegMode
    minutes: int = Field(ge=0, le=24 * 60)
    polyline: str | None = None  # encoded polyline from the Routes API
    estimate: bool = False  # True when the Routes API couldn't compute it (UI shows "please check")


class Stop(_Model):
    id: str = Field(min_length=1, max_length=40)
    time: str = Field(pattern=HHMM, description="Local time at the destination, HH:MM")
    name: str = Field(min_length=1, max_length=200, description="Name in the trip language")
    nameLocal: str | None = Field(default=None, max_length=200, description="Name in the destination's language")
    kind: str = Field(min_length=1, max_length=40, description="e.g. view, onsen, food, sight, stay")
    # Filled by the pipeline (Places API). A Planner draft has these as null.
    placeId: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    note: str | None = Field(default=None, max_length=300)
    videoIds: list[str] = Field(default_factory=list, max_length=10)
    warn: str | None = Field(default=None, max_length=300)
    leg: Leg | None = None


class Day(_Model):
    day: int = Field(ge=1)
    date: dt.date | None = None  # None when the user gave nights instead of dates
    theme: str = Field(max_length=200)
    stay: str | None = Field(default=None, max_length=200)
    stops: list[Stop] = Field(min_length=1, max_length=15)

    @model_validator(mode="after")
    def _last_stop_has_no_leg(self) -> Day:
        if self.stops[-1].leg is not None:
            raise ValueError(f"day {self.day}: the last stop of a day must have leg = null")
        return self


class CostItem(_Model):
    label: str = Field(min_length=1, max_length=100)
    min: int = Field(ge=0)
    max: int = Field(ge=0)

    @model_validator(mode="after")
    def _range(self) -> CostItem:
        if self.max < self.min:
            raise ValueError("cost item max must be >= min")
        return self


class Cost(_Model):
    """Always a range, never one exact number (UI shows an "estimate" badge)."""

    basis: CostBasis
    min: int = Field(ge=0)
    max: int = Field(ge=0)
    items: list[CostItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _range(self) -> Cost:
        if self.max < self.min:
            raise ValueError("cost max must be >= min")
        return self


class Plan(_Model):
    title: str = Field(min_length=1, max_length=120)
    subtitle: str | None = Field(default=None, max_length=200)
    language: Language
    currency: str = Field(pattern=CURRENCY)
    days: list[Day] = Field(min_length=1, max_length=30)
    cost: Cost
    checks: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _unique_stop_ids_and_day_order(self) -> Plan:
        ids = [s.id for d in self.days for s in d.stops]
        if len(ids) != len(set(ids)):
            raise ValueError("stop ids must be unique across the plan")
        if [d.day for d in self.days] != list(range(1, len(self.days) + 1)):
            raise ValueError("days must be numbered 1, 2, 3, ... in order")
        return self


# ---------------------------------------------------------------------------
# Chat: question cards, messages, Concierge output (PLAN.md 7.1, 7.4, 8)
# ---------------------------------------------------------------------------


class Chip(_Model):
    value: str = Field(min_length=1, max_length=60)  # stable key sent back in the answer
    label: str = Field(min_length=1, max_length=60)  # text shown in the trip language


class UiCard(_Model):
    """The card shown under an AI message. The server decides it (flow.py), never the LLM."""

    type: CardType
    chips: list[Chip] = Field(default_factory=list, max_length=20)  # suggestions (popular places, prefs, ...)
    multi: bool = False  # multi-select chips (transport, prefs)
    currency: str | None = Field(default=None, pattern=CURRENCY)  # budget card
    allowSkip: bool = True  # "Not decided yet" button; False only for "ready"


class Message(_Model):
    """trips/{tripId}/messages/{msgId}. `createdAt` is a server timestamp set on write."""

    role: Literal["user", "ai"]
    text: str = Field(max_length=2000)
    answer: dict[str, Any] | None = None  # the card answer, user messages only
    ui: UiCard | None = None  # AI messages only


class SlotUpdates(_Model):
    """Partial slot values. Only the keys present are merged into `trips.slots`."""

    dest: PlaceRef | None = None
    origin: PlaceRef | None = None
    dates: DateRange | None = None
    nights: int | None = Field(default=None, ge=0, le=60)
    people: People | None = None
    budget: Budget | None = None
    transport: list[Transport] | None = None
    prefs: list[str] | None = None
    musts: list[str] | None = None


class ConciergeOutput(_Model):
    """Concierge agent output (PLAN.md 8.3). `comment` and `clarify` are in the trip language."""

    updates: SlotUpdates = Field(default_factory=SlotUpdates)
    comment: str | None = Field(default=None, max_length=400)
    clarify: str | None = Field(default=None, max_length=300)


# ---------------------------------------------------------------------------
# API request bodies (PLAN.md 9.1)
# ---------------------------------------------------------------------------


class CreateTripRequest(_Model):
    language: Language


class AnswerMessage(_Model):
    type: Literal["answer"]
    step: StepKey
    value: Any  # validated per step in flow.py (e.g. DateRange for "dates"); "skip" sets status "skip"


class TextMessage(_Model):
    type: Literal["text"]
    text: str = Field(min_length=1, max_length=1000)


MessageRequest = AnswerMessage | TextMessage
