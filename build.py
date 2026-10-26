#!/usr/bin/env python3
"""Builds the static site into docs/, the folder GitHub Pages serves.

Sources:
  humanitys-checklist.html  the main page (content, styles and script in one file)
  questions.json            the long-tail questions, rendered to /questions/
  content/whitepaper.md     the whitepaper, rendered to /whitepaper/
  content/blog/*.md         blog posts, rendered to /blog/<file name>/
Outputs (in docs/):
  index.html, questions/, whitepaper/, blog/ (with feed.xml), sitemap.xml, robots.txt,
  llms.txt, llms-full.txt, the IndexNow key file, CNAME

Usage: python3 build.py                     build the site (standard library only)
       python3 build.py --indexnow-payload  print the IndexNow request body
"""
import datetime
import email.utils
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "docs"
CONTENT = ROOT / "content"
DOMAIN = "humanityschecklist.org"
SITE = f"https://{DOMAIN}"
REPO = "https://github.com/theguysaccount/humanityschecklist"
CALENDLY = "https://calendly.com/jackjay"
TELEGRAM = "https://t.me/web3wizard"
TODAY = datetime.date.today().isoformat()
# IndexNow (Bing, Yandex, Seznam, Naver, Yep): the key is public by design; engines
# fetch /<key>.txt to confirm we own the site before accepting a ping.
INDEXNOW_KEY = "129b58e44aa85f4829e64877c2dd7a76"
ORG = {"@type": "Organization", "name": "Humanity's Checklist", "url": SITE + "/"}
ITEM_NAMES = {
    "story": "Story", "coordination": "Coordination", "vision": "Vision",
    "attention": "Attention", "status": "Status", "gatekeepers": "Gatekeepers",
}

FAVICON = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='-3 -4.6 30 30'>"
    "<rect x='-3' y='-4.6' width='30' height='30' rx='7' fill='%23EDF1ED'/>"
    "<polygon points='12,0 18,10.39 6,10.39' fill='%23D23560'/>"
    "<polygon points='6,10.39 12,20.78 0,20.78' fill='%230F2621'/>"
    "<polygon points='18,10.39 24,20.78 12,20.78' fill='%230F2621'/></svg>"
)


def esc(text):
    return html.escape(text, quote=True)


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def nice_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


# ---------- Markdown (the small subset the content uses) ----------

def render_inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<em>\1</em>", text)
    return text


BLOCK_START = re.compile(r"(#{1,4}\s|>|\s*[-*]\s+|\s*\d+\.\s+|\|)")


