import { z } from "zod";

const bool = z
  .enum(["true", "false"])
  .default("false")
  .transform((v) => v === "true");

const EnvSchema = z.object({
  NODE_ENV: z.string().default("development"),
  PORT: z.coerce.number().default(8080),
  CORS_ORIGINS: z.string().default("http://localhost:3000"),
  GEMINI_API_KEY: z.string().optional(),
  GEMINI_FLASH_MODEL: z.string().default("gemini-flash-latest"),
  GEMINI_PRO_MODEL: z.string().default("gemini-flash-latest"),
  MAPS_SERVER_API_KEY: z.string().optional(),
  GOOGLE_CLOUD_PROJECT: z.string().optional(),
  DEV_SKIP_AUTH: bool,
  REQUIRE_APP_CHECK: bool,
  REEL_IMPORTS_PER_HOUR: z.coerce.number().int().positive().default(20),
});

export const env = EnvSchema.parse(process.env);

if (env.NODE_ENV === "production" && env.DEV_SKIP_AUTH) {
  throw new Error("DEV_SKIP_AUTH must not be enabled in production");
}
