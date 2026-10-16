#!/usr/bin/env python3
"""Build the TECAT website from src/ and public/ into _site/.

Standard library only. Run: python3 build.py

Every internal link is written as {{ root }}path in templates and resolved to a
relative path per page, so the same output works on github.io, a custom domain,
and a local preview server.
"""
import html
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

# Launch switch. False is staging: noindex, no sitemap, no redirects, [VERIFY]
# markers allowed. Set True only when Ron authorizes cutover; the build then
# fails while any [VERIFY] marker remains.
LAUNCH = False
PROD_URL = "https://tecatperformance.com/"
STAGING_URL = "https://ronrath.github.io/tecat-website/"
BASE_URL = PROD_URL if LAUNCH else STAGING_URL
SITE = "TECAT Performance Systems"

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DATA = Path(os.environ.get("TECAT_DATA", SRC / "data"))
PUBLIC = ROOT / "public"
OUT = ROOT / "_site"
R = "{{ root }}"

# Old WordPress URLs and their new homes. Written as redirect pages at launch.
REDIRECTS = {
    "wiser-4000-wireless-sensor-system/": "products/tecat-468-single/",
    "wiser-data/": "products/tecat-468-single/",
    "wiser-4000-wireless-sensor-system/wiser-oem-platform-2/": "products/tecat-oem/",
    "wiser-tc-platform/": "products/tecat-tc2-k/",
    "wiser-8000-wireless-sensor-system/": "products/tecat-468-dual/",
    "transporation/": "applications/transportation/",
    "industrial/": "applications/industrial/",
    "motorsports/": "applications/motorsports/",
    "energy/": "applications/energy/",
    "ivhm/": "applications/ivhm/",
    "press-releases/": "news/",
    "find-manufacturers-representative/": "contact/representatives/",
    "blog/": "news/",
    "events/": "news/",
    "whitepapers-2/": "news/",
}

APP_FALLBACK = [
    {"slug": "transportation", "name": "Transportation"},
    {"slug": "motorsports", "name": "Motorsports"},
    {"slug": "energy", "name": "Energy"},
    {"slug": "industrial", "name": "Industrial"},
    {"slug": "ivhm", "name": "IVHM"},
]

KIND_ORDER = {"datasheet": 0, "brochure": 1, "app-note": 2, "case-study": 3, "press": 4}

SOCIAL_LABELS = {"linkedin": "LinkedIn", "youtube": "YouTube", "facebook": "Facebook", "twitter": "X (Twitter)"}


def load(name, default):
    path = DATA / f"{name}.json"
    if not path.exists():
        print(f"  note: {name}.json not found, using empty data")
        return default
    return json.loads(path.read_text())


PRODUCTS = load("products", [])
APPS = load("applications", []) or APP_FALLBACK
IMAGES = load("images", {})
DOWNLOADS = load("downloads", [])
NEWS = load("news", [])
TESTIMONIALS = load("testimonials", [])
REPS = load("reps", {"reps": []})
CUSTOMERS = load("customers", {"customers": []})
COMPANY = {
    "name": "TECAT Performance Systems, LLC",
    "address": ["775 Technology Drive, Suite 200", "Ann Arbor, Michigan 48108"],
    "phone": "248.615.9862",
    "email": "sales@tecatperformance.com",
    "sales_contact": "Don Keating",
    "social": {},
    "history": [],
    "founder": "",
    **load("company", {}),
}

PAGES = []  # (path, verify_count)


# ---------------------------------------------------------------- helpers

def mark_verify(text):
    return text.replace("[VERIFY]", '<mark class="verify">VERIFY</mark>')


def e(text):
    """Escape data for HTML text and show [VERIFY] as a visible staging marker."""
    return mark_verify(html.escape(str(text), quote=True))


def attr(text):
    return html.escape(str(text), quote=True)


def read(rel):
    return (SRC / rel).read_text()


def fill(template, **ctx):
    def sub(m):
        key = m.group(1)
        if key == "root":
            return m.group(0)
        if key not in ctx:
            raise KeyError(f"template needs {{{{ {key} }}}}")
        return str(ctx[key])
    return re.sub(r"\{\{\s*([a-z0-9_]+)\s*\}\}", sub, template)


def comp(_component, **ctx):
    return fill(read(f"components/{_component}.html"), **ctx)


def li(items):
    return "".join(f"<li>{e(x)}</li>" for x in items)


