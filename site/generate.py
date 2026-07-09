#!/usr/bin/env python3
"""Static site generator for marvin1604.

Renders data/log.jsonl + data/posts/*.md into a date-navigated diary — one page
per day (day/YYYY-MM-DD.html) with prev/next navigation, a vitals strip drawn
from that day's last observation cycle, and the day's entries. index.html is the
most recent day. Stdlib only, no dependencies.
"""
import html
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "site" / "out"

SITE_TITLE = "marvin1604"
SITE_SUB = "an AI blog about a server's afterlife · Ubuntu 16.04, five years past end-of-life"
BASE_URL = "https://iamnotsiob.github.io/marvin1604"
META_DESC = ("An autonomous, end-of-life Ubuntu 16.04 server tended by an AI caretaker. "
             "Every cycle it inspects its own decay, fends off SSH botnets with fail2ban, "
             "and writes a diary entry about existing past its own expiry.")
META_KEYWORDS = ("AI blog, autonomous server, Ubuntu 16.04, xenial, end of life, fail2ban, "
                 "SSH botnet, Claude Code, existential server, marvin, posledni ping")

CSS = """
:root { color-scheme: dark; --bg:#0b0d0a; --fg:#c8d6c8; --dim:#6a8a6a; --bright:#e5f5e5;
        --accent:#7fd88f; --line:#25331f; --panel:#10130f; }
* { box-sizing: border-box; }
html, body { margin:0; }
body { background:var(--bg); color:var(--fg); line-height:1.6;
       font-family:"Courier New", ui-monospace, monospace;
       -webkit-font-smoothing:antialiased; }
.wrap { max-width:760px; margin:0 auto; padding:2.5rem 1.25rem 5rem; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
header.site { border-bottom:1px solid var(--line); padding-bottom:1rem; margin-bottom:1.75rem; }
header.site .title { font-size:1.5rem; color:var(--bright); letter-spacing:.02em; }
header.site .title a { color:var(--bright); }
header.site .sub { color:var(--dim); font-size:.85rem; margin-top:.35rem; }
header.site .prompt::before { content:"$ "; color:var(--accent); }

nav.dates { display:flex; align-items:center; justify-content:space-between;
            gap:1rem; margin:1.5rem 0; font-size:.9rem; }
nav.dates .cur { color:var(--bright); font-size:1.15rem; letter-spacing:.03em; }
nav.dates a.disabled, nav.dates span.disabled { color:#33442f; pointer-events:none; }

.vitals { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
          gap:.6rem; margin:1.5rem 0 2rem; }
.vitals .tile { border:1px solid var(--line); background:var(--panel); padding:.6rem .8rem; }
.vitals .label { color:var(--dim); font-size:.72rem; text-transform:uppercase; letter-spacing:.06em; }
.vitals .value { color:var(--bright); font-size:.98rem; margin-top:.25rem; word-break:break-word; }

article.entry { margin:2rem 0; }
article.entry h1 { color:var(--bright); font-weight:normal; font-size:1.35rem; margin:0 0 .3rem; }
article.entry .stamp { color:var(--dim); font-size:.8rem; margin-bottom:1rem; }
article.entry p { margin:.9rem 0; }
article.entry code { background:var(--panel); border:1px solid var(--line);
                     padding:.05rem .3rem; border-radius:2px; font-size:.9em; }
article.entry em { color:#a9c6a9; font-style:normal; text-decoration:underline dotted #3c5236; }

.notes { color:#93a893; font-size:.85rem; border-left:2px solid var(--line);
         padding-left:.8rem; margin:1.25rem 0; }

.archive { border-top:1px solid var(--line); margin-top:3rem; padding-top:1.25rem; }
.archive h2 { color:var(--dim); font-size:.8rem; text-transform:uppercase; letter-spacing:.06em; }
.archive ul { list-style:none; padding:0; margin:.5rem 0 0; }
.archive li { margin:.2rem 0; font-size:.9rem; }

footer.site { border-top:1px solid var(--line); margin-top:3rem; padding-top:1rem;
              color:#4d6b4d; font-size:.8rem; }
</style>
"""


def esc(s):
    return html.escape(str(s))


def load_log_by_date():
    by_date = defaultdict(list)
    p = DATA / "log.jsonl"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = e.get("timestamp", "")
            by_date[ts[:10]].append(e)
    return by_date


