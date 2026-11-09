/** TypeScript mirror of api/app/models.py (PLAN.md 7). Keep the names identical. */

export type Lang = 'en' | 'ja';
export type StepKey = 'dest' | 'dates' | 'people' | 'budget' | 'transport' | 'prefs' | 'musts';
export type UiType = StepKey | 'ready';
export type SlotStatus = 'empty' | 'done' | 'skip';
export type TransportMode = 'shinkansen' | 'train' | 'plane' | 'car' | 'bus' | 'ferry' | 'any';
export type TripStatus = 'chatting' | 'planning' | 'ready' | 'error';
export type Progress = 'spots' | 'routes' | 'videos' | 'done';

export const STEP_ORDER: StepKey[] = [
  'dest',
  'dates',
  'people',
  'budget',
  'transport',
  'prefs',
  'musts',
];

export interface PlaceRef {
  label: string;
  placeId?: string | null;
  countryCode?: string | null;
  lat?: number | null;
  lng?: number | null;
}

export interface DateRange {
  start: string; // "YYYY-MM-DD"
  end: string;
}

export interface People {
  adult: number;
  child: number;
  infant: number;
}

export interface Budget {
  basis: 'person' | 'total';
  amount?: number | null;
  currency: string;
}

export interface Slots {
  dest?: PlaceRef | null;
  origin?: PlaceRef | null;
  dates?: DateRange | null;
  nights?: number | null;
  people?: People | null;
  budget?: Budget | null;
  transport: TransportMode[];
  prefs: string[];
  musts: string[];
  status: Record<StepKey, SlotStatus>;
}

export interface UiCard {
  type: UiType;
  options: string[];
}

export interface Trip {
  id: string;
  ownerUid: string;
  members: Record<string, 'owner' | 'viewer'>;
  language: Lang;
  slots: Slots;
  asking: UiType;
  status: TripStatus;
  progress?: Progress | null;
  currentPlanId?: string | null;
  shareId?: string | null;
  messageCount?: number;
}

export interface Message {
  id: string;
  role: 'user' | 'ai';
  text: string;
  answer: { step: StepKey; value: unknown } | null;
  ui: UiCard | null;
}

export type LegMode = 'DRIVE' | 'TRANSIT' | 'WALK' | 'FLIGHT' | 'FERRY';

export interface Leg {
  mode: LegMode;
  minutes: number;
  polyline?: string | null;
  /** true = the Routes API could not compute it; show "Please check". */
  estimate: boolean;
  /** What to ride for TRANSIT/FERRY/FLIGHT ("Kamome Shinkansen", "Bus 52"); null when unknown. */
  line?: string | null;
}

export interface Stop {
  id: string;
  time: string; // "HH:MM", local time at the destination
  stayMinutes: number;
  name: string;
  nameLocal?: string | null;
  kind: string;
  placeId?: string | null;
  lat?: number | null;
  lng?: number | null;
  note: string;
  videoIds: string[];
  warn?: string | null;
  /** The move to the NEXT stop; null on the last stop of a day. */
  leg?: Leg | null;
}

export interface Day {
  day: number;
  date?: string | null;
  theme: string;
  stay: string;
  stops: Stop[];
}

export interface CostItem {
  label: string;
  min: number;
  max: number;
}

export interface Cost {
  basis: 'person' | 'total';
  min: number;
  max: number;
  items: CostItem[];
}

export interface Plan {
  title: string;
  subtitle: string;
  language: Lang;
  currency: string;
  days: Day[];
  cost?: Cost | null;
  checks: string[];
}

/** trips/{tripId}/plans/{planId} */
export interface PlanDoc {
  id: string;
  version: number;
  plan: Plan;
  reason?: string | null;
}

/** Body of POST /trips/{id}/messages (models.py MessageIn). */
export type MessageIn =
  { type: 'answer'; step: StepKey; value: unknown } | { type: 'text'; text: string };