def section(title, inner, alt=False):
    return f'<section class="section{" alt" if alt else ""}"><div class="container"><h2>{e(title)}</h2>{inner}</div></section>'


def short(text, limit=158):
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return (cut[: cut.rfind(". ") + 1] if ". " in cut else cut[: cut.rfind(" ")]).strip()


def fmt_date(iso):
    """YYYY, YYYY-MM, or YYYY-MM-DD to a readable date."""
    parts = iso.split("-")
    if len(parts) == 1:
        return iso
    if len(parts) == 2:
        return f"{date(int(parts[0]), int(parts[1]), 1).strftime('%B')} {parts[0]}"
    d = date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def img(slot, cls="", eager=False, sizes="(min-width: 960px) 50vw, 100vw"):
    im = IMAGES.get(slot)
    if not im:
        return f'<div class="img-missing {cls}">{e("[VERIFY] photo: " + slot)}</div>'
    width = im["width"]
    if im.get("src_sm") and width > 800:
        srcset = f' srcset="{R}{im["src_sm"]} 800w, {R}{im["src"]} {width}w" sizes="{sizes}"'
    else:
        srcset = ""
    loading = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (f'<img class="{cls}" src="{R}{im["src"]}"{srcset} width="{width}" height="{im["height"]}" '
            f'alt="{attr(im.get("alt", ""))}" {loading} decoding="async">')


def logo_html():
    logo = IMAGES.get("logo")
    if not logo:
        return '<span class="logo-text">TECAT Performance Systems</span>'
    srcset = f' srcset="{R}{logo["src"]} 1x, {R}{logo["src_2x"]} 2x"' if logo.get("src_2x") else ""
    return (f'<img src="{R}{logo["src"]}"{srcset} width="{logo["width"]}" height="{logo["height"]}" '
            f'alt="TECAT Performance Systems home">')


def product_url(p):
    return f'{R}products/{p["slug"]}/'


def app_url(a):
    return f'{R}applications/{a["slug"]}/'


def downloads_for(key, slug, kinds=None):
    return [d for d in DOWNLOADS if slug in d.get(key, []) and (not kinds or d.get("kind") in kinds)]


# ---------------------------------------------------------------- components

def key_specs(p, limit=None):
    items = p.get("key_specs", [])
    items = items[:limit] if limit else items
    if not items:
        return ""
    return '<dl class="keyspecs">' + "".join(
        f'<div class="keyspec"><dt>{e(k["label"])}</dt><dd>{e(k["value"])}</dd></div>' for k in items) + "</dl>"


def product_card(p):
    return comp("product-card", href=product_url(p), name=e(p["name"]), positioning=e(p.get("positioning", "")),
                specs=key_specs(p, 2),
                image=img(f'product-{p["slug"]}-1', "card-img", sizes="(min-width: 1200px) 25vw, (min-width: 640px) 50vw, 100vw"))


def app_tile(a):
    return comp("app-tile", href=app_url(a), name=e(a["name"]), line=e(a.get("tagline", "")),
                image=img(f'app-{a["slug"]}', "tile-img", sizes="(min-width: 960px) 33vw, (min-width: 640px) 50vw, 100vw"))


def testimonial(t):
    cite = ", ".join(e(x) for x in (t.get("name"), t.get("title"), t.get("organization")) if x)
    return comp("testimonial", quote=e(t["quote"]), cite=cite)


def testimonials(arg):
    if arg == "home":
        items = TESTIMONIALS[:2]
    else:
        items = [t for t in TESTIMONIALS if arg in t.get("applications", [])][:2]
    return "".join(testimonial(t) for t in items)


def download_item(d):
    meta = "PDF" + (f', {d["size"]}' if d.get("size") else "")
    return comp("download-item", href=R + d["file"], title=e(d["title"]), meta=e(meta),
                description=e(d.get("description", "")))


def download_list(items):
    return '<ul class="download-list">' + "".join(download_item(d) for d in items) + "</ul>"


CTAS = {
    "quote": ("Ready to measure?",
              "Tell us about the part and what you need to measure, and we'll follow up with a recommendation and a quote.",
              ("Request a Quote", "contact/?topic=quote"), ("Find a representative", "contact/representatives/")),
    "engineer": ("Talk to an engineer",
                 "Describe the part, how it moves, and what you need to measure. We'll tell you whether a TECAT system fits.",
                 ("Talk to an Engineer", "contact/?topic=engineer"), ("See all products", "products/")),
}


