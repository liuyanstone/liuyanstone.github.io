#!/usr/bin/env python3
"""Regenerate digital-evidence.html from data/evidence.json.

    python3 tools/build_dashboard.py

To add or edit a study, edit data/evidence.json and re-run. Each entry:

    {
      "id":        "p000",                       # regenerated on build
      "topics":    ["broadband"],                # see TOPICS below, 1+
      "outcomes":  ["labor", "growth"],          # see OUTCOMES below, 1+
      "tier":      "quasi",                      # rct|quasi|structural|descriptive|review
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
      "magnitude": "One headline statistic.",
      "source":    "repo"                        # repo = seeded from the source document
    }

The `tier` field is the spine of the dashboard: it separates studies that can
support a causal claim from those that document an association. Grade it by the
identification strategy the authors actually use, not by how confident the
abstract sounds.
"""
import json
import os
import html
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TOPICS = ['broadband', 'devices', 'ixp', 'datacenters', 'cloud', 'dpi',
          'govplatforms', 'payments', 'skills', 'transformation', 'ai',
          'social', 'cyber', 'datagov']
OUTCOMES = ['growth', 'labor', 'firms', 'welfare', 'inclusion', 'govt', 'humancap', 'environment']
TIERS = ['rct', 'quasi', 'structural', 'descriptive', 'review']
CAUSAL_TIERS = ('rct', 'quasi')

TITLE = 'Development Impact of Digital Transformation &amp; AI | Evidence Repository'


def load():
    with open(os.path.join(ROOT, 'data', 'evidence.json')) as fh:
        papers = json.load(fh)

    problems = []
    for i, p in enumerate(papers):
        where = p.get('authors') or f'entry {i}'
        if p.get('tier') not in TIERS:
            problems.append(f'{where}: unknown tier {p.get("tier")!r}')
        for t in p.get('topics') or []:
            if t not in TOPICS:
                problems.append(f'{where}: unknown topic {t!r}')
        for o in p.get('outcomes') or []:
            if o not in OUTCOMES:
                problems.append(f'{where}: unknown outcome {o!r}')
        if not p.get('topics') or not p.get('outcomes'):
            problems.append(f'{where}: needs at least one topic and one outcome')
    if problems:
        raise SystemExit('data/evidence.json has problems:\n  ' + '\n  '.join(problems))
    return papers


def build():
    papers = load()
    papers.sort(key=lambda r: (-(r.get('year') or 0), (r.get('authors') or '').lower()))
    for i, p in enumerate(papers):
        p['id'] = 'p%03d' % i

    with open(os.path.join(HERE, 'templates', 'head.html')) as fh:
        head = fh.read()
    with open(os.path.join(HERE, 'templates', 'body.html')) as fh:
        body = fh.read()

    causal = sum(1 for p in papers if p['tier'] in CAUSAL_TIERS)
    today = datetime.date.today()
    data_json = json.dumps(papers, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

    for key, val in {
        '__DATA__': data_json,
        '__N__': str(len(papers)),
        '__NCAUSAL__': str(causal),
        '__UPDATED__': today.strftime('%-d %B %Y'),
        '__YEAR__': str(today.year),
    }.items():
        body = body.replace(key, val)

    desc = ('A searchable repository of %d rigorous economic studies on the development impact of '
            'digital transformation and AI, organised by digital topic and outcome and graded by '
            'strength of causal identification.' % len(papers))
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
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

    print(f'{len(papers)} studies  ({causal} causally identified)')
    print(f'wrote {out}  ({len(page) / 1024:.0f} KB)')


if __name__ == '__main__':
    build()
