"""Live donor count for vassarrowing.com/Give2Brew2026, pulled from GiveCampus.

Runs in GitHub Actions (.github/workflows/give2brew-live.yml). During the giving
window it checks Rowing's GiveCampus team page every 5 minutes and writes the
donor count and dollars to `give2brew2026-live.json` on the `live-data` branch.
The campaign page reads that file directly, so updates don't trigger a site
rebuild and never collide with edits to the main branch.

Settings live in data/give2brew2026.json on main (re-read every cycle):
  "auto": false            -> stop publishing (page falls back to the manual count)
  "givecampus_url": "..."  -> Rowing's team page (or the campaign page); if blank
                              the script finds the 2026 campaign on Vassar's
                              GiveCampus school page and picks the Rowing card.

  python scripts/give2brew_live.py --test   # one check against last year's page
  python scripts/give2brew_live.py --loop   # the giving-day loop
"""
import base64, datetime as dt, json, os, re, sys, time
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ET = ZoneInfo("America/New_York")
START = dt.datetime(2026, 10, 13, 8, 0, tzinfo=ET)
END = dt.datetime(2026, 10, 14, 13, 0, tzinfo=ET)
LEAD = dt.timedelta(minutes=10)    # start checking a little early
TAIL = dt.timedelta(minutes=45)    # keep checking after close for late-posted gifts
EVERY = 300                        # seconds between checks
MAX_MINUTES = 340                  # one Actions job stays under the 6-hour limit

GC = "https://www.givecampus.com"
SCHOOL = GC + "/schools/VassarCollege"
GUESSES = [SCHOOL + "/vassar-athletics-day-of-giving-2026/pages/rowing",
           SCHOOL + "/vassar-athletics-day-of-giving-2026"]
TEST_URL = SCHOOL + "/vassar-athletics-day-of-giving-2025/pages/rowing"   # 405 donors, $52,616
TEAM_RE = re.compile(r"\browing\b", re.I)
BRANCH, LIVE_PATH, CONFIG_PATH = "live-data", "give2brew2026-live.json", "data/give2brew2026.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36 vassarrowing.com-live-count"}

REPO = os.environ.get("GITHUB_REPOSITORY", "BTormey23/vassarrowing.com")
API = f"https://api.github.com/repos/{REPO}"
GH = {"Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}", "Accept": "application/vnd.github+json"}


def num(s):
    s = re.sub(r"[^\d.]", "", s or "")
    return int(float(s)) if s else None


def get(url):
    r = requests.get(url, headers=UA, timeout=30, allow_redirects=True)
    r.raise_for_status()
    return r


def parse_team_page(html):
    """Rowing's own GiveCampus page: #donor_count and #donation_count."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    d = soup.select_one("#donor_count .goal_stat_count")
    m = soup.select_one("#donation_count .goal_stat_count")
    if not d:   # fallback: any stat whose label says Donors / Donated
        for stat in soup.select(".goal_stat"):
            lab = stat.select_one(".goal_stat_label")
            val = stat.select_one(".goal_stat_count")
            if lab and val and lab.get_text(strip=True).lower().startswith("donor") and not d:
                d = val
            if lab and val and lab.get_text(strip=True).lower().startswith("donated") and not m:
                m = val
    return title, num(d.get_text()) if d else None, num(m.get_text()) if m else None


def rowing_card(html):
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select(".tiered_campaign"):
        t = card.select_one(".tiered_campaign-title")
        if t and TEAM_RE.search(t.get_text()):
            img = card.select_one("[data-link]")
            txt = card.get_text(" ", strip=True)
            dm = re.search(r"([\d,]+)\s*Donors", txt)
            mm = re.search(r"\$([\d,]+)\s*Donated", txt)
            return (img["data-link"] if img else None), (num(dm.group(1)) if dm else None), (num(mm.group(1)) if mm else None)
    return None


def team_link_from_campaign(html):
    """Campaign page: find the Rowing card's link (and its numbers as a fallback)."""
    hit = rowing_card(html)
    if hit:
        return hit
    cid = re.search(r"/campaigns/(\d+)/tiered_campaign_cards", html)   # cards load in a frame
    if cid:
        hit = rowing_card(get(f"{GC}/campaigns/{cid.group(1)}/tiered_campaign_cards?search=Rowing").text)
        if hit:
            return hit
    return None, None, None


def discover_campaign_urls():
    """Look for a 2026 athletics campaign linked from Vassar's GiveCampus school page."""
    try:
        html = get(SCHOOL).text
    except Exception:
        return []
    links = set(re.findall(r'href="(/schools/VassarCollege/[^"#?]+)"', html))
    keep = [GC + l for l in links if "2026" in l and re.search(r"athlet|give2brew|giving-day|day-of-giving", l, re.I)]
    return sorted(keep)