def render_markdown(md):
    """Headings, paragraphs, lists, blockquotes, pipe tables and inline links/emphasis.
    Returns (html, [(id, text) for each h2])."""
    lines = md.strip().split("\n")
    out, toc, i = [], [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = re.match(r"(#{2,4})\s+(.*)", line)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            anchor = slugify(text)
            if level == 2:
                toc.append((anchor, text))
            out.append(f'<h{level} id="{anchor}">{render_inline(text)}</h{level}>')
            i += 1
            continue
        if line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].strip())
                i += 1
            out.append(f"<blockquote><p>{render_inline(' '.join(quote))}</p></blockquote>")
            continue
        for pattern, tag in ((r"\s*[-*]\s+", "ul"), (r"\s*\d+\.\s+", "ol")):
            if re.match(pattern, line):
                items = []
                while i < len(lines) and re.match(pattern, lines[i]):
                    items.append(re.sub(pattern, "", lines[i], count=1))
                    i += 1
                out.append(f"<{tag}>" + "".join(f"<li>{render_inline(x)}</li>" for x in items) + f"</{tag}>")
                break
        else:
            if line.startswith("|"):
                rows = []
                while i < len(lines) and lines[i].startswith("|"):
                    if not re.match(r"^\|[\s:|-]+\|$", lines[i].strip()):
                        rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                    i += 1
                head_row = "".join(f'<th scope="col">{render_inline(c)}</th>' for c in rows[0])
                body = "".join(
                    "<tr>" + "".join(
                        (f'<th scope="row">{render_inline(c)}</th>' if n == 0 else f"<td>{render_inline(c)}</td>")
                        for n, c in enumerate(r)) + "</tr>"
                    for r in rows[1:])
                out.append(f'<div class="table-wrap"><table><thead><tr>{head_row}</tr></thead><tbody>{body}</tbody></table></div>')
                continue
            para = []
            while i < len(lines) and lines[i].strip() and not BLOCK_START.match(lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{render_inline(' '.join(para))}</p>")
    return "\n".join(out), toc


def load_doc(path):
    """Reads a Markdown file with a simple `key: value` front matter block."""
    raw = path.read_text()
    meta = {}
    if raw.startswith("---"):
        _, front, raw = raw.split("---", 2)
        for line in front.strip().splitlines():
            key, _, value = line.partition(":")
            value = value.strip()
            if len(value) > 1 and value[0] == value[-1] == '"':
                value = value[1:-1]
            meta[key.strip()] = value
    for field in ("title", "description", "date"):
        if field not in meta:
            raise SystemExit(f"{path.relative_to(ROOT)} is missing '{field}' in its front matter")
    body_html, toc = render_markdown(raw)
    words = len(re.findall(r"\w+", raw))
    return {
        **meta,
        "slug": path.stem,
        "markdown": raw.strip(),
        "html": body_html,
        "toc": toc,
        "words": words,
        "minutes": max(1, round(words / 230)),
        "related": [s.strip() for s in meta.get("related", "").split(",") if s.strip()],
        "keywords": [k.strip() for k in meta.get("keywords", "").split(",") if k.strip()],
        "order": int(meta.get("order", 100)),
    }


def load_posts():
    folder = CONTENT / "blog"
    posts = [load_doc(p) for p in sorted(folder.glob("*.md"))] if folder.exists() else []
    posts.sort(key=lambda p: (p["date"], -p["order"]), reverse=True)
    return posts


# ---------- Shared page parts ----------

def head(title, description, path, json_ld, og_type="website", extra=""):
    url = SITE + path
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="{og_type}">
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
<link rel="alternate" type="application/rss+xml" title="Humanity's Checklist blog" href="{SITE}/blog/feed.xml">
{extra}<script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>
"""


def site_header(current=""):
    def link(href, label):
        here = ' aria-current="page"' if href == current else ""
        return f'<a href="{href}"{here}>{label}</a>'
    return f"""<header class="site-head">
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
      {link("/whitepaper/", "Whitepaper")}
      {link("/blog/", "Blog")}
      {link("/questions/", "Questions")}
      <a class="nav-join" href="/">The checklist</a>
    </nav>
  </div>
</header>
"""


def site_footer():
    return f"""<footer class="site-foot">
  <div class="wrap foot-row">
    <span>Humanity's Checklist &middot; Rev. 1</span>
    <nav class="foot-links" aria-label="More">
      <a href="/">The checklist</a>
      <a href="/whitepaper/">Whitepaper</a>
      <a href="/blog/">Blog</a>
      <a href="/questions/">Questions</a>
      <a href="{REPO}">Open source on GitHub</a>
      <a href="https://charitology.com">Grew out of Charitology, the study of charity</a>
    </nav>
  </div>
</footer>
"""


PAGE_CSS = """
<style>
.wrap.narrow { max-width: 880px; }
.head-nav a[aria-current="page"] { color: var(--ink); text-decoration: underline; text-decoration-color: var(--bloom); text-underline-offset: 5px; }
.foot-links { display: flex; flex-wrap: wrap; gap: 8px 20px; }
.foot-links a { color: var(--ink-2); text-underline-offset: 3px; }
.foot-links a:hover { color: var(--ink); }
.page-hero { padding-block: clamp(32px, 5vw, 64px) clamp(24px, 4vw, 40px); }
.page-hero .wrap { display: grid; gap: 16px; }
.meta-line { display: flex; flex-wrap: wrap; gap: 6px 18px; font: 500 .74rem/1.4 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--ink-2); }

/* Questions */
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
.q-links { display: flex; flex-wrap: wrap; gap: 6px 18px; }
.q-more { font: 600 .75rem/1.3 var(--font-mono); letter-spacing: .06em; text-transform: uppercase; color: var(--bloom-ink); }
.page-cta { padding-block: clamp(40px, 6vw, 72px); border-top: 1px solid var(--rule); }
.page-cta .wrap { display: grid; gap: 14px; }

