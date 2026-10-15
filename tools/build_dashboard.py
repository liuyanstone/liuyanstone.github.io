#!/usr/bin/env python3
"""Regenerate digital-evidence.html from data/evidence.json and data/summaries.json.

    python3 tools/build_dashboard.py

The output is ONE self-contained HTML file: the study data, the evidence summaries and the
fonts are all embedded, so the page makes no external requests and can be uploaded as-is
to any static host (GitHub Pages, Posit Connect, an intranet server).

To add or edit a study, edit data/evidence.json and re-run. Each entry:

    {
      "key":       "bahia-2023",                  # stable id, used by summaries to cite it
      "cite":      "Bahia et al. (2023)",          # optional short citation; derived if absent
      "topics":    ["broadband"],                  # see TOPICS below, 1+
      "outcomes":  ["labor", "welfare"],           # see OUTCOMES below, 1+
      "levers":    ["investment"],                 # policy | investment | adoption, 1+
      "tier":      "quasi",                        # rct | quasi | structural | descriptive | review
      "design":    "Difference-in-differences (staggered 3G rollout)",
      "authors":   "Bahia et al.",
      "year":      2023,
      "title":     "Mobile broadband internet, poverty and labor outcomes in Tanzania",
      "venue":     "World Bank Economic Review 37(2)",
      "url":       "https://...",
      "region":    "Africa",
      "countries": "Tanzania",
      "period":    "2008-2018",
      "data":      "Panel household surveys + geocoded 3G coverage maps",
      "findings":  "Prose summary carrying the reported magnitudes.",
      "magnitude": "One headline statistic."
    }

`tier` grades the identification strategy the authors actually use. `levers` records what the
study evaluates: a change in rules (policy), building or delivering something (investment), or
the take-up and use of a technology (adoption).

data/summaries.json holds the narrative "Evidence summary" for each topic. Cite studies inline
with their key in braces — "{bahia-2023}" — and the build turns each into a link; an unknown key
stops the build.
"""
import base64
import datetime
import html
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TOPICS = [
    ('broadband', 'Broadband & internet infrastructure'),
    ('devices', 'Digital devices'),
    ('ixp', 'Internet exchange points'),
    ('datacenters', 'Data centers'),
    ('cloud', 'Cloud computing'),
    ('dpi', 'Digital public infrastructure'),
    ('govplatforms', 'Digital government platforms & services'),
    ('payments', 'Digital payments & mobile money'),
    ('skills', 'Digital skills'),
    ('transformation', 'Broader digital transformation'),
    ('ai', 'Artificial intelligence'),
    ('social', 'Social media'),
    ('cyber', 'Cybersecurity'),
    ('datagov', 'Data governance'),
]
OUTCOMES = ['growth', 'labor', 'firms', 'welfare', 'inclusion', 'govt', 'humancap', 'environment']
TIERS = ['rct', 'quasi', 'structural', 'descriptive', 'review']
LEVERS = [('policy', 'Policy reform'), ('investment', 'Investment & programs'), ('adoption', 'Adoption & use')]
CAUSAL_TIERS = ('rct', 'quasi')

TITLE = 'Development Impact of Digital Transformation &amp; AI | Evidence Repository'

# (file, family, weight range, unicode-range) — Inter and Playfair Display, SIL OFL 1.1, see tools/fonts/
LATIN = ('U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,'
         'U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD')
LATIN_EXT = ('U+0100-02AF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,'
             'U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF')
FONTS = [
    ('inter-latin-ext-wght-normal.woff2', 'Inter', '100 900', LATIN_EXT),
    ('inter-latin-wght-normal.woff2', 'Inter', '100 900', LATIN),
    ('playfair-display-latin-ext-wght-normal.woff2', 'Playfair Display', '400 900', LATIN_EXT),
    ('playfair-display-latin-wght-normal.woff2', 'Playfair Display', '400 900', LATIN),
]


# ----------------------------------------------------------------------------- citations
def _deaccent(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c))


