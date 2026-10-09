# vassarrowing.com

Static site for Vassar Rowing alumni. Hosted on GitHub Pages; DNS at GoDaddy.

- `index.html` — the whole site (one page, sections anchored from the nav)
- `roster.js` — public roster data (name, class year, squad, side only), exported from the master workbook. Regenerate from the workbook; never hand-edit contact details into it — there are none here by design.
- `photos/` — web-sized JPGs (max 1600px)
- `photos/import/*.json` — photo manifests (Google Drive file ID → web filename). The daily feed job (`scripts/fetch_feeds.py`, which calls `scripts/import_photos.py`) downloads any listed photo that isn't in the repo yet, resizes it to 1600px, and commits it. The Drive folder must be shared "anyone with the link". Pushing a change to `scripts/fetch_feeds.py` runs the job immediately.
- `Give2Brew2026/` — the ONE OF 1000 campaign page (vassarrowing.com/Give2Brew2026). Everything that changes during the campaign lives in `data/give2brew2026.json`; the page re-reads it every minute while giving is live. Edit it on GitHub (pencil icon → Commit changes):
  - Live count: set `donors` (a whole number), optional `dollars`, and `updated` (e.g. "3:24 PM Tue"). Optional `note` replaces the auto "next unlock" line.
  - Videos: paste the Google Drive file ID (the part between `/d/` and `/view`) into `src` for the featured video, a team video, or a Power 10 clip (add a `caption`). The Drive file must be shared "Anyone with the link". YouTube works too: set `provider` to `youtube` and `src` to the video ID. Team videos are vertical (`aspect` 9:16).
  - Revealing a challenge: replace its locked placeholder with a full entry, e.g. `{"revealed": true, "name": "Matcher name", "kind": "per", "every": 50, "amount": 1000, "from": 501, "to": 750, "max": 5000, "text": "One sentence, worded exactly as announced."}`. Use `"kind": "at", "at": N` for a one-time bonus. This file is public, so never add a challenge's details before it's announced.
- `404.html` — friendly not-found page; also redirects lowercase/short links (/give2brew, /give2brew2026) to /Give2Brew2026/.
- `CNAME` — custom domain for GitHub Pages

To update: edit, commit, push. Pages redeploys in about a minute.
