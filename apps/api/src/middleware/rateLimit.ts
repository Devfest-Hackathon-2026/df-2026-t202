import type { MiddlewareHandler } from "hono";
import type { AuthVars } from "./auth.js";

/**
 * Simple fixed-window limiter per user, in memory.
 * Good enough for the MVP (one or few Cloud Run instances). For strict limits
 * across many instances, move the counter to Firestore or Memorystore.
 */
export function rateLimit(opts: { key: string; limit: number; windowMs: number }): MiddlewareHandler<{
  Variables: AuthVars;
}> {
  const hits = new Map<string, { count: number; resetAt: number }>();
  return async (c, next) => {
    const id = `${opts.key}:${c.get("uid")}`;
    const now = Date.now();
    const entry = hits.get(id);
    if (!entry || entry.resetAt <= now) {
      hits.set(id, { count: 1, resetAt: now + opts.windowMs });
    } else if (entry.count >= opts.limit) {
      c.header("Retry-After", String(Math.ceil((entry.resetAt - now) / 1000)));
      return c.json({ error: "rate_limited" }, 429);
    } else {
      entry.count++;
    }
    return next();
  };
}
