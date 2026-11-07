import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { cors } from "hono/cors";
import { secureHeaders } from "hono/secure-headers";
import { env } from "./env.js";
import { requireAuth, type AuthVars } from "./middleware/auth.js";
import { reels } from "./routes/reels.js";

const app = new Hono<{ Variables: AuthVars }>();

app.use("*", secureHeaders());
app.use(
  "*",
  cors({
    origin: env.CORS_ORIGINS.split(",").map((s) => s.trim()),
    allowHeaders: ["Authorization", "Content-Type", "X-Firebase-AppCheck"],
    allowMethods: ["GET", "POST", "OPTIONS"],
    maxAge: 600,
  }),
);
app.use("*", bodyLimit({ maxSize: 64 * 1024 }));

// Structured request log (Cloud Logging parses JSON lines on stdout).
app.use("*", async (c, next) => {
  const t0 = Date.now();
  await next();
  console.log(
    JSON.stringify({
      severity: c.res.status >= 500 ? "ERROR" : "INFO",
      method: c.req.method,
      path: c.req.path,
      status: c.res.status,
      ms: Date.now() - t0,
    }),
  );
});

app.get("/healthz", (c) => c.json({ ok: true }));

const v1 = new Hono<{ Variables: AuthVars }>();
v1.use("*", requireAuth);
v1.route("/reels", reels);
app.route("/v1", v1);

app.notFound((c) => c.json({ error: "not_found" }, 404));
app.onError((err, c) => {
  console.error(JSON.stringify({ severity: "ERROR", msg: "unhandled", err: String(err) }));
  return c.json({ error: "internal" }, 500);
});

serve({ fetch: app.fetch, port: env.PORT }, (info) => {
  console.log(JSON.stringify({ severity: "INFO", msg: `api listening on :${info.port}` }));
});

export default app;