ORG_RE = re.compile(
    r'\b(agency|bank|fund|organi[sz]ation|union|association|institute|commission|council|office|'
    r'ministry|group|coalition|society|gsma|oecd|itu|imf|ilo|unctad|wto|iea|unesco|unicef|undp|world|'
    r'international|national|laborator(?:y|ies)|university|forum|foundation|cent(?:er|re)|department|'
    r'bureau|census|reserve|budget model|anthropic|openai|microsoft|google|pwc|mckinsey|deloitte|staff|'
    r'portal|reform|platforms?|programme|case study|source|estimates?|first|intelligence|network)\b', re.I)
PARTICLES = {'de', 'del', 'della', 'der', 'den', 'van', 'von', 'la', 'le', 'da', 'dal', 'dalla', 'di', 'do',
             'dos', 'das', 'du', 'ter'}
SUFFIXES = {'neto', 'filho', 'junior', 'júnior', 'jr', 'jr.'}


def _surname(name):
    words = re.findall(r"[^\s,]+", name.strip())
    words = [w for w in words if not re.fullmatch(r"(?:[A-Z]\.)+[A-Z]?\.?|[A-Z]", w)]   # drop initials
    if not words:
        return ''
    i = len(words) - 1
    if words[i].lower().strip('.') in SUFFIXES and i > 0:
        i -= 1
    j = i
    while j > 0 and words[j - 1].lower() in PARTICLES:
        j -= 1
    return ' '.join(words[j:])


def short_cite(authors, year):
    a = re.sub(r'\s*\(.*?\)', '', re.sub(r'\s+', ' ', authors or ''))
    a = re.sub(r'\s*\(.*$', '', a).strip()          # an unclosed parenthetical note
    etal = bool(re.search(r'\bet al\b', a, re.I))
    if ORG_RE.search(a) and not etal and not re.search(r',\s*[A-Z]\.', a):
        name = re.split(r'\s+(?:for|with)\s+|;', a)[0].strip(' ,')
        if len(name) > 48:
            name = name[:45].rsplit(' ', 1)[0] + '…'
        return f'{name} ({year})'
    a = re.sub(r',?\s*\bet al\.?', '', a, flags=re.I)
    parts = [p.strip() for p in re.split(r'\s*,\s*|\s*&\s*|\s+and\s+', a) if p.strip()]
    parts = [p for p in parts if not re.fullmatch(r"(?:[A-Z]\.\s*)+[A-Z]?\.?", p)]
    names = [s for s in (_surname(p) for p in parts) if s]
    if not names:
        return f'{authors} ({year})'
    if etal or len(names) >= 3:
        return f'{names[0]} et al. ({year})'
    if len(names) == 2:
        return f'{names[0]} and {names[1]} ({year})'
    return f'{names[0]} ({year})'


def make_key(entry, taken):
    names = re.findall(r"[a-z]+", _deaccent(short_cite(entry.get('authors', ''), '')).lower())
    stem = names[0] if names else 'study'
    base = f"{stem}-{entry.get('year') or 'nd'}"
    if base not in taken:
        return base
    words = [w for w in re.findall(r"[a-z]{4,}", _deaccent(entry.get('title') or entry.get('findings', '')).lower())
             if w not in {'evidence', 'effects', 'effect', 'impact', 'impacts', 'from', 'with', 'their', 'using'}]
    for w in words[:4]:
        cand = f'{base}-{w}'
        if cand not in taken:
            return cand
    n = 2
    while f'{base}-{n}' in taken:
        n += 1
    return f'{base}-{n}'


