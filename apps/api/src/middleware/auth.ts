import type { MiddlewareHandler } from "hono";
import { env } from "../env.js";
import { adminAuth, appCheck } from "../lib/firebase.js";

export type AuthVars = { uid: string };

/**
 * Every API call must carry a Firebase ID token (Authorization: Bearer <token>).
 * Optionally also a Firebase App Check token (X-Firebase-AppCheck), so only our
 * app — not scripts — can spend our Gemini and Maps quota.
 */
export const requireAuth: MiddlewareHandler<{ Variables: AuthVars }> = async (c, next) => {
  if (env.DEV_SKIP_AUTH) {
    c.set("uid", c.req.header("x-dev-uid") ?? "dev-user");
    return next();
  }

  if (env.REQUIRE_APP_CHECK) {
    const token = c.req.header("x-firebase-appcheck");
    if (!token) return c.json({ error: "app_check_required" }, 401);
    try {
      await appCheck.verifyToken(token);
    } catch {
      return c.json({ error: "app_check_invalid" }, 401);
    }
  }

  const header = c.req.header("authorization") ?? "";
  const match = header.match(/^Bearer (.+)$/);
  if (!match?.[1]) return c.json({ error: "unauthenticated" }, 401);
  try {
    const decoded = await adminAuth.verifyIdToken(match[1]);
    c.set("uid", decoded.uid);
  } catch {
    return c.json({ error: "invalid_token" }, 401);
  }
  return next();
};