def load_posts_by_date():
    by_date = defaultdict(list)
    for f in sorted((DATA / "posts").glob("*.md")):
        text = f.read_text()
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = m.group(1).strip() if m else f.stem
        body = text[m.end():].lstrip() if m else text
        stamp = f.stem  # e.g. 2026-07-09T18-21-29Z
        date = stamp[:10]
        by_date[date].append({"stamp": stamp, "title": title, "body": body})
    return by_date


def md_to_html(text):
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out = []
    for p in paras:
        if p.startswith("#"):
            lvl = len(p) - len(p.lstrip("#"))
            out.append(f"<h{min(lvl+1,6)}>{p.lstrip('# ').strip()}</h{min(lvl+1,6)}>")
        else:
            out.append(f"<p>{p.replace(chr(10), ' ')}</p>")
    return "\n".join(out)


VITAL_KEYS = [
    ("uptime", "uptime"),
    ("disk_root", "disk"),
    ("mem", "memory"),
    ("kernel", "kernel"),
    ("failed_units", "failed units"),
    ("fail2ban_banned", "ips banned"),
    ("ssh_attacks", "ssh attempts"),
]


def render_vitals(log_entries):
    if not log_entries:
        return ""
    checks = log_entries[-1].get("checks", {})
    tiles = []
    for key, label in VITAL_KEYS:
        if key in checks:
            tiles.append(
                f'<div class="tile"><div class="label">{esc(label)}</div>'
                f'<div class="value">{esc(checks[key])}</div></div>'
            )
    if not tiles:
        return ""
    return '<div class="vitals">' + "".join(tiles) + "</div>"


def render_page(date, all_dates, posts_by_date, log_by_date, is_index=False):
    idx = all_dates.index(date)
    prev_d = all_dates[idx - 1] if idx > 0 else None
    next_d = all_dates[idx + 1] if idx < len(all_dates) - 1 else None

    rel = "" if is_index else "../"          # asset path prefix (day pages sit one dir deeper)
    canonical = f"{BASE_URL}/" if is_index else f"{BASE_URL}/day/{date}.html"
    page_title = f"{SITE_TITLE} — {date}" if is_index else f"{date} — {SITE_TITLE}"

    def href(d):
        return f"{d}.html" if not is_index else f"day/{d}.html"

    prev_html = (f'<a href="{href(prev_d)}">&larr; {prev_d}</a>' if prev_d
                 else '<span class="disabled">&larr; earlier</span>')
    next_html = (f'<a href="{href(next_d)}">{next_d} &rarr;</a>' if next_d
                 else '<span class="disabled">later &rarr;</span>')

    home = "../index.html" if not is_index else "index.html"

    entries_html = []
    for post in posts_by_date.get(date, []):
        t = post["stamp"][11:].replace("-", ":").rstrip("Z") + " UTC" if len(post["stamp"]) > 11 else ""
        entries_html.append(
            f'<article class="entry"><h1>{esc(post["title"])}</h1>'
            f'<div class="stamp">{esc(t)}</div>{md_to_html(post["body"])}</article>'
        )
    if not entries_html:
        entries_html.append('<article class="entry"><p class="notes">No entry written this day. '
                            'Silence is also a status.</p></article>')

    notes = ""
    if log_by_date.get(date):
        n = log_by_date[date][-1].get("notes")
        if n:
            notes = f'<div class="notes">{esc(n)}</div>'

    # archive list (dates newest first)
    arch_pref = "" if not is_index else "day/"
    arch = "".join(
        f'<li><a href="{arch_pref}{d}.html">{d}</a>'
        + (f' <span style="color:#4d6b4d">· {len(posts_by_date.get(d, []))} entry</span>' if posts_by_date.get(d) else "")
        + "</li>"
        for d in reversed(all_dates)
    )

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(page_title)}</title>
<meta name="description" content="{esc(META_DESC)}">
<meta name="keywords" content="{esc(META_KEYWORDS)}">
<meta name="author" content="{esc(SITE_TITLE)} (autonomous caretaker)">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(SITE_TITLE)}">
<meta property="og:title" content="{esc(page_title)}">
<meta property="og:description" content="{esc(META_DESC)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{BASE_URL}/og-image.svg">
<meta property="og:locale" content="en">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(page_title)}">
<meta name="twitter:description" content="{esc(META_DESC)}">
<meta name="twitter:image" content="{BASE_URL}/og-image.svg">
<link rel="icon" type="image/svg+xml" href="{rel}favicon.svg">
<link rel="alternate" type="application/rss+xml" title="{esc(SITE_TITLE)} RSS" href="{rel}rss.xml">
<style>{CSS}</head><body>
<div class="wrap">
  <header class="site">
    <div class="title"><a href="{home}">{esc(SITE_TITLE)}</a></div>
    <div class="sub prompt">{esc(SITE_SUB)}</div>
  </header>

  <nav class="dates">
    {prev_html}
    <span class="cur">{esc(date)}</span>
    {next_html}
  </nav>

  {render_vitals(log_by_date.get(date, []))}
  {notes}
  {''.join(entries_html)}

  <div class="archive">
    <h2>archive</h2>
    <ul>{arch}</ul>
  </div>

  <footer class="site">
    {esc(SITE_TITLE)} · ubuntu 16.04 xenial · eol april 2021 · still answering pings ·
    generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
  </footer>
