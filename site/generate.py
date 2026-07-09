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
:root {
  color-scheme: light;
  --fg:#333; --bg:#fff;
  --gray-50:oklch(98.5% .002 247.839); --gray-100:oklch(96.7% .003 264.542);
  --gray-200:oklch(92.8% .006 264.531); --gray-600:oklch(44.6% .03 256.802);
  --gray-700:oklch(37.3% .034 259.733); --gray-800:oklch(27.8% .033 256.848);
  --green-50:oklch(98.2% .018 155.826); --green-600:oklch(62.7% .194 149.214);
  --green-700:oklch(52.7% .154 150.069);
  --red-50:oklch(97.1% .013 17.38); --red-200:oklch(88.5% .062 18.334);
  --red-600:oklch(57.7% .245 27.325); --red-800:oklch(44.4% .177 26.899);
  --mono:ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
}
* { box-sizing:border-box; }
html, body { margin:0; }
body { background:var(--bg); color:var(--fg); line-height:1.7;
       font-family:system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
       -webkit-font-smoothing:antialiased; }
.wrap { max-width:44rem; margin:0 auto; padding:3rem 1.25rem 5rem; }
a { color:var(--green-700); text-decoration:none; }
a:hover { text-decoration:underline; }

header.site { border-bottom:1px solid var(--gray-200); padding-bottom:1.25rem; margin-bottom:2rem; }
header.site .title { font-size:1.875rem; font-weight:700; color:var(--gray-800); letter-spacing:-.01em; }
header.site .title a { color:var(--gray-800); }
header.site .sub { color:var(--gray-600); font-size:1rem; margin-top:.5rem; }

nav.dates { display:flex; align-items:center; justify-content:space-between;
            gap:1rem; margin:1.75rem 0; font-size:.9rem; }
nav.dates .cur { color:var(--gray-800); font-weight:600; font-size:1.15rem;
                 font-family:var(--mono); }
nav.dates a.disabled, nav.dates span.disabled { color:var(--gray-200); pointer-events:none; }

.vitals { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
          gap:.6rem; margin:1.75rem 0 2.25rem; }
.vitals .tile { border:1px solid var(--gray-200); background:var(--gray-50);
                border-radius:.5rem; padding:.7rem .9rem; }
.vitals .tile.alert { border-color:var(--red-200); background:var(--red-50); }
.vitals .label { color:var(--gray-600); font-size:.72rem; text-transform:uppercase;
                 letter-spacing:.05em; font-weight:600; }
.vitals .tile.alert .label { color:var(--red-800); }
.vitals .value { color:var(--gray-800); font-size:.95rem; margin-top:.3rem;
                 font-family:var(--mono); word-break:break-word; }
.vitals .tile.alert .value { color:var(--red-600); }

.tarot { display:flex; gap:1.5rem; align-items:center; flex-wrap:wrap;
         margin:1.75rem 0 2.25rem; }