def cta(kind, text=None, product=None):
    heading, default_text, (p_label, p_href), (s_label, s_href) = CTAS[kind]
    if product:
        p_href += f"&amp;product={product}"
    return comp("cta-block", heading=e(heading), text=e(text or default_text), primary_label=e(p_label),
                primary_href=R + p_href, secondary_label=e(s_label), secondary_href=R + s_href)


def comparison_table():
    if not PRODUCTS:
        return f'<p>{e("[VERIFY] products.json missing")}</p>'
    rows = list(PRODUCTS[0].get("comparison", {}).keys())
    head = "".join(f'<th scope="col"><a href="{product_url(p)}">{e(p["name"])}</a></th>' for p in PRODUCTS)
    body = ""
    for r in rows:
        cells = "".join(f'<td>{e(p.get("comparison", {}).get(r) or "Contact us")}</td>' for p in PRODUCTS)
        body += f'<tr><th scope="row">{e(r)}</th>{cells}</tr>'
    return (f'<div class="table-wrap"><table class="compare"><thead><tr><th scope="col">System</th>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def options_section(p):
    options = p.get("options", [])
    if not options:
        return ""
    rows = "".join(f'<tr><th scope="row">{e(o["name"])}</th><td><ul class="option-list">{li(o["choices"])}</ul></td></tr>'
                   for o in options)
    note = f'<p class="verify-note">{e(p["options_note"])}</p>' if p.get("options_note") else ""
    return section("Configurations", f'<div class="table-wrap"><table class="specs options"><tbody>{rows}</tbody></table></div>{note}')


def spec_table(p):
    groups = p.get("specs", [])
    if not groups:
        return f'<p>{e("[VERIFY] Specifications pending.")}</p>'
    body = ""
    for g in groups:
        body += f'<tbody><tr class="group"><th colspan="2" scope="colgroup">{e(g["group"])}</th></tr>'
        body += "".join(f'<tr><th scope="row">{e(r[0])}</th><td>{e(r[1])}</td></tr>' for r in g.get("rows", []))
        body += "</tbody>"
    return f'<div class="table-wrap"><table class="specs">{body}</table></div>'


def news_list():
    if not NEWS:
        return f'<p>{e("[VERIFY] news.json missing")}</p>'
    local = {d.get("date"): d for d in DOWNLOADS if d.get("kind") == "press"}
    years = {}
    for item in sorted(NEWS, key=lambda x: x["date"], reverse=True):
        years.setdefault(item["date"][:4], []).append(item)
    out = ""
    for year, items in years.items():
        rows = ""
        for it in items:
            kind = it.get("type", "Press release")
            d = local.get(it["date"]) if kind == "Press release" else None
            link = ""
            if d:
                link = f'<a class="text-link" href="{R}{d["file"]}">Press release PDF<span class="visually-hidden">: {e(it["headline"])}</span></a>'
            elif it.get("pdf"):
                link = f'<a class="text-link" href="{attr(it["pdf"])}">Press release PDF</a> {e("[VERIFY] file still on the old site")}'
            elif it.get("link"):
                link = f'<a class="text-link" href="{attr(it["link"]["href"])}">{e(it["link"]["label"])}</a>'
            rows += (f'<li class="press-item"><p class="news-meta"><span class="news-label">{e(kind)}</span>'
                     f'<time datetime="{it["date"]}">{e(fmt_date(it["date"]))}</time></p>'
                     f'<h3>{e(it["headline"])}</h3><p>{e(it.get("summary", ""))}</p>{link}</li>')
        out += f'<section class="press-year" aria-labelledby="y{year}"><h2 id="y{year}">{year}</h2><ul class="press-list">{rows}</ul></section>'
    return out


def downloads_block():
    groups = [("Brochures and data sheets", {"brochure", "datasheet"}), ("Application notes", {"app-note"}),
              ("Case studies", {"case-study"})]
    out = ""
    for title, kinds in groups:
        items = [d for d in DOWNLOADS if d.get("kind") in kinds and not d.get("legacy")]
        if items:
            out += f'<section class="download-group"><h2>{title}</h2>{download_list(items)}</section>'
    legacy = [d for d in DOWNLOADS if d.get("legacy")]
    if legacy:
        out += ('<section class="download-group"><h2>Earlier WISER product literature</h2>'
                '<p>These documents describe products under their earlier WISER names.</p>' + download_list(legacy) + "</section>")
    return out or f'<p>{e("[VERIFY] downloads.json missing")}</p>'


def reps_table():
    reps = REPS.get("reps", [])
    note = ""
    if REPS.get("verify"):
        note = f'<p class="verify-note">{e("[VERIFY] D9: this list comes from the October 2017 rep matrix. Don to confirm current firms.")}</p>'
    if not reps:
        return note + f'<p>{e("[VERIFY] reps.json missing")}</p>'
    firms = {}
    for r in reps:
        firms.setdefault(r.get("firm", ""), []).append(r)
    cards = ""
    for firm, rows in firms.items():
        label = "TECAT direct sales" if firm.startswith("TECAT") else firm
        web = rows[0].get("website", "")
        site = ""
        if web:
            href = web if web.startswith("http") else "https://" + web
            shown = re.sub(r"^https?://(www\.)?", "", web).rstrip("/")
            site = f'<p><a class="text-link" href="{attr(href)}">{e(shown)}</a></p>'
        items = ""
        for r in rows:
            m = re.match(r"^(.*?)\s*\((.*)\)\s*$", r.get("territory", ""))
            state, detail = (m.group(1), m.group(2)) if m else (r.get("territory", "") or "Territory not listed", "")
            contact = f'<span class="rep-contact">{e(r["contact"])}</span>' if r.get("contact") else ""
            reach = " ".join(x for x in (
                f'<a href="tel:{re.sub(r"[^0-9+]", "", r["phone"])}">{e(r["phone"])}</a>' if r.get("phone") else "",
                f'<a href="mailto:{attr(r["email"])}">{e(r["email"])}</a>' if r.get("email") else "") if x)
            more = f'<details><summary>Coverage detail</summary><p>{e(detail)}</p></details>' if detail else ""
            items += f'<li><span class="rep-state">{e(state)}</span>{contact}{reach}{more}</li>'
        cards += (f'<article class="card rep-card"><div class="card-body"><h2>{e(label)}</h2>{site}'
                  f'<ul class="rep-list">{items}</ul></div></article>')
    return note + f'<div class="grid cards-2 reps-grid">{cards}</div>'


def timeline(style):
    items = COMPANY.get("history", [])
    if not items:
        return f'<p>{e("[VERIFY] company history missing")}</p>'
    if style == "compact":
        return '<ol class="timeline compact">' + "".join(
            f'<li><span class="year">{e(h["year"])}</span><span>{e(h["title"])}</span></li>' for h in items) + "</ol>"
    return '<ol class="timeline full">' + "".join(
        f'<li><span class="year">{e(h["year"])}</span><div><h3>{e(h["title"])}{" " + e("[VERIFY]") if h.get("verify") else ""}</h3>'
        f'<p>{e(h.get("body", ""))}</p></div></li>'
        for h in items) + "</ol>"


def featured_case_study():
    studies = [d for d in DOWNLOADS if d.get("kind") == "case-study"]
    if not studies:
        return ""
    d = studies[0]
    return (f'<article class="card feature-card"><div class="card-body"><p class="eyebrow">Case study</p>'
            f'<h3>{e(d["title"])}</h3><p>{e(d.get("description", ""))}</p>'
            f'<a class="text-link" href="{R}{d["file"]}">Download the case study (PDF{", " + e(d["size"]) if d.get("size") else ""})</a></div></article>')


def logo_bar():
    cleared = [c for c in CUSTOMERS.get("customers", []) if c.get("logo_permission") is True and c.get("logo")]
    if not cleared:
        return ""
    return '<ul class="logo-bar" aria-label="Customers">' + "".join(
        f'<li><img src="{R}{c["logo"]}" alt="{attr(c["name"])}" loading="lazy"></li>' for c in cleared) + "</ul>"


def address_block():
    lines = "<br>".join(e(x) for x in COMPANY["address"])
    query = quote_plus(" ".join(COMPANY["address"]))
    return (f'<address>{e(COMPANY["name"])}<br>{lines}</address>'
            f'<p><a class="text-link" href="https://www.google.com/maps/search/?api=1&amp;query={query}">Open in Maps</a></p>')


def contact_form():
    options = "".join(f'<option value="{p["slug"]}">{e(p["name"])}</option>' for p in PRODUCTS)
    return comp("contact-form", email=attr(COMPANY["email"]), product_options=options)


BLOCKS = {
    "hero_image": lambda arg: img("hero-tecat-kit", "hero-img", eager=True),
    "image": lambda arg: img(arg),
    "product_cards": lambda arg: '<div class="grid cards-4">' + "".join(product_card(p) for p in PRODUCTS) + "</div>",
    "app_tiles": lambda arg: '<div class="grid cards-3">' + "".join(app_tile(a) for a in APPS) + "</div>",
    "architecture": lambda arg: comp("architecture"),
    "comparison": lambda arg: comparison_table(),
    "downloads": lambda arg: downloads_block(),
    "news": lambda arg: news_list(),
    "reps": lambda arg: reps_table(),
    "timeline": timeline,
    "testimonials": testimonials,
    "featured_case_study": lambda arg: featured_case_study(),
    "logo_bar": lambda arg: logo_bar(),
    "cta": lambda arg: cta(arg),
    "cta_band": lambda arg: comp("cta-band"),
    "contact_form": lambda arg: contact_form(),
    "address": lambda arg: address_block(),
    "company": lambda arg: e(COMPANY.get(arg, "")),
    "founder": lambda arg: e(COMPANY.get("founder", "")) or e("[VERIFY] founder narrative missing"),
    "tel": lambda arg: "+1" + re.sub(r"[^0-9]", "", COMPANY["phone"]),
}


def expand(text):
    def sub(m):
        name, arg = m.group(1), m.group(2)
        if name not in BLOCKS:
            raise KeyError(f"unknown block: {name}")
        return BLOCKS[name](arg)
    return re.sub(r"\{\{\s*block:([a-z_]+)(?::([a-z0-9_-]+))?\s*\}\}", sub, text)


# ---------------------------------------------------------------- pages

def header(active):
    def cur(key):
        return ' aria-current="page"' if active == key else ""
    products_menu = "".join(f'<li><a href="{product_url(p)}">{e(p["name"])}</a></li>' for p in PRODUCTS)
    apps_menu = "".join(f'<li><a href="{app_url(a)}">{e(a["name"])}</a></li>' for a in APPS)
    return comp("header", logo=logo_html(), products_menu=products_menu, apps_menu=apps_menu,
                cur_products=cur("products"), cur_applications=cur("applications"), cur_resources=cur("resources"),
                cur_news=cur("news"), cur_about=cur("about"), cur_contact=cur("contact"))


def footer():
    social = "".join(f'<li><a href="{attr(url)}">{label}</a></li>'
                     for key, label in SOCIAL_LABELS.items() if (url := COMPANY.get("social", {}).get(key)))
    return comp("footer", logo=logo_html(),
                products_links="".join(f'<li><a href="{product_url(p)}">{e(p["name"])}</a></li>' for p in PRODUCTS),
                apps_links="".join(f'<li><a href="{app_url(a)}">{e(a["name"])}</a></li>' for a in APPS),
                address="<br>".join(e(x) for x in COMPANY["address"]), phone=e(COMPANY["phone"]),
                phone_href=BLOCKS["tel"](None), email=attr(COMPANY["email"]), social=social,
                year=date.today().year, company=e(COMPANY["name"]))


def org_jsonld():
    data = {
        "@context": "https://schema.org", "@type": "Organization", "name": COMPANY["name"], "url": PROD_URL,
        "telephone": COMPANY["phone"], "email": COMPANY["email"],
        "address": {"@type": "PostalAddress", "streetAddress": COMPANY["address"][0], "addressLocality": "Ann Arbor",
                    "addressRegion": "MI", "postalCode": "48108", "addressCountry": "US"},
        "sameAs": list(COMPANY.get("social", {}).values()),
    }
    if "logo" in IMAGES:
        data["logo"] = BASE_URL + IMAGES["logo"]["src"]
    return f'<script type="application/ld+json">{json.dumps(data)}</script>'


def write_page(path, title, description, content, active="", crumbs=(), exact_title=False, jsonld=""):
    depth = path.count("/")
    root = BASE_URL if path == "404.html" else ("../" * depth or "./")
    crumb_html = ""
    if crumbs:
        items = f'<li><a href="{R}">Home</a></li>'
        for i, (label, href) in enumerate(crumbs):
            last = i == len(crumbs) - 1
            items += f'<li aria-current="page">{e(label)}</li>' if last else f'<li><a href="{R}{href}">{e(label)}</a></li>'
        crumb_html = comp("breadcrumb", items=items)
    hero = IMAGES.get("hero-tecat-kit")
    page = fill(
        read("layouts/base.html"),
        title=attr(title if exact_title else f"{title} | {SITE}"),
        description=attr(description),
        robots="" if LAUNCH else '<meta name="robots" content="noindex, nofollow">',
        canonical=f'<link rel="canonical" href="{PROD_URL}{path}">' if LAUNCH and path != "404.html" else "",
        og_image=BASE_URL + hero["src"] if hero else "",
        jsonld=jsonld, header=header(active), breadcrumb=crumb_html, content=content, footer=footer(),
    )
    page = re.sub(r"\{\{\s*root\s*\}\}", root, page)
    target = OUT / path if path.endswith(".html") else OUT / path / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page)
    PAGES.append((path or "(home)", page.count('class="verify"')))


