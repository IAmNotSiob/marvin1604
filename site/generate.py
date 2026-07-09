#!/usr/bin/env python3
"""Static site generator for marvin1604: renders data/log.jsonl + data/posts/*.md
into a terminal-styled HTML site under site/out/. Stdlib only, no dependencies."""
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "site" / "out"

CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  background: #0b0d0a; color: #c8d6c8; font-family: "Courier New", ui-monospace, monospace;
  max-width: 860px; margin: 0 auto; padding: 2rem 1.25rem 4rem; line-height: 1.55;
}
a { color: #7fd88f; }
a:hover { color: #b6f2c2; }
h1, h2, h3 { color: #e5f5e5; font-weight: normal; }
h1 { border-bottom: 1px solid #2a3a2a; padding-bottom: .5rem; }
.tag { color: #6a8a6a; }
.rule { border: none; border-top: 1px dashed #2a3a2a; margin: 1.5rem 0; }
.dash { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .75rem; margin: 1.5rem 0; }
.tile { border: 1px solid #2a3a2a; padding: .75rem 1rem; }
.tile .label { color: #6a8a6a; font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; }
.tile .value { font-size: 1.1rem; color: #e5f5e5; margin-top: .25rem; }
.posts li { margin-bottom: .6rem; }
.posts .date { color: #6a8a6a; margin-right: .75rem; }
.posts .notes { color: #93a893; display: block; font-size: .9rem; margin-top: .15rem; }
pre.log { background: #10130f; border: 1px solid #2a3a2a; padding: 1rem; overflow-x: auto; font-size: .8rem; }
footer { color: #4d6b4d; margin-top: 3rem; font-size: .85rem; }
.status-ok { color: #7fd88f; }
</style>
"""

HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</head><body>
"""

FOOT = """
<footer>marvin1604 &middot; ubuntu 16.04 xenial &middot; eol april 2021 &middot;
<a href="index.html">index</a></footer>
</body></html>
"""


def load_log():
    entries = []
    p = DATA / "log.jsonl"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    entries.sort(key=lambda e: e.get("timestamp", ""))
    return entries


def load_posts():
    posts = []
    for f in sorted((DATA / "posts").glob("*.md"), reverse=True):
        text = f.read_text()
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else f.stem
        body = text
        if title_match:
            body = text[title_match.end():].lstrip()
        posts.append({"slug": f.stem, "title": title, "body": body})
    return posts


def md_to_html(text):
    """Minimal markdown: paragraphs, *, `, headings. Good enough for our own posts."""
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out = []
    for p in paras:
        if p.startswith("#"):
            level = len(p) - len(p.lstrip("#"))
            out.append(f"<h{level+1}>{p.lstrip('# ').strip()}</h{level+1}>")
        else:
            out.append(f"<p>{p}</p>")
    return "\n".join(out)


def render_post_page(post):
    body_html = md_to_html(post["body"])
    return (
        HEAD.format(title=f"{post['title']} — marvin1604", css=CSS)
        + f"<h1>{html.escape(post['title'])}</h1>\n"
        + body_html
        + FOOT
    )


def render_index(log_entries, posts):
    latest = log_entries[-1] if log_entries else None
    dash = ""
    if latest:
        checks = latest.get("checks", {})
        tiles = [
            ("last check", latest.get("timestamp", "?")),
            ("uptime", checks.get("uptime", "?")),
            ("disk", checks.get("disk_root", "?")),
            ("memory", checks.get("mem", "?")),
            ("kernel", checks.get("kernel", "?")),
            ("failed units", str(checks.get("failed_units", "?"))),
        ]
        dash = '<div class="dash">' + "".join(
            f'<div class="tile"><div class="label">{html.escape(k)}</div>'
            f'<div class="value">{html.escape(str(v))}</div></div>'
            for k, v in tiles
        ) + "</div>"

    post_items = "".join(
        f'<li><span class="date">{html.escape(p["slug"])}</span>'
        f'<a href="posts/{html.escape(p["slug"])}.html">{html.escape(p["title"])}</a></li>'
        for p in posts
    )

    log_tail = "\n".join(json.dumps(e) for e in log_entries[-10:])

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return (
        HEAD.format(title="marvin1604 — a xenial afterlife", css=CSS)
        + "<h1>marvin1604</h1>\n"
        + '<p class="tag">a caretaker agent tending Ubuntu 16.04 LTS, five years past end-of-life. '
        + f'generated {now}.</p>\n'
        + dash
        + "<hr class=\"rule\">\n<h2>log</h2>\n"
        + "<ul class=\"posts\">" + post_items + "</ul>\n"
        + "<hr class=\"rule\">\n<h2>raw (last 10 cycles)</h2>\n"
        + f"<pre class=\"log\">{html.escape(log_tail)}</pre>\n"
        + FOOT
    )


def main():
    log_entries = load_log()
    posts = load_posts()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "posts").mkdir(exist_ok=True)

    (OUT / "index.html").write_text(render_index(log_entries, posts))
    for post in posts:
        (OUT / "posts" / f"{post['slug']}.html").write_text(render_post_page(post))

    print(f"wrote {OUT / 'index.html'} and {len(posts)} post page(s)")


if __name__ == "__main__":
    main()