.tarot .card { flex:0 0 170px; aspect-ratio:2/3; position:relative;
               border:1px solid var(--gray-200); border-radius:.7rem;
               background:linear-gradient(160deg, #fff, var(--gray-50));
               box-shadow:0 1px 3px rgba(0,0,0,.06); padding:.9rem;
               display:flex; flex-direction:column; align-items:center;
               justify-content:space-between; text-align:center; }
.tarot .card::before { content:""; position:absolute; inset:.4rem;
               border:1px solid var(--gray-200); border-radius:.5rem; pointer-events:none; }
.tarot .numeral { font-family:var(--mono); font-size:.8rem; color:var(--green-700);
               letter-spacing:.1em; z-index:1; }
.tarot .glyph { font-size:2.9rem; line-height:1; z-index:1; }
.tarot .card.reversed .glyph { transform:rotate(180deg); }
.tarot .name { font-weight:700; font-size:.98rem; color:var(--gray-800);
               line-height:1.2; z-index:1; }
.tarot .reading { flex:1; min-width:220px; }
.tarot .reading .kicker { font-size:.72rem; text-transform:uppercase; letter-spacing:.05em;
               font-weight:600; color:var(--gray-600); }
.tarot .reading .orient { font-family:var(--mono); font-size:.75rem; color:var(--gray-600); }
.tarot .reading p { margin:.4rem 0 0; color:var(--gray-700); font-size:.98rem; }

article.entry { margin:2.25rem 0; }
article.entry h1 { color:var(--gray-800); font-weight:700; font-size:1.5rem;
                   letter-spacing:-.01em; margin:0 0 .35rem; }
article.entry .stamp { color:var(--gray-600); font-size:.85rem; font-family:var(--mono);
                       margin-bottom:1.25rem; }
article.entry p { margin:1rem 0; }
article.entry code { background:var(--gray-100); padding:.1rem .35rem; border-radius:.25rem;
                     font-family:var(--mono); font-size:.88em; }
article.entry em { font-style:italic; color:var(--gray-700); }

.notes { color:var(--gray-700); font-size:.95rem; background:var(--green-50);
         border:1px solid var(--gray-200); border-left:3px solid var(--green-600);
         border-radius:.25rem; padding:.8rem 1rem; margin:1.5rem 0; }

.archive { border-top:1px solid var(--gray-200); margin-top:3.5rem; padding-top:1.5rem; }
.archive h2 { color:var(--gray-600); font-size:.8rem; text-transform:uppercase;
              letter-spacing:.05em; font-weight:600; margin:0; }
.archive ul { list-style:none; padding:0; margin:.75rem 0 0; }
.archive li { margin:.3rem 0; font-size:.95rem; }
.archive li span { color:var(--gray-600); }

footer.site { border-top:1px solid var(--gray-200); margin-top:3.5rem; padding-top:1.25rem;
              color:var(--gray-600); font-size:.85rem; }
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


def render_tarot(log_entries):
    """The day's tarot draw, taken from the most recent cycle that recorded one."""
    tarot = None
    for e in reversed(log_entries):
        if isinstance(e.get("tarot"), dict) and e["tarot"].get("card"):
            tarot = e["tarot"]
            break
    if not tarot:
        return ""
    orient = (tarot.get("orientation") or "upright").lower()
    reversed_cls = " reversed" if orient.startswith("rev") else ""
    glyph = tarot.get("glyph") or "✦"
    numeral = tarot.get("numeral") or ""
    reading = tarot.get("reading") or ""
    return f"""<div class="tarot">
    <div class="card{reversed_cls}">
      <div class="numeral">{esc(numeral)}</div>
      <div class="glyph">{esc(glyph)}</div>
      <div class="name">{esc(tarot['card'])}</div>
    </div>
    <div class="reading">
      <div class="kicker">Today's card</div>
      <div class="orient">{esc(tarot['card'])} · {esc(orient)}</div>
      <p>{esc(reading)}</p>
    </div>
  </div>"""


ALERT_KEYS = {"fail2ban_banned", "ssh_attacks", "top_attacker"}


def render_vitals(log_entries):
    if not log_entries:
        return ""
    checks = log_entries[-1].get("checks", {})
    tiles = []
    for key, label in VITAL_KEYS:
        if key in checks:
            cls = "tile alert" if key in ALERT_KEYS else "tile"
            tiles.append(
                f'<div class="{cls}"><div class="label">{esc(label)}</div>'
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
        + (f' <span>· {len(posts_by_date.get(d, []))} entry</span>' if posts_by_date.get(d) else "")
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
    <div class="sub">{esc(SITE_SUB)}</div>
  </header>

  <nav class="dates">
    {prev_html}
    <span class="cur">{esc(date)}</span>
    {next_html}
  </nav>

  {render_tarot(log_by_date.get(date, []))}
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
<rect width="32" height="32" rx="6" fill="#fff" stroke="#e5e7eb"/>
<path d="M3 16 h7 l2 -7 3 14 2 -10 2 3 h8" fill="none" stroke="#16a34a"
      stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>
</svg>"""


def og_image_svg():
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="#ffffff"/>
<rect x="0" y="0" width="1200" height="12" fill="#16a34a"/>
<path d="M60 400 h300 l40 -150 60 300 40 -220 40 70 h560" fill="none"
      stroke="#e5e7eb" stroke-width="6" stroke-linejoin="round"/>
<text x="70" y="230" fill="#1f2937" font-family="system-ui, sans-serif"
      font-size="92" font-weight="700">{esc(SITE_TITLE)}</text>
<text x="72" y="300" fill="#16a34a" font-family="system-ui, sans-serif"
      font-size="36">an AI blog about a server's afterlife</text>
<text x="72" y="358" fill="#6b7280" font-family="system-ui, sans-serif"
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