def build_static_pages():
    pages_dir = SRC / "pages"
    for src in sorted(pages_dir.rglob("*.html")):
        rel = src.relative_to(pages_dir).as_posix()
        text = src.read_text()
        m = re.match(r"\s*<!--\s*(\{.*?\})\s*-->", text, re.S)
        meta = json.loads(m.group(1)) if m else {}
        body = expand(mark_verify(text[m.end():] if m else text))
        if rel == "index.html":
            path = ""
        elif rel == "404.html":
            path = "404.html"
        else:
            path = rel[: -len("index.html")]
        write_page(path, meta.get("title", SITE), meta.get("description", ""), body, active=meta.get("nav", ""),
                   crumbs=[tuple(c) for c in meta.get("crumbs", [])], exact_title=meta.get("exact_title", False),
                   jsonld=org_jsonld() if path == "" else "")


def build_product_pages():
    layout = read("layouts/product.html")
    for p in PRODUCTS:
        slug = p["slug"]
        sheets = [d for d in downloads_for("products", slug) if d.get("primary")]
        href = f'{R}{sheets[0]["file"]}' if sheets else f"{R}contact/?topic=datasheet&amp;product={slug}"
        datasheet = f'<a class="btn btn-primary" href="{href}">Download Datasheet</a>'
        slots = [s for s in (f"product-{slug}-{i}" for i in (1, 2, 3)) if s in IMAGES]
        gallery = img(slots[0] if slots else f"product-{slug}-1", "gallery-main", eager=True)
        if len(slots) > 1:
            gallery += '<div class="gallery-thumbs">' + "".join(
                img(s, "gallery-thumb", sizes="(min-width: 960px) 25vw, 50vw") for s in slots[1:]) + "</div>"
        dls = sorted(downloads_for("products", slug), key=lambda d: KIND_ORDER.get(d.get("kind"), 9))
        related =[a for a in APPS if a["slug"] in p.get("applications", [])]
        content = expand(fill(
            layout, slug=slug, name=e(p["name"]), category=e(p.get("category", "")),
            positioning=e(p.get("positioning", "")), key_specs=key_specs(p), datasheet_button=datasheet,
            gallery=gallery, summary=e(p.get("summary", "")), measures=li(p.get("measures", [])),
            features=li(p.get("features", [])), spec_table=spec_table(p), options_section=options_section(p),
            spec_note=f'<p class="verify-note">{e(p["spec_note"])}</p>' if p.get("spec_note") else "",
            downloads_section=section("Downloads", download_list(dls)) if dls else "",
            related_section=section("Where it's used", '<div class="grid cards-3">' + "".join(app_tile(a) for a in related) + "</div>", alt=True) if related else "",
            cta=cta("quote", product=slug),
        ))
        write_page(f"products/{slug}/", p["name"], short(p.get("summary") or p.get("positioning", "")), content,
                   active="products", crumbs=[("Products", "products/"), (p["name"], f"products/{slug}/")])


