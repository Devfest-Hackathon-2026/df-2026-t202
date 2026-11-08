"""Shared data contract. Owned by BOTH people. Change only after agreeing together."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Lang = Literal["en", "ja"]
StepKey = Literal["dest", "dates", "people", "budget", "transport", "prefs", "musts"]
STEP_ORDER: list[str] = ["dest", "dates", "people", "budget", "transport", "prefs", "musts"]
SlotStatus = Literal["empty", "done", "skip"]
TransportMode = Literal["shinkansen", "train", "plane", "car", "bus", "ferry", "any"]
LegMode = Literal["DRIVE", "TRANSIT", "WALK", "FLIGHT", "FERRY"]
UiType = Literal["dest", "dates", "people", "budget", "transport", "prefs", "musts", "ready"]
Progress = Literal["spots", "routes", "videos", "done"]
TripStatus = Literal["chatting", "planning", "ready", "error"]


# ---------- Conditions collected in chat ----------
class PlaceRef(BaseModel):
    label: str
    placeId: Optional[str] = None
    countryCode: Optional[str] = None  # ISO 3166-1 alpha-2, e.g. "JP"
    lat: Optional[float] = None
    lng: Optional[float] = None


class DateRange(BaseModel):
    start: str  # "YYYY-MM-DD"
    end: str


class People(BaseModel):
    adult: int = 1
    child: int = 0
    infant: int = 0


class Budget(BaseModel):
    basis: Literal["person", "total"] = "person"
    amount: Optional[int] = None
    currency: str = "JPY"


def _empty_status() -> dict[str, str]:
    return {k: "empty" for k in STEP_ORDER}


class Slots(BaseModel):
    dest: Optional[PlaceRef] = None
    origin: Optional[PlaceRef] = None
    dates: Optional[DateRange] = None
    nights: Optional[int] = None  # used when dates are not decided
    people: Optional[People] = None
    budget: Optional[Budget] = None
    transport: list[TransportMode] = Field(default_factory=list)
    prefs: list[str] = Field(default_factory=list)
    musts: list[str] = Field(default_factory=list)
    status: dict[StepKey, SlotStatus] = Field(default_factory=_empty_status)


class SlotUpdates(BaseModel):
    """Partial update from the Concierge. Only fields that are set change."""
    dest: Optional[str] = None    # free text; the server resolves it with the Places API
    origin: Optional[str] = None  # free text; resolved the same way
    dates: Optional[DateRange] = None
    nights: Optional[int] = None
    people: Optional[People] = None
    budget: Optional[Budget] = None
    transport: Optional[list[TransportMode]] = None
    prefs: Optional[list[str]] = None
    musts: Optional[list[str]] = None
    skip: list[StepKey] = Field(default_factory=list)  # steps the user left to the AI


class ConciergeOutput(BaseModel):
    updates: SlotUpdates = Field(default_factory=SlotUpdates)
    comment: str = ""               # short reply in the trip language
    clarify: Optional[str] = None   # one follow-up question, if the text was unclear


class UiCard(BaseModel):
    type: UiType
    options: list[str] = Field(default_factory=list)  # chip values, if any


# ---------- The trip plan ----------
class Leg(BaseModel):
    mode: LegMode
    minutes: int
    polyline: Optional[str] = None  # encoded polyline from the Routes API
    estimate: bool = False          # True = not computed by the Routes API


class Stop(BaseModel):
    id: str                         # "s-<day><index>", e.g. "s-201"
    time: str                       # "HH:MM", local time at the destination
    stayMinutes: int = 60
    name: str                       # in the trip language
    nameLocal: Optional[str] = None # in the destination's language (YouTube search)
    kind: str = "sight"             # view, food, onsen, sight, shop, activity, hotel
    placeId: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    note: str = ""
    videoIds: list[str] = Field(default_factory=list)
    warn: Optional[str] = None
    leg: Optional[Leg] = None       # move to the NEXT stop; None for the last stop of a day


class Day(BaseModel):
    day: int
    date: Optional[str] = None
    theme: str = ""
    stay: str = ""
    stops: list[Stop]


class CostItem(BaseModel):
    label: str
    min: int
    max: int


class Cost(BaseModel):
    basis: Literal["person", "total"] = "person"
    min: int
    max: int
    items: list[CostItem] = Field(default_factory=list)


class Plan(BaseModel):
    title: str
    subtitle: str = ""
    language: Lang
    currency: str = "JPY"
    days: list[Day]
    cost: Optional[Cost] = None
    checks: list[str] = Field(default_factory=list)  # things to confirm before the trip


# ---------- API request bodies ----------
class CreateTripIn(BaseModel):
    language: Lang = "en"


class MessageIn(BaseModel):
    type: Literal["answer", "text"]
    step: Optional[StepKey] = None  # for type="answer"
    value: Any = None               # for type="answer"
    text: Optional[str] = None      # for type="text"
