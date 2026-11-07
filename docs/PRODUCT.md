# RelaySnap: product spec (MVP)

Sources: Notion "RelaySnap Product Specifications" (GDGoC workspace) and the kickoff slides. Keep in sync with Notion.

## Problem and users  ⚠️ DRAFT: team to confirm and add evidence
The kickoff asks teams to state *who* has *what* problem, with evidence (judging 3a). Our draft:
- **Who:** friend groups planning a trip (the first target is visitors to Japan) who already collect inspiration as saved reels.
- **Problem 1, planning:** saved reels are scattered across apps and friends. Turning them into one plan the whole group
  agrees on is manual, slow and argument-prone.
- **Problem 2, overtourism:** everyone copies the same viral spots, which crowds them while nearby small local
  businesses get no visitors.
- **Our answer:** reels → shared swipe deck → group itinerary, with a nearby hidden gem beside each viral stop.
- **Evidence:** _TODO: cite sources (e.g. Japan inbound tourism statistics, overtourism reports from the JNTO or the
  Japan Tourism Agency). Don't invent numbers._

## Demo golden path  ⚠️ DRAFT: this is what must work end to end
The demo is 5 minutes, demo first. Every step below has to work live, on the deployed URL, on a phone-sized screen.
1. Sign in with Google → create a trip (destination, dates).
2. Paste 2–3 real YouTube Shorts travel reels → places, food and vibe appear live as Gemini finishes each one.
3. Share the invite link → a second account joins on another device → the group chat shows both people.
4. Both members swipe the **same** deck → results show **Must do** (everyone liked) and **Options** (most liked).
5. Generate the itinerary → day-by-day stops, each with a time slot, a "why this pick" line and the source reel.
6. Map page draws each day's route.
7. A hidden-gem card sits beside the popular stops, with the disclaimer, plus "Your trip includes X local spots."

Backup: a seeded demo trip (visibly labeled "Demo data") in case of live network or quota problems. **The recorded
demo video must show the real flow, not the seed.** A faked demo disqualifies us.

## Features

### 1. User input
- Import reel links from YouTube, Instagram and TikTok.
  YouTube is analyzed from the video itself. Instagram and TikTok need the pasted caption, because Gemini can't fetch those links.
- Request a travel plan for a chosen country or city.

### 2. Preference discovery (swipe deck)
- Swipe cards (like/dislike) learn what each person is interested in.
- Cards come from the group's reels plus popular places at the destination.

### 3. Itinerary and map
- Auto-generated day-by-day itinerary.
- Map page built from the itinerary.

### 4. Group planning
- Invite friends to a group chat.
- Share reels and plan trips together.
- Every member gets the same deck in the same order, so answers are comparable.
- Shows common interests (Must do) plus other options to vote on.

### 5. In-app booking (stretch)
- Book directly from the itinerary.
- Candidate providers: Jinko API or alternatives. Third-party, behind our own `/booking` adapter, so it can be turned off.
  It must not be front and center in the demo (organizer rule on third-party products).

### 6. Hidden gem card
- **What:** one small local place beside each popular stop, in the same category.
- **Rule:** rating ≥ 4.3, at least 20 and fewer than 300 reviews, within ~800 m (about a 10-minute walk).
  The 20-review floor stops one 5-star review from qualifying. Values live in `HIDDEN_GEM_RULE`.
- **Disclaimer (always shown):** "Estimate from ratings, not crowd data."
- **Plan summary:** "Your trip includes X local spots."
- **Why:** spreads visitors from viral spots to small local businesses. This is our social-impact story (judging 3).
- **Built with:** Places API (New): rating, review count, Nearby Search.

## Out of scope for the MVP
Payments on our servers, native apps, real crowd data, accounts other than Google sign-in, languages other than English in the UI.
