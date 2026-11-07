# Submission and judging

Source: kickoff slides (Nov 1, 2026). Deadline **Nov 10 (Tue) 19:00 JST**. After that the repo is read-only.

## Deliverables
Submit through the venue's Google Form: the GitHub URL plus a Google Drive folder set to "anyone with the link can view".
- [ ] GitHub repository (this one). The README has the deployed URL.
- [ ] Product description document (organizer template). It must include:
  - Reasons for each technology choice, with pros and cons → from `docs/DECISIONS.md`
  - Where and how AI was used, and why there (required, not scored) → from `docs/AI_USAGE.md`
  - What we learned and how we grew (required, not scored)
- [ ] Demo video (online venue: presentation video including the demo). **Must be real, not faked.**
- [ ] Attribution and licensing sheet → from `docs/ATTRIBUTION.md`
- [ ] Pitch slides (in-person venue applicants only)
- [ ] Google Cloud architecture diagram (official icons: cloud.google.com/icons)
- [ ] Deployed URL stays up through Nov 14. Check remaining credit and expiry.

## Judging: 8 items, each scored 0–3 (24 total)
1. **Use of Google tech**
   a. Google tech is the core and works effectively.
   b. The reasons for choosing it are rational and concrete.
2. **Product completeness**
   a. The operations needed to solve the problem work as one connected flow.
   b. Target users can reach their goal through the UI/UX.
   c. The design considers security, scalability and maintainability.
3. **Solving a social problem**
   a. The problem is concrete and clear.
   b. The features actually help solve it.
4. **Pitch**
   a. The demo and story are clear and have impact. Demo-first: what we built and why → demo.

## Disqualifiers
Faked demo video · third-party AI tools front and center · off-theme or off-category (must be Tourism) ·
inappropriate content · rule violations · missing required items · not running on Google Cloud.

## Platform rules
- Runtime: Cloud Run / App Hosting / Firebase Hosting / App Engine / GCE / GKE (at least one).
- Using third-party LLM APIs isn't banned, but it earns nothing for "Google tech". We use Gemini only.
- Cloud credit: $20 per team (received; the code is private and must never be committed). **It doesn't cover Google AI Studio**, so we use Vertex AI (D6).
  Check in Billing → Credits which services it covers (Maps Platform may be billed separately).
  Set budget alerts (they notify, they don't stop spend), stop unused resources, restrict API keys.
- Never commit API keys or secrets. This also counts toward the "security" score.
- Follow the GDG community guidelines.

## Timeline
| Date (JST) | Event |
| --- | --- |
| Nov 10 (Tue) 19:00 | Code freeze + submission |
| Nov 11–13 | Judges' pre-screening; Nov 13 pitch teams notified |
| Nov 14 (Sat) | Regional Day (3 venues + online). At least 1 member on site if pitching |
| Nov 15 (Sun) | Online-venue finalists announced |
| Nov 27 (Fri) 10:00–12:00 | Demo Day at Google Shibuya, 9 teams, 6 min each (5 demo/pitch + 1 Q&A) |
| Nov 29 (Sun) | GDG DevFest Tokyo, finalist exhibition |

## Final stretch plan (suggested; adjust as a team)
| When (JST) | Goal |
| --- | --- |
| Nov 9 (Mon), end of day | MVP steps 1–4 on `main`; first deploy to Cloud Run + App Hosting; golden path works on the deployed URL |
| Nov 10 (Tue) until 13:00 | Bug fixes on the golden path only; seed a labeled demo trip; Cloud Run min instances = 1; budget alert set |
| Nov 10 (Tue) 13:00–17:00 | Record the **real** demo video; write the product doc from `DECISIONS.md` and `AI_USAGE.md`; attribution sheet from `ATTRIBUTION.md`; architecture diagram |
| Nov 10 (Tue) by 18:30 | Deployed URL in the README, Drive folder set to "anyone with the link", form submitted. Don't push at 18:59 |
