"""Pull the rowing schedule and news from vassarathletics.com into data/feeds.json.

Runs in GitHub Actions (see .github/workflows/feeds.yml). No credentials needed.
Strategies are tried in order for the schedule, and the one that worked is recorded
in the JSON's "debug" field so parsing can be tuned without guessing.
"""
import json, re, sys, datetime, html
from xml.etree import ElementTree as ET
import requests
from bs4 import BeautifulSoup

BASE = "https://www.vassarathletics.com"
SQUADS = [("Women's", "womens-rowing", "wrow"), ("Men's", "mens-rowing", "mrow")]
UA = {"User-Agent": "Mozilla/5.0 (compatible; vassarrowing.com feed bot; +https://vassarrowing.com)"}
OUT = "data/feeds.json"

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def get(url, **kw):
    r = requests.get(url, headers=UA, timeout=30, **kw)
    r.raise_for_status()
    return r


def season_years(today=None):
    """Academic season the site is in: Aug–Jul. Returns (start_year, end_year)."""
    today = today or datetime.date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return start, start + 1


def parse_date_guess(text, season):
    """Turn 'Oct 4 (Sun)', 'October 4, 2026', '10/4/2026', 'Sat, Oct 4' into ISO. Year inferred from season if absent."""
    t = text.strip()
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        return f"{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:,?\s+(\d{4}))?", t)
    if m:
        mon = MONTHS.get(m.group(1)[:3].lower())
        if mon:
            day = int(m.group(2))
            if m.group(3):
                year = int(m.group(3))
            else:
                y0, y1 = season
                year = y0 if mon >= 8 else y1
            return f"{year:04d}-{mon:02d}-{day:02d}"
    return None


def events_from_jsonld(soup, squad, season):
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if not isinstance(it, dict):
                continue
            typ = it.get("@type", "")
            if "Event" not in str(typ):
                continue
            start = it.get("startDate", "")
            date = start[:10] if start else None
            time_ = ""
            if start and "T" in start:
                try:
                    dt = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
                    time_ = dt.strftime("%-I:%M %p")
                except Exception:
                    pass
            loc = it.get("location", {})
            if isinstance(loc, dict):
                addr = loc.get("address", {})
                loc_s = loc.get("name") or (addr.get("addressLocality", "") + (", " + addr["addressRegion"] if addr.get("addressRegion") else "")) if isinstance(addr, dict) else loc.get("name", "")
            else:
                loc_s = str(loc)
            if date:
                out.append({"date": date, "time": time_, "name": html.unescape(it.get("name", "")).strip(), "location": (loc_s or "").strip(), "squad": squad})
    return out


def events_from_classic(soup, squad, season):
    out = []
    for g in soup.select(".sidearm-schedule-game"):
        d = g.select_one(".sidearm-schedule-game-opponent-date")
        n = g.select_one(".sidearm-schedule-game-opponent-name")
        l = g.select_one(".sidearm-schedule-game-location")
        t = g.select_one(".sidearm-schedule-game-time")
        date = parse_date_guess(d.get_text(" ", strip=True), season) if d else None
        time_ = t.get_text(" ", strip=True) if t else ""
        if not re.search(r"\d{1,2}(:\d{2})?\s*(a|p)\.?m", time_, re.I) and "tba" not in time_.lower():
            time_ = ""   # only keep values that look like a clock time or TBA
        if date and n:
            out.append({"date": date, "time": time_, "name": n.get_text(" ", strip=True),
                        "location": (l.get_text(" ", strip=True) if l else ""), "squad": squad})
    return out


def events_from_cards(soup, squad, season):
    out = []
    for g in soup.select("[class*='s-game-card'], [class*='schedule-event'], [class*='c-schedule']"):
        text = g.get_text(" ", strip=True)
        date = parse_date_guess(text, season)
        name_el = g.select_one("[class*='opponent'], [class*='title'], h3, h4, a")
        if date and name_el:
            name = name_el.get_text(" ", strip=True)
            if 3 < len(name) < 120:
                out.append({"date": date, "time": "", "name": name, "location": "", "squad": squad})
    return out


