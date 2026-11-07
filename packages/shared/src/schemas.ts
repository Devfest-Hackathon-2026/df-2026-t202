import { z } from "zod";

/* ---------- Reel analysis (Gemini structured output) ---------- */

export const ExtractedPlaceSchema = z.object({
  name: z.string().describe("Place name exactly as shown or said in the reel"),
  city: z.string().optional().describe("City or area, if identifiable"),
  category: z
    .enum(["food", "cafe", "bar", "sight", "nature", "shopping", "activity", "stay", "other"])
    .describe("Best-fit category"),
  note: z.string().optional().describe("One short line on what the reel shows here"),
});

export const ReelExtractionSchema = z.object({
  isTravelContent: z.boolean().describe("False if the reel has nothing to do with travel"),
  country: z.string().optional(),
  city: z.string().optional(),
  places: z.array(ExtractedPlaceSchema).max(15),
  activities: z.array(z.string()).max(10).describe("Things to do, e.g. 'yatai street food crawl'"),
  vibeTags: z
    .array(z.string())
    .max(8)
    .describe("Short lowercase tags, e.g. 'night food', 'quiet temples', 'local cafes'"),
  summary: z.string().describe("One sentence summary of the reel"),
});
export type ReelExtraction = z.infer<typeof ReelExtractionSchema>;

export const ReelStatusSchema = z.enum(["processing", "done", "failed"]);

/* ---------- API request/response ---------- */

export const AnalyzeReelRequestSchema = z.object({
  url: z.string().url().max(500),
  tripId: z.string().min(1).max(64).optional(),
  /** Instagram/TikTok fallback: the post caption the user pasted */
  caption: z.string().max(3000).optional(),
});
export type AnalyzeReelRequest = z.infer<typeof AnalyzeReelRequestSchema>;

/* ---------- Trips ---------- */

export const TripSchema = z.object({
  destination: z.string().min(1).max(100),
  startDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  endDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  budget: z.enum(["low", "mid", "high"]).default("mid"),
  ownerId: z.string(),
  memberIds: z.array(z.string()).min(1).max(10),
  status: z.enum(["collecting", "swiping", "planning", "planned"]).default("collecting"),
});
export type Trip = z.infer<typeof TripSchema>;

export const DeckCardSchema = z.object({
  placeId: z.string(),
  title: z.string(),
  category: ExtractedPlaceSchema.shape.category,
  sourceReelId: z.string().optional(),
  order: z.number().int(),
});
export type DeckCard = z.infer<typeof DeckCardSchema>;

export const SwipeSchema = z.object({
  uid: z.string(),
  cardId: z.string(),
  liked: z.boolean(),
});
export type Swipe = z.infer<typeof SwipeSchema>;

export const ItineraryStopSchema = z.object({
  placeId: z.string(),
  slot: z.string().describe("e.g. '10:00' or 'Afternoon'"),
  why: z.string().max(160),
  sourceReelId: z.string().optional(),
  gemPlaceId: z.string().optional(),
});

export const ItineraryDaySchema = z.object({
  day: z.number().int().min(1),
  date: z.string().optional(),
  stops: z.array(ItineraryStopSchema).max(12),
});
export type ItineraryDay = z.infer<typeof ItineraryDaySchema>;

/* ---------- Hidden gem rule (kept in config so it can be tuned) ---------- */

export const HIDDEN_GEM_RULE = {
  minRating: 4.3,
  maxReviews: 300,
  minReviews: 20,
  radiusMeters: 800,
} as const;

export function isHiddenGem(p: { rating?: number; userRatingCount?: number }): boolean {
  const r = p.rating ?? 0;
  const n = p.userRatingCount ?? 0;
  return (
    r >= HIDDEN_GEM_RULE.minRating &&
    n < HIDDEN_GEM_RULE.maxReviews &&
    n >= HIDDEN_GEM_RULE.minReviews
  );
}
