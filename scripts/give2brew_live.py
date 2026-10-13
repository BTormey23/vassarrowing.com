"""Live donor count for vassarrowing.com/Give2Brew2026, pulled from Vassar's giving-day site.

Vassar runs the 2026 Athletics Day of Giving on its own Slate portal
(https://engage.vassar.edu/portal/giving_day), not GiveCampus. The portal loads
its leaderboard from a plain endpoint that returns an HTML table:

  https://engage.vassar.edu/portal/giving_day?cmd=getDonorInitiatives&campaign=<id>&cntxt=initiatives_list

  <tr><td>Rowing</td><td>30</td><td>$995</td><td>175</td><td>17%</td></tr>

This script (run by .github/workflows/give2brew-live.yml) reads the Rowing row,
cross-checks it against the Coach Wells challenge card ("30 of 500 Donors") on
the challenges endpoint, and writes donors/dollars to `give2brew2026-live.json`
on the `live-data` branch. The campaign page reads that file directly from
raw.githubusercontent.com, so no site rebuild is involved.

Settings in data/give2brew2026.json on main (re-read every cycle):
  "auto": false     -> stop publishing (page falls back to the manual count)
  "bot": false      -> stop this server-side checker (the browser Count Keeper takes over)
  "campaign_id"     -> Slate campaign id, if Vassar ever changes it

  python scripts/give2brew_live.py          # check now, then every 30 min until launch nears
  python scripts/give2brew_live.py --loop   # the giving-day loop (every 5 min while the window is open)
"""
import base64, datetime as dt, json, os, re, sys, time
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ET = ZoneInfo("America/New_York")
START = dt.datetime(2026, 10, 13, 8, 0, tzinfo=ET)
END = dt.datetime(2026, 10, 14, 13, 0, tzinfo=ET)
LEAD = dt.timedelta(hours=2)       # start the fast loop a little early
TAIL = dt.timedelta(minutes=45)    # keep checking after close for late-posted gifts
EVERY = 300                        # seconds between checks inside the loop
MAX_MINUTES = 340                  # one Actions job stays under the 6-hour limit

PORTAL = "https://engage.vassar.edu/portal/giving_day"
CAMPAIGN = "9fa55dea-f4bd-7c4c-4354-5501dbfdf05b"      # Athletics Day of Giving 2026
TEAM_RE = re.compile(r"^\s*(men'?s\s*(and|&)\s*women'?s\s*)?rowing\s*$", re.I)
BRANCH, LIVE_PATH, CONFIG_PATH = "live-data", "give2brew2026-live.json", "data/give2brew2026.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36 vassarrowing.com-live-count",
      "Accept": "text/html,*/*", "Referer": PORTAL}

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


def leaderboard(campaign):
    """Rowing's row on the Teams leaderboard: donors, dollars, team goal."""
    url = f"{PORTAL}?cmd=getDonorInitiatives&campaign={campaign}&cntxt=initiatives_list"
    soup = BeautifulSoup(get(url).text, "html.parser")
    for tr in soup.select("table tr"):
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(tds) >= 3 and TEAM_RE.search(tds[0]):
            return {"donors": num(tds[1]), "dollars": num(tds[2]), "goal": num(tds[3]) if len(tds) > 3 else None, "source": url}
    raise LookupError("no Rowing row on the Teams leaderboard")


def challenge_count(campaign):
    """Cross-check: the Coach Wells challenge card shows 'N of 500 Donors'."""
    try:
        html = get(f"{PORTAL}?cmd=getChallenges&cntxt=challenges&campaign={campaign}").text
    except Exception:
        return None
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    m = re.search(r"Coach Wells.{0,600}?(\d[\d,]*)\s+of\s+500\s+Donors", text, re.I | re.S)
    return num(m.group(1)) if m else None


def read_count(campaign):
    try:
        res = leaderboard(campaign)
    except Exception as e:
        return {"error": f"leaderboard read failed: {type(e).__name__}: {str(e)[:160]}"}
    if res["donors"] is None:
        return {"error": "Rowing row found but no donor number"}
    alt = challenge_count(campaign)
    if alt is not None and alt != res["donors"]:
        res["challenge_count"] = alt      # recorded for the log; the leaderboard is the number we show
    return res


# ---------- GitHub (live-data branch via the contents API) ----------

def gh(method, path, **kw):
    return requests.request(method, API + path, headers=GH, timeout=30, **kw)


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


def cycle():
    now = dt.datetime.now(dt.timezone.utc)
    cfg = load_config()
    if cfg.get("auto") is False or cfg.get("bot") is False:
        print("server-side checking is off in data/give2brew2026.json; skipping")
        return
    res = read_count((cfg.get("campaign_id") or CAMPAIGN).strip())
    ensure_branch()
    prev, sha = load_live()
    if prev.get("test"):
        prev = {}                      # drop any leftover GiveCampus test reading
    out = {k: v for k, v in prev.items() if k not in ("tried", "test")}
    out["checked"] = now.isoformat(timespec="seconds")
    out["test"] = False
    out["keeper"] = "github-actions"
    if "error" in res:
        out["ok"] = bool(prev.get("ok")) and "donors" in prev   # keep showing the last good number
        out["error"] = res["error"]
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
            if res.get("goal"):
                out["team_goal"] = res["goal"]
            if "challenge_count" in res:
                out["challenge_count"] = res["challenge_count"]
            else:
                out.pop("challenge_count", None)
            if changed or not prev.get("updated_iso"):
                out["updated_iso"] = now.isoformat(timespec="seconds")
                out["updated"] = stamp(now)
    # write when numbers change, on errors, and at least every 30 min as a heartbeat
    last = prev.get("checked")
    try:
        stale = not last or (now - dt.datetime.fromisoformat(last)).total_seconds() > 1800
    except Exception:
        stale = True
    if out.get("donors") != prev.get("donors") or out.get("dollars") != prev.get("dollars") \
            or out.get("ok") != prev.get("ok") or out.get("error") != prev.get("error") or stale:
        publish(out, sha, f"live count: {out.get('donors')} donors, ${out.get('dollars')}" if not out.get("error")
                else f"live count: {out.get('error')}")
    print(json.dumps(out))


def main():
    """--loop: the giving-day loop (5-minute checks while the window is open).
    Anything else (a push, a manual run, the old --test flag): check now; if launch is still
    hours away, keep checking every 30 minutes for the rest of this job so early gifts show."""
    began = time.time()
    if "--loop" not in sys.argv:
        cycle()
        while time.time() - began < MAX_MINUTES * 60 and dt.datetime.now(ET) < START - LEAD:
            time.sleep(1800)
            try:
                cycle()
            except Exception as e:
                print("cycle failed:", e)
        return
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
            time.sleep(EVERY)
        else:
            try:
                cycle()
            except Exception as e:
                print("cycle failed:", e)
            time.sleep(1800)


if __name__ == "__main__":
    main()
