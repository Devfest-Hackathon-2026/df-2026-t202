import { ReelImport } from "@/components/ReelImport";

export default function Home() {
  return (
    <main className="mx-auto flex max-w-xl flex-col gap-8 px-5 py-12">
      <header className="flex flex-col gap-3">
        <p className="text-sm font-medium tracking-wide text-accent uppercase">Reel-to-Trip</p>
        <h1 className="text-3xl leading-tight font-semibold">
          Your saved reels, turned into one trip your whole group agrees on.
        </h1>
        <p className="text-muted">
          Paste a YouTube Shorts, Instagram Reel or TikTok link. Gemini pulls out the places, food and vibe.
        </p>
      </header>
      <ReelImport />
    </main>
  );
}