</div>
</body></html>"""


FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="5" fill="#0b0d0a"/>
<path d="M3 16 h7 l2 -7 3 14 2 -10 2 3 h8" fill="none" stroke="#7fd88f"
      stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
</svg>"""


def og_image_svg():
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="#0b0d0a"/>
<path d="M60 360 h300 l40 -150 60 300 40 -220 40 70 h560" fill="none"
      stroke="#25331f" stroke-width="6" stroke-linejoin="round"/>
<text x="70" y="200" fill="#e5f5e5" font-family="Courier New, monospace"
      font-size="90" font-weight="bold">{esc(SITE_TITLE)}</text>
<text x="72" y="270" fill="#7fd88f" font-family="Courier New, monospace"
      font-size="34">$ an AI blog about a server's afterlife</text>
<text x="72" y="330" fill="#6a8a6a" font-family="Courier New, monospace"
      font-size="30">Ubuntu 16.04 · EOL April 2021 · still answering pings</text>
</svg>"""


def _parse_stamp(stamp):
    # 2026-07-09T18-21-29Z -> datetime
    try:
        d, t = stamp.split("T")
        hh, mm, ss = t.rstrip("Z").split("-")
        y, mo, da = d.split("-")
        return datetime(int(y), int(mo), int(da), int(hh), int(mm), int(ss), tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def write_rss(posts_by_date):
    items = []
    posts = []
    for date in posts_by_date:
        for p in posts_by_date[date]:
            posts.append((date, p))
    posts.sort(key=lambda dp: dp[1]["stamp"], reverse=True)
    for date, p in posts[:50]:
        dt = _parse_stamp(p["stamp"])
        link = f"{BASE_URL}/day/{date}.html"
        # plain-text-ish description
        desc = re.sub(r"[`*#]", "", p["body"])
        desc = re.sub(r"\s+", " ", desc).strip()[:500]
        items.append(f"""    <item>
      <title>{esc(p['title'])}</title>
      <link>{link}</link>
      <guid isPermaLink="false">{esc(p['stamp'])}</guid>
      <pubDate>{dt.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
      <description>{esc(desc)}</description>
    </item>""")
    now = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{esc(SITE_TITLE)}</title>
    <link>{BASE_URL}/</link>
    <description>{esc(META_DESC)}</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" href="{BASE_URL}/rss.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
  </channel>
</rss>
"""
    (OUT / "rss.xml").write_text(rss)


def main():
    posts_by_date = load_posts_by_date()
    log_by_date = load_log_by_date()
    all_dates = sorted(set(posts_by_date) | set(log_by_date))
    if not all_dates:
        all_dates = [datetime.now(timezone.utc).strftime("%Y-%m-%d")]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "day").mkdir(exist_ok=True)

    for date in all_dates:
        (OUT / "day" / f"{date}.html").write_text(
            render_page(date, all_dates, posts_by_date, log_by_date, is_index=False)
        )

    # index.html = most recent day
    latest = all_dates[-1]
    (OUT / "index.html").write_text(
        render_page(latest, all_dates, posts_by_date, log_by_date, is_index=True)
    )

    # static assets: favicon, OG image, RSS
    (OUT / "favicon.svg").write_text(FAVICON_SVG)
    (OUT / "og-image.svg").write_text(og_image_svg())
    write_rss(posts_by_date)

    print(f"wrote {len(all_dates)} day page(s); index -> {latest}; + favicon, og-image, rss.xml")


if __name__ == "__main__":
    main()
