#!/usr/bin/env python3
"""Builds the static site into docs/, the folder GitHub Pages serves.

Sources:
  humanitys-checklist.html  the main page (content, styles and script in one file)
  questions.json            the long-tail questions, rendered to /questions/
Outputs:
  docs/index.html, docs/questions/index.html, docs/sitemap.xml, docs/robots.txt,
  docs/llms.txt, docs/CNAME

Usage: python3 build.py   (standard library only)
"""
import datetime
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "docs"
DOMAIN = "humanityschecklist.org"
SITE = f"https://{DOMAIN}"
REPO = "https://github.com/theguysaccount/humanityschecklist"
TODAY = datetime.date.today().isoformat()

FAVICON = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='-3 -4.6 30 30'>"
    "<rect x='-3' y='-4.6' width='30' height='30' rx='7' fill='%23EDF1ED'/>"
    "<polygon points='12,0 18,10.39 6,10.39' fill='%23D23560'/>"
    "<polygon points='6,10.39 12,20.78 0,20.78' fill='%230F2621'/>"
    "<polygon points='18,10.39 24,20.78 12,20.78' fill='%230F2621'/></svg>"
)


def esc(text):
    return html.escape(text, quote=True)


def head(title, description, path, json_ld):
    url = SITE + path
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Humanity's Checklist">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="theme-color" content="#EDF1ED" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0B1613" media="(prefers-color-scheme: dark)">
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<link rel="alternate" type="text/plain" title="Summary for AI agents" href="{SITE}/llms.txt">
<script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>
"""


def split_page(source):
    """Returns (head material up to </style>, body) from the page fragment."""
    cut = source.index("</style>") + len("</style>")
    top = source[:cut]
    top = re.sub(r"<title>.*?</title>\n?", "", top)
    top = re.sub(r'<meta name="claude:viewport-fit-sides"[^>]*>\n?', "", top)
    return top, source[cut:]


def build_index(page_head, page_body, groups):
    description = (
        "Every world problem grows from a few sources. Humanity's Checklist names the six and the "
        "beachhead that flips each one, and asks: what if $5 million, spent systemically, was all it took?"
    )
    json_ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "@id": SITE + "/#website",
                "url": SITE + "/",
                "name": "Humanity's Checklist",
                "description": description,
                "inLanguage": "en",
            },
            {
                "@type": "WebPage",
                "url": SITE + "/",
                "name": "Humanity's Checklist: six things to fix so we can fix everything else",
                "isPartOf": {"@id": SITE + "/#website"},
                "about": ["Systemic change", "Effective altruism", "Root causes of world problems",
                          "Coordination problems", "Protopia", "Philanthropy"],
                "isBasedOn": "https://charitology.com",
            },
        ],
    }
    doc = head("Humanity's Checklist", description, "/", json_ld) + page_head
    doc += "\n</head>\n<body>" + page_body + "\n</body>\n</html>\n"
    (OUT / "index.html").write_text(doc)


QUESTIONS_CSS = """
<style>
.q-hero { padding-block: clamp(32px, 5vw, 64px) clamp(24px, 4vw, 40px); }
.q-hero .wrap { display: grid; gap: 16px; }
.q-index { display: flex; flex-wrap: wrap; gap: 8px; }
.q-index a {
  padding: 6px 12px; border-radius: 999px; background: var(--sym-2); color: var(--ink);
  font: 500 .8rem/1.2 var(--font-mono); text-decoration: none;
}
.q-index a:hover { background: var(--bloom-tint); }
.q-group { padding-block: clamp(28px, 4vw, 48px); border-top: 1px solid var(--rule); }
.q-group .wrap { display: grid; gap: 22px; }
.q-list { display: grid; gap: 26px; max-width: 72ch; }
.q-item { display: grid; gap: 8px; scroll-margin-top: 24px; }
.q-item h3 { font-family: var(--font-display); font-weight: 750; font-stretch: 80%; font-size: 1.45rem; line-height: 1.12; text-wrap: balance; }
.q-item h3 a { color: inherit; text-decoration: none; }
.q-item h3 a:hover { text-decoration: underline; text-decoration-color: var(--bloom); }
.q-item p { color: var(--ink-2); }
.q-more { font: 600 .75rem/1.3 var(--font-mono); letter-spacing: .06em; text-transform: uppercase; color: var(--bloom-ink); }
.q-cta { padding-block: clamp(40px, 6vw, 72px); border-top: 1px solid var(--rule); }
.q-cta .wrap { display: grid; gap: 14px; }
.foot-links { display: flex; flex-wrap: wrap; gap: 8px 20px; }
.foot-links a { color: var(--ink-2); }
</style>
"""


def build_questions(page_head, groups):
    all_items = [item for g in groups for item in g["items"]]
    description = (
        f"{len(all_items)} questions about fixing the world at the source: root causes of world problems, "
        "systemic change versus charity, effective altruism, coordination problems, protopia and more."
    )
    json_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "url": SITE + "/questions/",
        "name": "Questions about Humanity's Checklist",
        "isPartOf": {"@id": SITE + "/#website"},
        "mainEntity": [
            {"@type": "Question", "name": i["q"], "url": f"{SITE}/questions/#{i['id']}",
             "acceptedAnswer": {"@type": "Answer", "text": i["a"]}}
            for i in all_items
        ],
    }
    parts = [
        head("Questions | Humanity's Checklist", description, "/questions/", json_ld),
        page_head,
        QUESTIONS_CSS,
        "</head>\n<body>\n",
        f"""<header class="site-head">
  <div class="wrap head-row">
    <a class="brand" href="/">
      <svg class="brand-mark" viewBox="0 0 24 21" aria-hidden="true" focusable="false">
        <polygon class="bm-top" points="12,0 18,10.39 6,10.39"/>
        <polygon class="bm-side" points="6,10.39 12,20.78 0,20.78"/>
        <polygon class="bm-side" points="18,10.39 24,20.78 12,20.78"/>
      </svg>
      <span>Humanity's Checklist</span>
    </a>
    <nav class="head-nav" aria-label="Sections">
      <a href="/#list">The list</a>
      <a href="/#math">The math</a>
      <a class="nav-join" href="/#join">Join</a>
    </nav>
  </div>