def read_count(configured=""):
    tried = []
    for url in ([configured] if configured else []) + GUESSES + discover_campaign_urls():
        if not url or any(t.startswith(url + " ->") for t in tried):
            continue
        try:
            r = requests.get(url, headers=UA, timeout=30, allow_redirects=True)
        except Exception as e:
            tried.append(f"{url} -> {type(e).__name__}")
            continue
        title = re.search(r"<title>([^<]{0,80})", r.text or "")
        tried.append(f"{url} -> HTTP {r.status_code}, {len(r.text)} chars, ends at {r.url}, title: {title.group(1).strip() if title else '-'}")
        if not r.ok:
            continue
        final = r.url.rstrip("/")
        if final == SCHOOL:          # GiveCampus redirects unpublished campaigns to the school page
            continue
        if "/pages/" in final:
            title, donors, dollars = parse_team_page(r.text)
            if donors is not None and TEAM_RE.search(title):
                return {"donors": donors, "dollars": dollars, "source": final}
            continue
        link, donors, dollars = team_link_from_campaign(r.text)
        if link:
            try:
                title, d2, m2 = parse_team_page(get(link).text)
                if d2 is not None:
                    return {"donors": d2, "dollars": m2, "source": link}
            except Exception:
                pass
        if donors is not None:
            return {"donors": donors, "dollars": dollars, "source": final}
    return {"error": "Rowing's 2026 GiveCampus page not found yet", "tried": tried}


# ---------- GitHub (live-data branch via the contents API) ----------

def gh(method, path, **kw):
    r = requests.request(method, API + path, headers=GH, timeout=30, **kw)
    return r


def load_config():
    r = gh("GET", f"/contents/{CONFIG_PATH}?ref=main")
    if r.ok:
        try:
            return json.loads(base64.b64decode(r.json()["content"]))
        except Exception:
            pass
    return {}


def ensure_branch():
    if gh("GET", f"/git/ref/heads/{BRANCH}").ok:
        return
    sha = gh("GET", "/git/ref/heads/main").json()["object"]["sha"]
    gh("POST", "/git/refs", json={"ref": f"refs/heads/{BRANCH}", "sha": sha})


def load_live():
    r = gh("GET", f"/contents/{LIVE_PATH}?ref={BRANCH}")
    if r.ok:
        j = r.json()
        try:
            return json.loads(base64.b64decode(j["content"])), j["sha"]
        except Exception:
            return {}, j.get("sha")
    return {}, None


def publish(obj, sha, msg):
    body = {"message": msg, "branch": BRANCH,
            "content": base64.b64encode((json.dumps(obj, indent=1) + "\n").encode()).decode(),
            "committer": {"name": "live-count-bot", "email": "live-count-bot@users.noreply.github.com"}}
    if sha:
        body["sha"] = sha
    r = gh("PUT", f"/contents/{LIVE_PATH}", json=body)
    print("publish", r.status_code, msg)
    return r.ok


def stamp(now):
    return now.astimezone(ET).strftime("%-I:%M %p %a")


def cycle(test=False):
    now = dt.datetime.now(dt.timezone.utc)
    cfg = load_config()
    if (cfg.get("auto") is False or cfg.get("bot") is False) and not test:
        print("server-side checking is off in data/give2brew2026.json; skipping")
        return
    res = read_count(TEST_URL if test else (cfg.get("givecampus_url") or "").strip())
    ensure_branch()
    prev, sha = load_live()
    if bool(prev.get("test")) != bool(test):
        prev = {"checked": prev.get("checked")}    # never mix test numbers with live ones
    out = {k: v for k, v in prev.items() if k != "tried"}
    out["checked"] = now.isoformat(timespec="seconds")
    out["test"] = bool(test)
    if "error" in res:
        out["ok"] = False
        out["error"] = res["error"]
        out["tried"] = res.get("tried", [])
    else:
        d, m = res["donors"], res["dollars"]
        if prev.get("donors") and d < prev["donors"]:
            print(f"ignoring a lower count ({d} < {prev['donors']})")   # counts never go down
            d, m = prev["donors"], prev.get("dollars", m)
        if not (0 <= d <= 20000):
            out.update(ok=False, error=f"implausible count {d}")
        else:
            changed = (d, m) != (prev.get("donors"), prev.get("dollars"))
            out.update(ok=True, error="", donors=d, dollars=m, source=res["source"])
            if changed or not prev.get("updated_iso"):
                out["updated_iso"] = now.isoformat(timespec="seconds")
                out["updated"] = stamp(now)
    # write when numbers change, on errors, and at least every 30 min as a heartbeat
    last = prev.get("checked")
    stale = not last or (now - dt.datetime.fromisoformat(last)).total_seconds() > 1800
    if out.get("donors") != prev.get("donors") or out.get("dollars") != prev.get("dollars") \
            or out.get("ok") != prev.get("ok") or "test" not in prev or stale or test:
        label = "TEST " if test else ""
        publish(out, sha, f"{label}live count: {out.get('donors')} donors, ${out.get('dollars')}" if out.get("ok")
                else f"{label}live count: {out.get('error')}")
    print(json.dumps(out))


def main():
    if "--test" in sys.argv:
        cycle(test=True)
        return
    if "--loop" not in sys.argv:
        cycle()
        return
    cfg = load_config()
    if cfg.get("bot") is False or cfg.get("auto") is False:
        print("server-side checking is off in data/give2brew2026.json (the browser Count Keeper handles it)")
        return
    began = time.time()
    while time.time() - began < MAX_MINUTES * 60:
        now = dt.datetime.now(ET)
        if now > END + TAIL:
            print("giving window closed")
            return
        if now >= START - LEAD:
            try:
                cycle()
            except Exception as e:
                print("cycle failed:", e)
        else:
            print("waiting for the window to open")
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
