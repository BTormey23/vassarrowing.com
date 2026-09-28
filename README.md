# vassarrowing.com

Static site for Vassar Rowing alumni. Hosted on GitHub Pages; DNS at GoDaddy.

- `index.html` — the whole site (one page, sections anchored from the nav)
- `roster.js` — public roster data (name, class year, squad, side only), exported from the master workbook. Regenerate from the workbook; never hand-edit contact details into it — there are none here by design.
- `photos/` — web-sized JPGs (max 1600px)
- `photos/import/*.json` — photo manifests (Google Drive file ID → web filename). The daily feed job (`scripts/fetch_feeds.py`, which calls `scripts/import_photos.py`) downloads any listed photo that isn't in the repo yet, resizes it to 1600px, and commits it. The Drive folder must be shared "anyone with the link". Pushing a change to `scripts/fetch_feeds.py` runs the job immediately.
- `CNAME` — custom domain for GitHub Pages

To update: edit, commit, push. Pages redeploys in about a minute.
