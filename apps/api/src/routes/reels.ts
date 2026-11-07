import { AnalyzeReelRequestSchema, parseReelUrl } from "@rtt/shared";
import { FieldValue } from "firebase-admin/firestore";
import { Hono } from "hono";
import { analyzeReelFlow, CaptionRequiredError } from "../ai/flows/analyzeReel.js";
import { env } from "../env.js";
import { db } from "../lib/firebase.js";
import type { AuthVars } from "../middleware/auth.js";
import { rateLimit } from "../middleware/rateLimit.js";

export const reels = new Hono<{ Variables: AuthVars }>();

/**
 * POST /reels  { url, tripId?, caption? }
 *
 * 1. Allowlist check on the link (YouTube / Instagram / TikTok only).
 * 2. Shared cache by video id: a reel is analyzed once for every user.
 * 3. Analyze with Gemini via the Genkit flow.
 *
 * MVP runs the analysis inline. Next step: write `processing`, enqueue a
 * Cloud Task, and let the worker finish it (the client already listens to
 * the reel doc, so the UI does not change).
 */
reels.post(
  "/",
  rateLimit({ key: "reel", limit: env.REEL_IMPORTS_PER_HOUR, windowMs: 60 * 60 * 1000 }),
  async (c) => {
    const body = AnalyzeReelRequestSchema.safeParse(await c.req.json().catch(() => null));
    if (!body.success) return c.json({ error: "bad_request", issues: body.error.issues }, 400);

    const parsed = parseReelUrl(body.data.url);
    if (!parsed) return c.json({ error: "unsupported_link" }, 400);

    const uid = c.get("uid");
    const reelRef = db.collection("reels").doc(parsed.cacheKey);

    const cached = await reelRef.get();
    if (cached.exists && cached.get("status") === "done") {
      await attachToTrip(body.data.tripId, parsed.cacheKey, parsed.canonicalUrl, parsed.platform, uid);
      return c.json({ id: parsed.cacheKey, cached: true, ...cached.data() });
    }

    await reelRef.set(
      {
        status: "processing",
        platform: parsed.platform,
        url: parsed.canonicalUrl,
        updatedAt: FieldValue.serverTimestamp(),
      },
      { merge: true },
    );

    try {
      const extraction = await analyzeReelFlow({
        platform: parsed.platform,
        url: parsed.canonicalUrl,
        caption: body.data.caption,
      });
      const doc = {
        status: "done" as const,
        platform: parsed.platform,
        url: parsed.canonicalUrl,
        extraction,
        updatedAt: FieldValue.serverTimestamp(),
      };
      await reelRef.set(doc, { merge: true });
      await attachToTrip(body.data.tripId, parsed.cacheKey, parsed.canonicalUrl, parsed.platform, uid);
      return c.json({ id: parsed.cacheKey, cached: false, status: "done", extraction });
    } catch (err) {
      if (err instanceof CaptionRequiredError) {
        await reelRef.delete();
        return c.json({ error: "caption_required", platform: parsed.platform }, 422);
      }
      console.error(JSON.stringify({ msg: "reel_analysis_failed", reel: parsed.cacheKey, err: String(err) }));
      await reelRef.set({ status: "failed", updatedAt: FieldValue.serverTimestamp() }, { merge: true });
      return c.json({ error: "analysis_failed" }, 502);
    }
  },
);

/** Add the reel to a trip, but only if the caller is a member of that trip. */
async function attachToTrip(
  tripId: string | undefined,
  reelId: string,
  url: string,
  platform: string,
  uid: string,
) {
  if (!tripId) return;
  const trip = await db.collection("trips").doc(tripId).get();
  const members: string[] = trip.get("memberIds") ?? [];
  if (!trip.exists || !members.includes(uid)) return;
  await trip.ref
    .collection("reels")
    .doc(reelId)
    .set({ reelRef: reelId, url, platform, addedBy: uid, createdAt: FieldValue.serverTimestamp() }, { merge: true });
}
