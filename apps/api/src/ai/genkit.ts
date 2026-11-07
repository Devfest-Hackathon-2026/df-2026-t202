import { googleAI } from "@genkit-ai/google-genai";
import { genkit } from "genkit";
import { env } from "../env.js";

// One Genkit instance for the whole API. Every Gemini call goes through a flow,
// so it is typed, traced (Genkit Dev UI) and testable on its own.
export const ai = genkit({
  plugins: [googleAI(env.GEMINI_API_KEY ? { apiKey: env.GEMINI_API_KEY } : {})],
});

export const flashModel = googleAI.model(env.GEMINI_FLASH_MODEL);
export const proModel = googleAI.model(env.GEMINI_PRO_MODEL);