def events_from_txt(schedule_id, squad, season):
    """Sidearm's plain-text export. Format varies; we take any line with a parseable date."""
    r = get(f"{BASE}/services/schedule_txt.ashx?schedule={schedule_id}")
    out = []
    for line in r.text.splitlines():
        date = parse_date_guess(line, season)
        if not date:
            continue
        parts = [p.strip() for p in re.split(r"\t|\s{2,}|\|", line) if p.strip()]
        name = ""
        for p in parts:
            if not parse_date_guess(p, season) and not re.match(r"^\d{1,2}:\d{2}", p) and len(p) > 3:
                name = p
                break
        if name:
            out.append({"date": date, "time": "", "name": name, "location": "", "squad": squad})
    return out


def fetch_schedule(squad, slug, season):
    debug = {"squad": squad}
    y0, y1 = season
    for url in (f"{BASE}/sports/{slug}/schedule/{y0}-{str(y1)[2:]}", f"{BASE}/sports/{slug}/schedule"):
        try:
            r = get(url)
        except Exception as e:
            debug.setdefault("errors", []).append(f"{url}: {e}")
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for name, fn in (("jsonld", events_from_jsonld), ("classic", events_from_classic), ("cards", events_from_cards)):
            try:
                ev = fn(soup, squad, season)
            except Exception as e:
                debug.setdefault("errors", []).append(f"{name}: {e}")
                ev = []
            if ev:
                debug.update(url=url, strategy=name, count=len(ev))
                return ev, debug
        m = re.search(r"schedule_txt\.ashx\?schedule=(\d+)", r.text)
        if m:
            try:
                ev = events_from_txt(m.group(1), squad, season)
                if ev:
                    debug.update(url=url, strategy="txt", schedule_id=m.group(1), count=len(ev))
                    return ev, debug
            except Exception as e:
                debug.setdefault("errors", []).append(f"txt: {e}")
        debug.setdefault("errors", []).append(f"{url}: no strategy matched; page had {len(r.text)} chars; classes sample: " + ",".join(sorted({c for t in soup.find_all(True, class_=True) for c in t.get('class', []) if 'sched' in c.lower() or 'game' in c.lower() or 'event' in c.lower()})[:15]))
    return [], debug


def fetch_news(squad, code):
    r = get(f"{BASE}/rss?path={code}")
    root = ET.fromstring(r.content)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        date = None
        try:
            from email.utils import parsedate_to_datetime
            date = parsedate_to_datetime(pub).date().isoformat()
        except Exception:
            m = re.search(r"(\d{1,2}) ([A-Za-z]{3}) (\d{4})", pub)
            if m:
                date = f"{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
        if title and link:
            out.append({"date": date or "", "title": html.unescape(title), "url": link, "squad": squad})
    return out


def main():
    season = season_years()
    events, news, debug = [], [], {"season": f"{season[0]}-{season[1]}", "schedules": [], "news_errors": []}
    for squad, slug, code in SQUADS:
        ev, dbg = fetch_schedule(squad, slug, season)
        events.extend(ev)
        debug["schedules"].append(dbg)
        try:
            news.extend(fetch_news(squad, code))
        except Exception as e:
            debug["news_errors"].append(f"{code}: {e}")
    # de-dup events that appear on both squads' schedules
    seen, merged = {}, []
    for e in sorted(events, key=lambda x: (x["date"], x["name"])):
        k = (e["date"], e["name"].lower())
        if k in seen:
            seen[k]["squad"] = "Men's & Women's"
        else:
            seen[k] = e
            merged.append(e)
    news = sorted(news, key=lambda n: n["date"], reverse=True)
    # same story syndicated to both squads → keep once
    seen_urls, news_out = set(), []
    for n in news:
        if n["url"] in seen_urls:
            continue
        seen_urls.add(n["url"])
        news_out.append(n)
    payload = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "events": merged, "news": news_out[:20], "debug": debug}
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    print(json.dumps(debug, indent=1))
    print(f"events: {len(merged)}  news: {len(news_out)}")


if __name__ == "__main__":
    main()
