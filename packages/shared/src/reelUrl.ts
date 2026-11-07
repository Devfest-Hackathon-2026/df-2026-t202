/**
 * Reel link parsing. The backend only ever talks to these hosts, which is our
 * SSRF guard: anything else is rejected before any fetch or Gemini call.
 */
export type Platform = "youtube" | "instagram" | "tiktok";

export interface ParsedReel {
  platform: Platform;
  /** Stable id used as the shared cache key: `${platform}_${id}` */
  videoId: string;
  cacheKey: string;
  /** Canonical URL we pass to Gemini / store */
  canonicalUrl: string;
}

const YT_ID = /^[A-Za-z0-9_-]{11}$/;

function hostOf(url: URL): string {
  return url.hostname.toLowerCase().replace(/^www\.|^m\./, "");
}

export function parseReelUrl(input: string): ParsedReel | null {
  let url: URL;
  try {
    url = new URL(input.trim());
  } catch {
    return null;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  const host = hostOf(url);
  const parts = url.pathname.split("/").filter(Boolean);

  // YouTube: youtu.be/<id>, youtube.com/shorts/<id>, youtube.com/watch?v=<id>
  if (host === "youtu.be" || host === "youtube.com") {
    let id: string | undefined;
    if (host === "youtu.be") id = parts[0];
    else if (parts[0] === "shorts" || parts[0] === "embed" || parts[0] === "live") id = parts[1];
    else if (parts[0] === "watch") id = url.searchParams.get("v") ?? undefined;
    if (!id || !YT_ID.test(id)) return null;
    return make("youtube", id, `https://www.youtube.com/watch?v=${id}`);
  }

  // Instagram: instagram.com/reel/<code>/ or /p/<code>/
  if (host === "instagram.com") {
    const kind = parts[0];
    const code = parts[1];
    if ((kind === "reel" || kind === "reels" || kind === "p") && code && /^[A-Za-z0-9_-]+$/.test(code)) {
      return make("instagram", code, `https://www.instagram.com/reel/${code}/`);
    }
    return null;
  }

  // TikTok: tiktok.com/@user/video/<digits>
  if (host === "tiktok.com") {
    const i = parts.indexOf("video");
    const id = i >= 0 ? parts[i + 1] : undefined;
    if (id && /^\d+$/.test(id)) {
      const user = parts[0]?.startsWith("@") ? parts[0] : "@_";
      return make("tiktok", id, `https://www.tiktok.com/${user}/video/${id}`);
    }
    return null;
  }

  return null;
}

function make(platform: Platform, videoId: string, canonicalUrl: string): ParsedReel {
  return { platform, videoId, cacheKey: `${platform}_${videoId}`, canonicalUrl };
}