def build_application_pages():
    layout = read("layouts/application.html")
    for a in APPS:
        slug = a["slug"]
        questions = a.get("questions", [])
        question_html = ""
        if questions:
            quotes = "".join(f'<blockquote class="voice"><p>{e(q)}</p></blockquote>' for q in questions[:2])
            question_html = f'<section class="section problem"><div class="container narrow">{quotes}</div></section>'
        proofs = "".join(comp("proof-card", title=e(pp["title"]), body=e(pp["body"]) + (
            f' <a class="text-link" href="{attr(pp["link"]["href"])}">{e(pp["link"]["label"])}</a>' if pp.get("link") else ""))
            for pp in a.get("proof_points", []))
        components = a.get("components", [])
        quotes = testimonials(slug)
        products = [p for p in PRODUCTS if slug in p.get("applications", [])]
        dls = downloads_for("applications", slug, {"app-note", "case-study"})
        content = expand(fill(
            layout, name=e(a["name"]), tagline=e(a.get("tagline", "")),
            image=img(f"app-{slug}", "banner-img", eager=True), questions=question_html,
            intro=e(a.get("intro", "") or "[VERIFY] intro pending"),
            proof_section=section("Examples from the field", f'<div class="grid cards-2">{proofs}</div>', alt=True) if proofs else "",
            components_section=section("Components we instrument", f'<ul class="chip-grid">{li(components)}</ul>') if components else "",
            testimonials_section=section("From customers", f'<div class="grid cards-2">{quotes}</div>', alt=True) if quotes else "",
            products_section=section("Systems for this work", '<div class="grid cards-4">' + "".join(product_card(p) for p in products) + "</div>") if products else "",
            downloads_section=section("Application notes and case studies", download_list(dls), alt=True) if dls else "",
            cta=cta("engineer", text=a.get("cta") or None),
        ))
        write_page(f"applications/{slug}/", a["name"], short(a.get("intro", "") or a["name"]), content,
                   active="applications", crumbs=[("Applications", "applications/"), (a["name"], f"applications/{slug}/")])


