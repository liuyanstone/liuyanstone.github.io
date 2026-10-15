#!/usr/bin/env python3
"""Find duplicate studies in data/evidence.json.

    python3 tools/check_duplicates.py            # report likely duplicates, exit 1 if any
    python3 tools/check_duplicates.py --fix      # merge them, keeping the latest version

The same paper often enters a repository more than once: as a working paper and as the published
article, under two spellings of an author's name, or with a revised title. Matching uses, in order:

  1. a shared identifier in the link (NBER number, DOI, SSRN id, arXiv id);
  2. the same normalised title;
  3. the same first author plus a near-identical title, or the same distinctive main title
     ("From Chalkboards to Chatbots: ...") with a different subtitle;
  4. the same first author, a close year and heavily overlapping abstracts — but only when the
     countries studied are compatible, so an author's Nigeria and Tanzania papers stay separate;
  5. the same first author and year reporting the same three or more distinctive numbers (decimals,
     percentages) — which catches a working paper whose title changed on publication.

Pairs that share several distinctive reported numbers but are years apart, and untitled entries that
sit next to a titled study by the same author from the same period, are listed for manual review and
never merged automatically.

When merging, the latest version wins (newest year, then a published link over a working-paper
link), and the topic, outcome and lever tags of every version are kept.
"""
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'data', 'evidence.json')

STOP = set('the a an of and or to in on for with by from at as is are be into using use evidence effect effects '
           'impact impacts study analysis data paper new does do how what role case field experimental '
           'experiment among across their its can more less than'.split())
GENERIC_GEO = set('global cross country countries multi multiple worldwide international world developing developed '
                  'economies economy low middle income lics mics ssa oecd eu sub saharan africa asia america europe '
                  'region regions various several and the'.split())


def deaccent(s):
    s = (s or '').replace('’', "'").replace('‘', "'").replace('`', "'")   # D’Andrea == D'Andrea
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def sig(s):
    return set(w for w in re.findall(r"[a-z]{3,}", deaccent(s).lower()) if w not in STOP)