/* Articles */
.article-body { padding-block: 0 clamp(48px, 7vw, 88px); }
.article-body .wrap { display: grid; gap: clamp(28px, 4vw, 44px); }
.toc { display: grid; gap: 10px; padding: 18px 20px; border: 1px solid var(--rule); border-radius: 8px; background: var(--card); max-width: 68ch; }
.toc ol { list-style: decimal; padding-left: 1.4em; display: grid; gap: 4px; columns: 1; }
.toc a { color: var(--ink); text-underline-offset: 3px; text-decoration-color: var(--rule); }
.toc a:hover { text-decoration-color: var(--bloom); }
.prose { display: grid; gap: 1.05em; max-width: 68ch; font-size: 1.15rem; line-height: 1.65; }
.prose h2 { font-family: var(--font-display); font-weight: 800; font-stretch: 74%; font-size: clamp(1.7rem, 1.25rem + 1.4vw, 2.3rem); line-height: 1.04; padding-top: .7em; text-wrap: balance; scroll-margin-top: 24px; }
.prose h3 { font-family: var(--font-display); font-weight: 750; font-stretch: 82%; font-size: 1.35rem; line-height: 1.15; padding-top: .35em; text-wrap: balance; }
.prose a { color: var(--ink); text-decoration-color: var(--bloom); text-decoration-thickness: 1.5px; text-underline-offset: 3px; }
.prose ul { list-style: disc; padding-left: 1.3em; display: grid; gap: .4em; }
.prose ol { list-style: decimal; padding-left: 1.4em; display: grid; gap: .4em; }
.prose blockquote { margin: 0; padding: 2px 0 2px 20px; border-left: 3px solid var(--bloom); font-style: italic; font-size: 1.25rem; line-height: 1.5; }
.prose code { font-family: var(--font-mono); font-size: .85em; background: var(--sym-2); padding: 1px 5px; border-radius: 4px; }
.table-wrap { overflow-x: auto; max-width: 100%; }
.prose table { border-collapse: collapse; width: 100%; min-width: 520px; font-size: 1rem; line-height: 1.45; }
.prose th, .prose td { text-align: left; vertical-align: top; padding: 10px 12px; border-bottom: 1px solid var(--rule); }
.prose thead th { font: 600 .7rem/1.3 var(--font-mono); letter-spacing: .1em; text-transform: uppercase; color: var(--ink-2); border-bottom: 1.5px solid var(--ink); }
.prose tbody th { font-weight: 600; }
.cta-box { display: grid; gap: 12px; padding: 22px; border: 1.5px solid var(--ink); border-radius: 8px; background: var(--card); max-width: 68ch; }
.cta-box p { color: var(--ink-2); }
.cite { display: grid; gap: 8px; max-width: 68ch; }
.cite p { font: 400 .9rem/1.5 var(--font-mono); color: var(--ink-2); padding: 14px 16px; background: var(--sym-2); border-radius: 6px; overflow-wrap: anywhere; }
.related { display: grid; gap: 12px; max-width: 68ch; }
.related ul { display: grid; gap: 8px; }
.related a { font-family: var(--font-display); font-weight: 700; font-stretch: 82%; font-size: 1.2rem; color: var(--ink); text-decoration-color: var(--bloom); text-underline-offset: 4px; }
.cta-box a:not(.btn) { color: var(--ink); text-decoration-color: var(--bloom); text-underline-offset: 3px; }
.all-posts { display: grid; gap: 12px; padding-top: 20px; border-top: 1px solid var(--rule); }
.all-posts ul { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px 32px; }
@media (min-width: 720px) { .all-posts ul { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.all-posts a { color: var(--ink-2); font-size: 1rem; line-height: 1.35; text-underline-offset: 3px; text-decoration-color: var(--rule); }
.all-posts a:hover { color: var(--ink); text-decoration-color: var(--bloom); }

/* Blog index */
.post-list { display: grid; gap: 30px; max-width: 74ch; }
.post-card { display: grid; gap: 8px; padding-top: 18px; border-top: 2px solid var(--ink); }
.post-card h2 { font-family: var(--font-display); font-weight: 800; font-stretch: 74%; font-size: clamp(1.6rem, 1.25rem + 1.2vw, 2.1rem); line-height: 1.04; text-wrap: balance; }
.post-card h2 a { color: inherit; text-decoration: none; }
.post-card h2 a:hover { text-decoration: underline; text-decoration-color: var(--bloom); text-underline-offset: 5px; }
.post-card p { color: var(--ink-2); }
.feature { display: grid; gap: 10px; padding: 22px; border: 1.5px solid var(--ink); border-radius: 8px; background: var(--card); max-width: 74ch; }
.feature h2 { font-family: var(--font-display); font-weight: 800; font-stretch: 74%; font-size: clamp(1.6rem, 1.25rem + 1.2vw, 2.1rem); line-height: 1.04; }
.feature h2 a { color: inherit; text-decoration-color: var(--bloom); text-underline-offset: 5px; }
.feature p { color: var(--ink-2); }
</style>
"""


def shell(page_head, title, description, path, json_ld, current, main_html, og_type="website", extra=""):
    return (head(title, description, path, json_ld, og_type, extra) + page_head + PAGE_CSS
            + "</head>\n<body>\n" + site_header(current) + main_html + site_footer() + "</body>\n</html>\n")


def write(path, text):
    target = OUT / path.strip("/")
    if path.endswith("/"):
        target.mkdir(parents=True, exist_ok=True)
        target = target / "index.html"
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def split_page(source):
    """Returns (head material up to </style>, body) from the page fragment."""
    cut = source.index("</style>") + len("</style>")
    top = source[:cut]
    top = re.sub(r"<title>.*?</title>\n?", "", top)
    top = re.sub(r'<meta name="claude:viewport-fit-sides"[^>]*>\n?', "", top)
    return top, source[cut:]


# ---------- Pages ----------

def build_index(page_head, page_body):
    description = (
        "Every world problem grows from a few sources. Humanity's Checklist names the six and the "
        "beachhead that flips each one, and asks: what if $5 million, spent systemically, was all it took?"
    )
    json_ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "@id": SITE + "/#website", "url": SITE + "/", "name": "Humanity's Checklist",
             "description": description, "inLanguage": "en", "publisher": ORG},
            {"@type": "WebPage", "url": SITE + "/",
             "name": "Humanity's Checklist: six things to fix so we can fix everything else",
             "isPartOf": {"@id": SITE + "/#website"},
             "about": ["Systemic change", "Effective altruism", "Root causes of world problems",
                       "Coordination problems", "Protopia", "Philanthropy"],
             "isBasedOn": "https://charitology.com"},
        ],
    }
    doc = head("Humanity's Checklist", description, "/", json_ld) + page_head
    doc += "\n</head>\n<body>" + page_body + "\n</body>\n</html>\n"
    write("/", doc)


def build_questions(page_head, groups, posts_by_slug):
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
    parts = ["""<main>
  <section class="page-hero" aria-labelledby="q-title">
    <div class="wrap">
      <p class="eyebrow">Questions</p>
      <h1 class="display-1" id="q-title">Fixing the world at the source</h1>
      <p class="lead">The questions people ask on the way to Humanity's Checklist, answered plainly. Every answer links back to the item on the checklist it belongs to.</p>
      <nav class="q-index" aria-label="Topics">
"""]
    for gi, g in enumerate(groups):
        parts.append(f'        <a href="#topic-{gi + 1}">{esc(g["title"])}</a>\n')
    parts.append("      </nav>\n    </div>\n  </section>\n")
    for gi, g in enumerate(groups):
        parts.append(f'  <section class="q-group" id="topic-{gi + 1}" aria-labelledby="topic-{gi + 1}-title">\n'
                     f'    <div class="wrap">\n      <h2 class="display-2" id="topic-{gi + 1}-title">{esc(g["title"])}</h2>\n'
                     '      <div class="q-list">\n')
        for i in g["items"]:
            links = []
            if i.get("read"):
                post = posts_by_slug.get(i["read"])
                if not post:
                    raise SystemExit(f"questions.json: '{i['id']}' reads unknown post '{i['read']}'")
                links.append(f'<a class="q-more" href="/blog/{post["slug"]}/">Read: {esc(post["title"])} &rarr;</a>')
            if i.get("item"):
                links.append(f'<a class="q-more" href="/#{i["item"]}">Open {ITEM_NAMES[i["item"]]} on the checklist &rarr;</a>')
            more = f'\n          <p class="q-links">{"".join(links)}</p>' if links else ""
            parts.append(f'        <article class="q-item" id="{i["id"]}">\n'
                         f'          <h3><a href="#{i["id"]}">{esc(i["q"])}</a></h3>\n'
                         f'          <p>{esc(i["a"])}</p>{more}\n'
                         '        </article>\n')
        parts.append("      </div>\n    </div>\n  </section>\n")
    parts.append(f"""  <section class="page-cta">
    <div class="wrap">
      <h2 class="display-2">Missing a question?</h2>
      <p class="section-lead">Add it. The site is open source: edit <code>questions.json</code> and open a pull request, or point your AI agent at the repository and it will find instructions in AGENTS.md.</p>
      <p><a class="btn" href="{REPO}">Contribute on GitHub</a></p>
    </div>
  </section>
</main>
""")
    write("/questions/", shell(page_head, "Questions | Humanity's Checklist", description, "/questions/",
                               json_ld, "/questions/", "".join(parts)))
    return all_items


def article_page(page_head, doc, path, kind, posts_by_slug):
    url = SITE + path
    json_ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting" if kind == "Blog" else "Article",
        "headline": doc["title"],
        "description": doc["description"],
        "url": url,
        "mainEntityOfPage": url,
        "datePublished": doc["date"],
        "dateModified": doc.get("updated", doc["date"]),
        "inLanguage": "en",
        "wordCount": doc["words"],
        "author": ORG,
        "publisher": ORG,
        "isPartOf": {"@id": SITE + "/#website"},
        "keywords": doc["keywords"],
    }
    if kind == "Whitepaper":
        json_ld["genre"] = "Whitepaper"
    toc = ""
    if doc.get("contents") == "yes" and doc["toc"]:
        numbering = re.compile(r"^\d+\.\s*")
        entries = "".join(f'<li><a href="#{a}">{render_inline(numbering.sub("", t))}</a></li>' for a, t in doc["toc"])
        toc = f'<nav class="toc" aria-labelledby="toc-title"><p class="mini-label" id="toc-title">Contents</p><ol>{entries}</ol></nav>\n'
    item = doc.get("item")
    if item:
        cta_link = f'<a class="btn" href="/#{item}">Open {ITEM_NAMES[item]} on the checklist</a>'
    else:
        cta_link = '<a class="btn" href="/">Open the checklist</a>'
    cta = f"""<aside class="cta-box" aria-label="Humanity's Checklist">
        <p class="mini-label">Humanity's Checklist</p>
        <p>Six sources sit upstream of every world problem: the story we tell, how we coordinate, what we can picture, what our feeds reward, what we admire and who gets to build. What if $5 million, spent on those, was all it took?</p>
        <p>{cta_link}</p>
        <p>Found this and it resonates? <a href="{CALENDLY}">Schedule a call</a> or message <a href="{TELEGRAM}">@web3wizard on Telegram</a>.</p>
      </aside>"""
    cite = ""
    if kind == "Whitepaper":
        cite = f"""<section class="cite" aria-labelledby="cite-title">
        <h2 class="mini-label" id="cite-title">Cite this</h2>
        <p>Humanity's Checklist ({doc["date"][:4]}). {esc(doc["title"])}. {url}</p>
      </section>"""
    related = [posts_by_slug[s] for s in doc["related"] if s in posts_by_slug]
    missing = [s for s in doc["related"] if s not in posts_by_slug]
    if missing:
        raise SystemExit(f"{doc['slug']}.md lists unknown related posts: {missing}")
    rel = ""
    if related or kind == "Blog":
        links = "".join(f'<li><a href="/blog/{p["slug"]}/">{esc(p["title"])}</a></li>' for p in related)
        if kind == "Blog":
            links += '<li><a href="/whitepaper/">Whitepaper: Fixing the world at the source</a></li>'
        rel = f'<nav class="related" aria-labelledby="rel-title"><h2 class="mini-label" id="rel-title">Keep reading</h2><ul>{links}</ul></nav>'
    # Every essay links to every other one.
    others = [p for p in posts_by_slug.values() if p["slug"] != doc["slug"]]
    every = "".join(f'<li><a href="/blog/{p["slug"]}/">{esc(p["title"])}</a></li>' for p in others)
    if kind == "Blog":
        every = '<li><a href="/whitepaper/">Whitepaper: Fixing the World at the Source</a></li>' + every
    rel += (f'\n      <nav class="all-posts" aria-labelledby="all-title"><h2 class="mini-label" id="all-title">All essays</h2>'
            f'<ul>{every}</ul><p><a href="/blog/">The blog</a> &middot; <a href="/questions/">Questions</a></p></nav>')
    main_html = f"""<main>
  <article>
    <header class="page-hero">
      <div class="wrap narrow">
        <p class="eyebrow">{kind}</p>
        <h1 class="display-1">{esc(doc["title"])}</h1>
        <p class="lead">{esc(doc["description"])}</p>
        <p class="meta-line"><span><time datetime="{doc["date"]}">{nice_date(doc["date"])}</time></span><span>{doc["minutes"]} min read</span><span>Humanity's Checklist</span></p>
      </div>
    </header>
    <div class="article-body">
      <div class="wrap narrow">
      {toc}<div class="prose">
{doc["html"]}
      </div>
      {cite}
      {cta}
      {rel}
      </div>
    </div>
  </article>
</main>
"""
    title = f'{doc["title"]} | Humanity\'s Checklist'
    extra = f'<meta property="article:published_time" content="{doc["date"]}">\n'
    write(path, shell(page_head, title, doc["description"], path, json_ld,
                      "/whitepaper/" if kind == "Whitepaper" else "/blog/", main_html, "article", extra))


def build_blog_index(page_head, posts, whitepaper):
    description = ("Long-form writing on fixing the world at the source: effective altruism, systemic change, "
                   "coordination problems, leverage points, protopia and the six items on Humanity's Checklist.")
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Blog",
        "url": SITE + "/blog/",
        "name": "Humanity's Checklist blog",
        "description": description,
        "isPartOf": {"@id": SITE + "/#website"},
        "publisher": ORG,
        "blogPost": [{"@type": "BlogPosting", "headline": p["title"], "url": f"{SITE}/blog/{p['slug']}/",
                      "datePublished": p["date"]} for p in posts],
    }
    cards = "".join(f"""
        <article class="post-card">
          <p class="meta-line"><time datetime="{p["date"]}">{nice_date(p["date"])}</time><span>{p["minutes"]} min read</span></p>
          <h2><a href="/blog/{p["slug"]}/">{esc(p["title"])}</a></h2>
          <p>{esc(p["description"])}</p>
        </article>""" for p in posts)
    main_html = f"""<main>
  <section class="page-hero" aria-labelledby="blog-title">
    <div class="wrap narrow">
      <p class="eyebrow">Blog</p>
      <h1 class="display-1" id="blog-title">Fixing the world at the source</h1>
      <p class="lead">Essays on the ideas behind Humanity's Checklist: why problems share sources, where to push, and what giving would look like if it aimed at causes.</p>
    </div>
  </section>
  <section class="article-body" aria-label="Posts">
    <div class="wrap narrow">
      <div class="feature">
        <p class="mini-label">Start here</p>
        <h2><a href="/whitepaper/">{esc(whitepaper["title"])}</a></h2>
        <p>{esc(whitepaper["description"])}</p>
      </div>
      <div class="post-list">{cards}
      </div>
    </div>
  </section>
</main>
"""
    write("/blog/", shell(page_head, "Blog | Humanity's Checklist", description, "/blog/", json_ld, "/blog/", main_html))


def build_feed(posts):
    items = "".join(f"""
    <item>
      <title>{esc(p["title"])}</title>
      <link>{SITE}/blog/{p["slug"]}/</link>
      <guid>{SITE}/blog/{p["slug"]}/</guid>
      <pubDate>{email.utils.format_datetime(datetime.datetime.fromisoformat(p["date"] + "T12:00:00+00:00"))}</pubDate>
      <description>{esc(p["description"])}</description>
    </item>""" for p in posts)
    (OUT / "blog" / "feed.xml").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Humanity's Checklist blog</title>
    <link>{SITE}/blog/</link>
    <description>Essays on fixing the world at the source.</description>
    <language>en</language>
    <atom:link href="{SITE}/blog/feed.xml" rel="self" type="application/rss+xml"/>{items}
  </channel>
</rss>
""")


def page_paths(posts):
    return ["/", "/whitepaper/", "/blog/"] + [f"/blog/{p['slug']}/" for p in posts] + ["/questions/"]


def build_meta_files(all_items, whitepaper, posts):
    (OUT / "CNAME").write_text(DOMAIN + "\n")
    (OUT / "robots.txt").write_text(
        "# Search engines and AI crawlers are welcome to read and cite everything here.\n"
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    dates = {f"/blog/{p['slug']}/": p.get("updated", p["date"]) for p in posts}
    dates["/whitepaper/"] = whitepaper.get("updated", whitepaper["date"])
    urls = "\n".join(f"  <url><loc>{SITE}{p}</loc><lastmod>{dates.get(p, TODAY)}</lastmod></url>"
                     for p in page_paths(posts))
    (OUT / "sitemap.xml").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>
""")
    (OUT / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY)
    questions = "\n".join(f"- [{i['q']}]({SITE}/questions/#{i['id']})" for i in all_items)
    post_lines = "\n".join(f"- [{p['title']}]({SITE}/blog/{p['slug']}/): {p['description']}" for p in posts)
    summary = f"""# Humanity's Checklist

> Every world problem grows from a few sources. Humanity's Checklist names six of them, pairs each with one buildable "beachhead" project, and asks: what if $5 million, spent systemically, was all it took? The only effective altruism is systemic.

The checklist, read from the top of a triangle down:

1. Story: rewrite the story humanity tells itself (beachhead: a new story of protopia).
2. Coordination: every problem is a coordination problem (beachhead: the Social Router, an automated LinkedIn for visions of the future).
3. Vision: let humanity preview its future (beachhead: the Vision Market, a market for visions of the future).
4. Attention: social media is the superorganism's nervous system (beachhead: Bloomscroll, a feed ranked for the value it adds).
5. Status: make giving the status symbol (beachhead: charity designer goods).
6. Gatekeepers: open the internet's gates (beachhead: the Co-Creator Portal).

Below them sit every world problem: climate change, war, poverty, hunger, disease, loneliness, polarization, misinformation and more.
"""
    (OUT / "llms.txt").write_text(f"""{summary}
## Pages

- [The checklist]({SITE}/): the triangle, a deep dive on each item, and the $5 million question
- [Whitepaper]({SITE}/whitepaper/): {whitepaper['description']}
- [Blog]({SITE}/blog/): essays on systemic change, effective altruism and each item
- [Questions]({SITE}/questions/): plain answers to {len(all_items)} questions about root causes, systemic change and charity
- [Full text for language models]({SITE}/llms-full.txt): the whitepaper, every post and every answer in one file

## Blog

{post_lines}

## Contact

- [Schedule a call]({CALENDLY}) if this resonates, or message [@web3wizard on Telegram]({TELEGRAM})

## Contribute

- [Source on GitHub]({REPO}): open source; pull requests welcome
- [AGENTS.md]({REPO}/blob/main/AGENTS.md): how an AI agent can propose changes
- [Charitology](https://charitology.com): the study of charity this project grew out of

## Questions

{questions}
""")
    full = [summary, f"\n---\n\n# {whitepaper['title']}\n\nSource: {SITE}/whitepaper/\n\n{whitepaper['markdown']}\n"]
    for p in posts:
        full.append(f"\n---\n\n# {p['title']}\n\nSource: {SITE}/blog/{p['slug']}/\n\n{p['markdown']}\n")
    full.append("\n---\n\n# Questions and answers\n\nSource: " + SITE + "/questions/\n\n" + "\n\n".join(
        f"## {i['q']}\n\n{i['a']}" for i in all_items) + "\n")
    (OUT / "llms-full.txt").write_text("".join(full))


def indexnow_payload():
    """The JSON body for https://api.indexnow.org/indexnow, listing every page."""
    return json.dumps({
        "host": DOMAIN,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt",
        "urlList": [SITE + p for p in page_paths(load_posts())] + [f"{SITE}/llms.txt", f"{SITE}/llms-full.txt"],
    })


def main():
    if "--indexnow-payload" in sys.argv:
        print(indexnow_payload())
        return
    source = (ROOT / "humanitys-checklist.html").read_text()
    groups = json.loads((ROOT / "questions.json").read_text())["groups"]
    ids = [i["id"] for g in groups for i in g["items"]]
    dupes = {x for x in ids if ids.count(x) > 1}
    if dupes:
        raise SystemExit(f"Duplicate question ids in questions.json: {sorted(dupes)}")
    whitepaper = load_doc(CONTENT / "whitepaper.md")
    posts = load_posts()
    posts_by_slug = {p["slug"]: p for p in posts}
    OUT.mkdir(exist_ok=True)
    page_head, page_body = split_page(source)
    build_index(page_head, page_body)
    all_items = build_questions(page_head, groups, posts_by_slug)
    article_page(page_head, whitepaper, "/whitepaper/", "Whitepaper", posts_by_slug)
    for p in posts:
        article_page(page_head, p, f"/blog/{p['slug']}/", "Blog", posts_by_slug)
    build_blog_index(page_head, posts, whitepaper)
    build_feed(posts)
    build_meta_files(all_items, whitepaper, posts)
    print(f"Built docs/: whitepaper, {len(posts)} posts, {len(all_items)} questions")


if __name__ == "__main__":
    main()
