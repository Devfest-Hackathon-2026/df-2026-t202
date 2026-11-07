import { describe, expect, it } from "vitest";
import { isHiddenGem, parseReelUrl } from "./index";

describe("parseReelUrl", () => {
  it("parses YouTube Shorts, watch and youtu.be", () => {
    expect(parseReelUrl("https://www.youtube.com/shorts/dQw4w9WgXcQ")?.cacheKey).toBe("youtube_dQw4w9WgXcQ");
    expect(parseReelUrl("https://youtube.com/watch?v=dQw4w9WgXcQ&t=3")?.videoId).toBe("dQw4w9WgXcQ");
    expect(parseReelUrl("https://youtu.be/dQw4w9WgXcQ")?.platform).toBe("youtube");
  });
  it("parses Instagram and TikTok", () => {
    expect(parseReelUrl("https://www.instagram.com/reel/C1a2B3c4D5e/?igsh=x")?.cacheKey).toBe("instagram_C1a2B3c4D5e");
    expect(parseReelUrl("https://www.tiktok.com/@foo/video/7301234567890123456")?.cacheKey).toBe("tiktok_7301234567890123456");
  });
  it("rejects other hosts and junk", () => {
    expect(parseReelUrl("https://evil.com/shorts/dQw4w9WgXcQ")).toBeNull();
    expect(parseReelUrl("http://169.254.169.254/latest")).toBeNull();
    expect(parseReelUrl("file:///etc/passwd")).toBeNull();
    expect(parseReelUrl("not a url")).toBeNull();
  });
});

describe("isHiddenGem", () => {
  it("applies the rule", () => {
    expect(isHiddenGem({ rating: 4.5, userRatingCount: 120 })).toBe(true);
    expect(isHiddenGem({ rating: 4.2, userRatingCount: 120 })).toBe(false);
    expect(isHiddenGem({ rating: 4.8, userRatingCount: 900 })).toBe(false);
    expect(isHiddenGem({ rating: 5, userRatingCount: 3 })).toBe(false);
  });
});