# ----------------------------------------------------------------------------- data
def load():
    with open(os.path.join(ROOT, 'data', 'evidence.json')) as fh:
        papers = json.load(fh)
    topic_slugs = {t for t, _ in TOPICS}
    lever_slugs = {l for l, _ in LEVERS}
    problems, keys = [], {}
    for i, p in enumerate(papers):
        where = p.get('key') or p.get('authors') or f'entry {i}'
        if p.get('tier') not in TIERS:
            problems.append(f'{where}: unknown tier {p.get("tier")!r}')
        for t in p.get('topics') or []:
            if t not in topic_slugs:
                problems.append(f'{where}: unknown topic {t!r}')
        for o in p.get('outcomes') or []:
            if o not in OUTCOMES:
                problems.append(f'{where}: unknown outcome {o!r}')
        for l in p.get('levers') or []:
            if l not in lever_slugs:
                problems.append(f'{where}: unknown lever {l!r}')
        if not p.get('topics') or not p.get('outcomes') or not p.get('levers'):
            problems.append(f'{where}: needs at least one topic, outcome and lever')
        if p.get('key'):
            if p['key'] in keys:
                problems.append(f'duplicate key {p["key"]!r}')
            keys[p['key']] = p
    # derive anything missing, deterministically
    for p in papers:
        if not p.get('key'):
            p['key'] = make_key(p, keys)
            keys[p['key']] = p
        if not p.get('cite'):
            p['cite'] = short_cite(p.get('authors'), p.get('year'))
    if problems:
        raise SystemExit('data/evidence.json has problems:\n  ' + '\n  '.join(problems))
    return papers


# ----------------------------------------------------------------------------- summaries
# Same pattern as hiNums() in templates/body.html, so summaries and study cards highlight identically.
_N, _R = r'\d[\d,]*(?:\.\d+)?', r'(?:\s?[-–]\s?|\s+to\s+)'
_U = (r'(?:percentage points?|percentage-points?|percent|%|p\.p\.|log points?|basis points?|'
      r'standard deviations?|std\.? dev\.?|SDs?)')
NUM_RE = re.compile(
    r'(^|[^\w.$])('
    rf'[−-]?{_N}(?:\s?%)?(?:{_R}[−-]?{_N})?\s?{_U}'
    rf'|(?:US)?\$\s?{_N}(?:{_R}\$?\s?{_N})?(?:\s?(?:trillion|billion|million|bn|mn|k)\b)?'
    rf'|{_N}(?:\s?[-–]\s?{_N})?\s?(?:times|-fold|fold)\b'
    r'|\d+(?:\.\d+)?x\b)', re.I)
TOKEN_RE = re.compile(r'\{([a-z0-9][a-z0-9\-]*)\}')


def _hinums(escaped):
    return NUM_RE.sub(lambda m: f'{m.group(1)}<b class="num">{m.group(2)}</b>', escaped)


def render_text(text, keymap, where):
    out, pos = [], 0
    for m in TOKEN_RE.finditer(text):
        out.append(_hinums(html.escape(text[pos:m.start()], quote=False)))
        e = keymap.get(m.group(1))
        if e is None:
            raise SystemExit(f'summaries.json ({where}): unknown study key {{{m.group(1)}}}')
        label = html.escape(e['cite'], quote=False)
        if e.get('url'):
            out.append(f'<a class="cite-link" href="{html.escape(e["url"])}" target="_blank" rel="noopener">{label}</a>')
        else:
            out.append(label)
        pos = m.end()
    out.append(_hinums(html.escape(text[pos:], quote=False)))
    return ''.join(out)