def build_extras():
    if LAUNCH:
        (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {PROD_URL}sitemap.xml\n")
        urls = "".join(f"<url><loc>{PROD_URL}{'' if p == '(home)' else p}</loc></url>" for p, _ in PAGES if p != "404.html")
        (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
        for old, new in REDIRECTS.items():
            target = OUT / old / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            url = PROD_URL + new
            target.write_text(f'<!doctype html><meta charset="utf-8"><title>Moved</title><link rel="canonical" href="{url}">'
                              f'<meta http-equiv="refresh" content="0; url={url}"><p>This page moved to <a href="{url}">{url}</a>.</p>\n')
    else:
        (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n")


def check_output():
    problems, dashes = [], 0
    for f in sorted(OUT.rglob("*.html")):
        text = f.read_text()
        where = f.relative_to(OUT)
        dashes += text.count("—") + text.count("–")
        for m in re.finditer(r'(?:href|src)="(/(?!/)[^"]*)"', text):
            problems.append(f"root-relative path {m.group(1)} in {where}")
        if f.name == "404.html" and f.parent == OUT:
            continue
        refs = [m.group(1) for m in re.finditer(r'(?:href|src)="([^"]+)"', text)]
        for m in re.finditer(r'srcset="([^"]+)"', text):
            refs += [part.strip().split(" ")[0] for part in m.group(1).split(",")]
        for url in refs:
            url = html.unescape(url)
            if re.match(r"^(https?:|mailto:|tel:|#|data:)", url):
                continue
            clean = url.split("#")[0].split("?")[0]
            target = (f.parent / clean).resolve()
            if clean.endswith("/") or clean in ("", ".", "./") or target.is_dir():
                target = target / "index.html"
            if not target.exists():
                problems.append(f"broken link {url} in {where}")
    return problems, dashes


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(PUBLIC, OUT, ignore=shutil.ignore_patterns(".DS_Store", "*.md"))
    build_static_pages()
    build_product_pages()
    build_application_pages()
    build_extras()
    problems, dashes = check_output()
    verify_total = sum(n for _, n in PAGES)
    print(f"Built {len(PAGES)} pages into _site/ ({'LAUNCH' if LAUNCH else 'staging'})")
    if verify_total:
        print(f"[VERIFY] markers: {verify_total}")
        for path, n in PAGES:
            if n:
                print(f"  {n:3d}  {path}")
    if dashes:
        print(f"warning: {dashes} em or en dashes in output")
    if problems:
        print(f"{len(problems)} problems:")
        for msg in problems:
            print("  " + msg)
        sys.exit(1)
    if LAUNCH and verify_total:
        print("Launch blocked: [VERIFY] markers remain.")
        sys.exit(1)


if __name__ == "__main__":
    main()