def jac(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def surname(authors):
    first = re.split(r'\s*(?:,|&| and )\s*', deaccent(authors).strip())[0]
    words = [w for w in re.findall(r"[A-Za-z][\w'\-]+", first)
             if w.lower() not in ('et', 'al', 'the', 'de', 'van', 'von', 'la', 'del', 'dal')]
    return words[-1].lower() if words else ''


def norm_title(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', deaccent(s).lower())).strip()


def distinctive_prefix(a, b):
    pa = re.findall(r"[a-z0-9]+", deaccent(a).lower())[:4]
    pb = re.findall(r"[a-z0-9]+", deaccent(b).lower())[:4]
    return len(pa) == 4 and pa == pb and sum(1 for w in pa if len(w) > 2 and w not in STOP) >= 2


def strong_id(url):
    u = (url or '').strip().lower()
    for pat, pre in ((r'nber\.org\S*?/(w\d{4,6})', 'nber'),
                     (r'(10\.\d{4,9}/[-._;()/:a-z0-9]+)', 'doi'),
                     (r'abstract_?id=(\d+)', 'ssrn'),
                     (r'arxiv\.org/(?:abs|pdf)/([\d.]+)', 'arxiv'),
                     (r'worldbank\.org/\S*?/(\d{15,18})/', 'wbdoc')):
        m = re.search(pat, u)
        if m:
            return pre + ':' + m.group(1).rstrip('.')
    return None


def geo_tokens(e):
    return set(re.findall(r"[a-z]{3,}", deaccent(f"{e.get('countries', '')} {e.get('region', '')}").lower())) - GENERIC_GEO


def geo_compatible(a, b):
    ga, gb = geo_tokens(a), geo_tokens(b)
    return (not ga) or (not gb) or bool(ga & gb)


def numbers(e):
    """Distinctive reported numbers: decimals and percentages, not years or small counts."""
    txt = f"{e.get('findings', '')} {e.get('magnitude', '')}"
    out = set()
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(%|percent|percentage points?|pp\b|sd\b|standard deviation)', txt, re.I):
        out.add(m.group(1))
    for m in re.finditer(r'\b\d+\.\d+\b', txt):
        out.add(m.group(0))
    return {n for n in out if not re.fullmatch(r'(19|20)\d\d', n) and n not in {'1', '2', '0', '10', '100'}}


def find(papers):
    """Return (clusters, review_pairs). clusters: lists of indices to merge, with reasons."""
    n = len(papers)
    parent = list(range(n))
    reason = {}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def link(a, b, why):
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
            reason[(min(a, b), max(a, b))] = why

    byid, bytitle, bysur = defaultdict(list), defaultdict(list), defaultdict(list)
    for i, e in enumerate(papers):
        sid = strong_id(e.get('url'))
        if sid:
            byid[sid].append(i)
        nt = norm_title(e.get('title'))
        if len(nt) >= 22:
            bytitle[nt].append(i)
        s = surname(e.get('authors'))
        if s:
            bysur[s].append(i)

    for sid, idx in byid.items():
        for j in idx[1:]:
            link(idx[0], j, f'same identifier {sid}')
    for nt, idx in bytitle.items():
        for j in idx[1:]:
            if abs((papers[idx[0]].get('year') or 0) - (papers[j].get('year') or 0)) <= 4:
                link(idx[0], j, 'same title')

    review = []
    for s, idx in bysur.items():
        for x in range(len(idx)):
            for y in range(x + 1, len(idx)):
                i, j = idx[x], idx[y]
                a, b = papers[i], papers[j]
                ti, tj = sig(a.get('title')), sig(b.get('title'))
                fi, fj = sig(a.get('findings')), sig(b.get('findings'))
                yi, yj = a.get('year') or 0, b.get('year') or 0
                if jac(ti, tj) >= 0.6:
                    link(i, j, 'same author, near-identical title')
                    continue
                if distinctive_prefix(a.get('title'), b.get('title')):
                    link(i, j, 'same author, same main title')
                    continue
                overlap = max(jac(fi, fj), jac(ti, fj), jac(tj, fi))
                one_titleless = bool(ti) != bool(tj)
                if one_titleless and overlap >= 0.25 and geo_compatible(a, b) and abs(yi - yj) <= 1:
                    link(i, j, 'same author and year, overlapping abstract (one entry untitled)')
                    continue
                if not one_titleless and overlap >= 0.30 and geo_compatible(a, b) and abs(yi - yj) <= 3:
                    link(i, j, 'same author, overlapping abstract')
                    continue
                shared = numbers(a) & numbers(b)
                if len(shared) >= 3 and abs(yi - yj) <= 1 and geo_compatible(a, b):
                    link(i, j, 'same author and year, same reported numbers')
                    continue
                if root(i) == root(j):
                    continue
                if len(shared) >= 3:
                    review.append((i, j, 'shared numbers ' + ', '.join(sorted(shared)[:6])))
                elif (one_titleless and abs(yi - yj) <= 3 and geo_compatible(a, b)
                      and set(a.get('topics') or []) & set(b.get('topics') or [])):
                    # an untitled stub next to a titled study by the same author: often the same paper
                    review.append((i, j, f'untitled stub, same author and period, overlap {overlap:.2f}'))

    clusters = defaultdict(list)
    for i in range(n):
        clusters[root(i)].append(i)
    groups = []
    for members in clusters.values():
        if len(members) > 1:
            why = sorted({w for (a, b), w in reason.items() if a in members and b in members})
            groups.append((members, why))
    return groups, review


def rank(e):
    url = (e.get('url') or '').lower()
    preprint = re.search(r'nber\.org|ssrn|arxiv|repec|ideas\.|/wp[-/]|working.?paper|dms_pub|'
                         r'documents\d*\.worldbank|\.gov/|github\.io', url)
    return (e.get('year') or 0, 0 if preprint else 1, 1 if e.get('title') else 0, len(e.get('findings') or ''))


def merge(papers, groups):
    drop = set()
    for members, _ in groups:
        entries = [papers[i] for i in members]
        win = max(entries, key=rank)
        for e in entries:
            if e is win:
                continue
            for fld in ('topics', 'outcomes', 'levers'):
                for v in e.get(fld) or []:
                    if v not in win.setdefault(fld, []):
                        win[fld].append(v)
            for fld in ('title', 'venue', 'data', 'magnitude', 'period', 'countries', 'design'):
                if not win.get(fld) and e.get(fld):
                    win[fld] = e[fld]
            drop.add(id(e))
    return [p for p in papers if id(p) not in drop]


def label(e):
    return f"{(e.get('authors') or '')[:34]:34} {e.get('year')} | {(e.get('title') or e.get('findings', ''))[:60]}"


def main():
    papers = json.load(open(PATH))
    groups, review = find(papers)
    for members, why in groups:
        win = max((papers[i] for i in members), key=rank)
        print(f"DUPLICATE ({'; '.join(why)}):")
        for i in members:
            print(f"  {'keep' if papers[i] is win else 'drop'}  {label(papers[i])}")
    if review:
        print('\nREVIEW BY HAND (possible duplicates the rules will not merge on their own):')
        for i, j, why in review:
            print(f"  {label(papers[i])}\n  {label(papers[j])}\n     {why}")
    print(f'\n{len(groups)} duplicate group(s), {len(review)} pair(s) to review, {len(papers)} studies.')
    if '--fix' in sys.argv and groups:
        merged = merge(papers, groups)
        json.dump(merged, open(PATH, 'w'), indent=1, ensure_ascii=False)
        print(f'merged -> {len(merged)} studies written to {PATH}')
    sys.exit(1 if groups and '--fix' not in sys.argv else 0)


if __name__ == '__main__':
    main()