def render_summaries(papers):
    path = os.path.join(ROOT, 'data', 'summaries.json')
    if not os.path.exists(path):
        return '', 0
    with open(path) as fh:
        sums = json.load(fh)
    keymap = {p['key']: p for p in papers}
    blocks = []
    for slug, label in TOPICS:
        s = sums.get(slug)
        if not s:
            continue
        rows = [p for p in papers if slug in p['topics']]
        n, c = len(rows), sum(1 for p in rows if p['tier'] in CAUSAL_TIERS)
        lev = {l: sum(1 for p in rows if l in p['levers']) for l, _ in LEVERS}

        def items(field, cls, heading):
            lis = ''.join(f'<li>{render_text(t, keymap, slug + "." + field)}</li>' for t in s.get(field, []))
            return f'<div class="sum-block {cls}"><h4>{heading}</h4><ul>{lis}</ul></div>' if lis else ''

        lever_line = ''.join(
            f'<span><i class="lv-mark" data-l="{l}" aria-hidden="true"></i>{html.escape(lbl)}<b>{lev[l]}</b></span>'
            for l, lbl in LEVERS)
        blocks.append(
            f'<details class="sum" id="sum-{slug}" data-topic="{slug}">'
            f'<summary><span class="sum-head"><span class="sum-title">{html.escape(label)}</span>'
            f'<span class="sum-stats"><b>{n}</b> studies &middot; <b>{c}</b> causal</span>'
            f'<span class="sum-headline">{render_text(s.get("headline", ""), keymap, slug + ".headline")}</span></span></summary>'
            f'<div class="sum-body">'
            f'{items("findings", "findings", "What the evidence shows")}'
            f'<div class="sum-side">{items("mechanisms", "mechanisms", "Mechanisms")}'
            f'{items("gaps", "gaps", "Where the evidence is thin")}</div>'
            f'<div class="sum-foot"><div class="sum-levers" aria-label="Studies by what they evaluate">{lever_line}</div>'
            f'<button type="button" class="sum-show" data-t="{slug}">Show the {n} studies &rarr;</button></div>'
            f'</div></details>')
    return '\n'.join(blocks), len(blocks)


# ----------------------------------------------------------------------------- fonts
def font_face_css():
    rules = []
    for fname, family, weight, urange in FONTS:
        path = os.path.join(HERE, 'fonts', fname)
        if not os.path.exists(path):
            continue
        with open(path, 'rb') as fh:
            b64 = base64.b64encode(fh.read()).decode('ascii')
        rules.append(f"    @font-face {{ font-family:'{family}'; font-style:normal; font-display:swap; "
                     f"font-weight:{weight}; src:url(data:font/woff2;base64,{b64}) format('woff2'); "
                     f"unicode-range:{urange}; }}")
    return '\n'.join(rules)


# ----------------------------------------------------------------------------- build
def build():
    papers = load()
    papers.sort(key=lambda r: (-(r.get('year') or 0), (r.get('authors') or '').lower()))
    for i, p in enumerate(papers):
        p['id'] = 'p%03d' % i

    with open(os.path.join(HERE, 'templates', 'head.html')) as fh:
        head = fh.read().replace('__FONTFACE__', font_face_css())
    with open(os.path.join(HERE, 'templates', 'body.html')) as fh:
        body = fh.read()

    summary_html, n_sum = render_summaries(papers)
    causal = sum(1 for p in papers if p['tier'] in CAUSAL_TIERS)
    today = datetime.date.today()
    page_rows = [{k: v for k, v in p.items() if k != 'source'} for p in papers]   # provenance stays in the data file
    data_json = json.dumps(page_rows, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

    for key, val in {
        '__SUMMARY__': summary_html,
        '__DATA__': data_json,
        '__N__': str(len(papers)),
        '__NCAUSAL__': str(causal),
        '__UPDATED__': today.strftime('%-d %B %Y'),
    }.items():
        body = body.replace(key, val)

    desc = ('A searchable repository of %d economic studies on the development impact of digital '
            'transformation and AI, organized by digital topic, outcome and what each study evaluates, '
            'and graded by strength of causal identification.' % len(papers))
    esc_desc = html.escape(desc, quote=True)

    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{TITLE}</title>
  <meta name="description" content="{esc_desc}">
  <meta property="og:title" content="Development Impact of Digital Transformation &amp; AI">
  <meta property="og:description" content="{esc_desc}">
  <meta property="og:type" content="website">
{head}
</head>
<body>
{body}
</body>
</html>
'''
    out = os.path.join(ROOT, 'digital-evidence.html')
    with open(out, 'w') as fh:
        fh.write(page)

    print(f'{len(papers)} studies  ({causal} causally identified), {n_sum} topic summaries')
    print(f'wrote {out}  ({len(page) / 1024:.0f} KB)')


if __name__ == '__main__':
    build()