</header>
<main>
  <section class="q-hero" aria-labelledby="q-title">
    <div class="wrap">
      <p class="eyebrow">Questions</p>
      <h1 class="display-1" id="q-title">Fixing the world at the source</h1>
      <p class="lead">The questions people ask on the way to Humanity's Checklist, answered plainly. Every answer links back to the item on the checklist it belongs to.</p>
      <nav class="q-index" aria-label="Topics">
""",
    ]
    for gi, g in enumerate(groups):
        parts.append(f'        <a href="#topic-{gi + 1}">{esc(g["title"])}</a>\n')
    parts.append("      </nav>\n    </div>\n  </section>\n")
    for gi, g in enumerate(groups):
        parts.append(f'  <section class="q-group" id="topic-{gi + 1}" aria-labelledby="topic-{gi + 1}-title">\n'
                     f'    <div class="wrap">\n      <h2 class="display-2" id="topic-{gi + 1}-title">{esc(g["title"])}</h2>\n'
                     '      <div class="q-list">\n')
        for i in g["items"]:
            more = ""
            if i.get("item"):
                more = f'\n          <a class="q-more" href="/#{i["item"]}">Open this item on the checklist &rarr;</a>'
            parts.append(f'        <article class="q-item" id="{i["id"]}">\n'
                         f'          <h3><a href="#{i["id"]}">{esc(i["q"])}</a></h3>\n'
                         f'          <p>{esc(i["a"])}</p>{more}\n'
                         '        </article>\n')
        parts.append("      </div>\n    </div>\n  </section>\n")
    parts.append(f"""  <section class="q-cta">
    <div class="wrap">
      <h2 class="display-2">Missing a question?</h2>
      <p class="section-lead">Add it. The site is open source: edit <code>questions.json</code> and open a pull request, or point your AI agent at the repository and it will find instructions in AGENTS.md.</p>
      <p><a class="btn" href="{REPO}">Contribute on GitHub</a></p>
    </div>
  </section>
</main>
<footer class="site-foot">
  <div class="wrap foot-row">
    <span>Humanity's Checklist &middot; Rev. 1</span>
    <nav class="foot-links" aria-label="More">
      <a href="/">The checklist</a>
      <a href="{REPO}">Open source on GitHub</a>
      <a href="https://charitology.com">Grew out of Charitology, the study of charity</a>
    </nav>
  </div>
</footer>
</body>
</html>
""")
    target = OUT / "questions"
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text("".join(parts))
    return all_items


def build_meta_files(all_items):
    (OUT / "CNAME").write_text(DOMAIN + "\n")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    (OUT / "sitemap.xml").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{SITE}/</loc><lastmod>{TODAY}</lastmod></url>
  <url><loc>{SITE}/questions/</loc><lastmod>{TODAY}</lastmod></url>
</urlset>
""")
    questions = "\n".join(f"- [{i['q']}]({SITE}/questions/#{i['id']})" for i in all_items)
    (OUT / "llms.txt").write_text(f"""# Humanity's Checklist

> Every world problem grows from a few sources. Humanity's Checklist names six of them, pairs each with one buildable "beachhead" project, and asks: what if $5 million, spent systemically, was all it took? The only effective altruism is systemic.

The checklist, read from the top of a triangle down:

1. Story: rewrite the story humanity tells itself (beachhead: a new story of protopia).
2. Coordination: every problem is a coordination problem (beachhead: the Social Router, an automated LinkedIn for visions of the future).
3. Vision: let humanity preview its future (beachhead: the Vision Market, a market for visions of the future).
4. Attention: social media is the superorganism's nervous system (beachhead: Bloomscroll, a feed ranked for the value it adds).
5. Status: make giving the status symbol (beachhead: charity designer goods).
6. Gatekeepers: open the internet's gates (beachhead: the Co-Creator Portal).

Below them sit every world problem: climate change, war, poverty, hunger, disease, loneliness, polarization, misinformation and more.

## Pages

- [The checklist]({SITE}/): the triangle, a deep dive on each item, and the $5 million question
- [Questions]({SITE}/questions/): plain answers to {len(all_items)} questions about root causes, systemic change and charity

## Contribute

- [Source on GitHub]({REPO}): open source; pull requests welcome
- [AGENTS.md]({REPO}/blob/main/AGENTS.md): how an AI agent can propose changes
- [Charitology](https://charitology.com): the study of charity this project grew out of

## Questions

{questions}
""")


def main():
    source = (ROOT / "humanitys-checklist.html").read_text()
    groups = json.loads((ROOT / "questions.json").read_text())["groups"]
    ids = [i["id"] for g in groups for i in g["items"]]
    dupes = {x for x in ids if ids.count(x) > 1}
    if dupes:
        raise SystemExit(f"Duplicate question ids in questions.json: {sorted(dupes)}")
    OUT.mkdir(exist_ok=True)
    page_head, page_body = split_page(source)
    build_index(page_head, page_body, groups)
    all_items = build_questions(page_head, groups)
    build_meta_files(all_items)
    print(f"Built docs/ with {len(all_items)} questions")


if __name__ == "__main__":
    main()
