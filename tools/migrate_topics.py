#!/usr/bin/env python3
"""One-off data migration for data/evidence.json.

1. Splits the old "digital public infrastructure & gov platforms" topic (`dpi`) into
   three: `dpi` (foundational identity, e-signature, data-exchange layers),
   `govplatforms` (e-government services, tax, procurement, land registries), and
   `payments` (digital payments and mobile money).
2. Adds two new topics across the whole repository: `payments` and `social` (social media).
3. De-duplicates the repository globally by paper identity (author, title, year, findings),
   keeping the latest / most-published version and its link, and unioning the topic and
   outcome tags of every version that is merged away.

Run once, then rebuild with tools/build_dashboard.py. Prints a report to stdout.
"""
import json, os, re, unicodedata
from collections import defaultdict


def deaccent(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'data', 'evidence.json')

# ---------------------------------------------------------------- classification
# Payments and mobile money — the instrument or system is the subject of study.
PAY_RE = re.compile(
    r'\bmobile money\b|m-?pesa|m-?shwari|\bbkash\b|\bgcash\b|airtel money|mtn momo|orange money|'
    r'\bmomo\b|digital payment|mobile payment|e-?payment|electronic payment|instant payment|'
    r'fast payment|real-?time payment|\bupi\b|unified payments|\bpix\b|promptpay|\bg2p\b|'
    r'government-to-person|mobile wallet|e-?wallet|digital wallet|branchless banking|agent banking|'
    r'point-?of-?sale|\bpos\b terminal|digital financial services|digitiz(?:e|ing|ed|ation)[^.]{0,40}payment|'
    r'cashless|demoneti[sz]ation|debit card|electronic benefit|electronic voucher|payroll[- ]?tax(?!)|'
    r'\bremittance', re.I)
# payroll-tax compliance is tax, not payments — handled by removing that false hit below.

# Foundational digital public infrastructure — identity, signatures, interoperable data layers.
DPI_RE = re.compile(
    r'digital id\b|digital identity|\be-?id\b|biometric|aadhaar|national id\b|foundational id|'
    r'unique identif|identity verification|identification (?:system|number|program)|e-?signature|'
    r'electronic signature|digital signature|data exchange|x-?road|interoperab|digital credential|'
    r'know your customer|\bkyc\b|civil registr|digital public infrastructure', re.I)

# Digital government platforms and services — tax, procurement, land, e-gov service delivery.
GOV_RE = re.compile(
    r'e-?procurement|electronic procurement|tax (?:administration|compliance|collection|capacity|enforcement|auditor|evasion|revenue)|'
    r'tax-?rich|\bvat\b|tax filing|e-?filing|e-?tax|digital tax|payroll-?tax|land registr|land record|'
    r'property registr|cadastr|e-?government|e-?governance|govtech|government platform|government service|'
    r'public (?:service delivery|employment|program)|digital government|online (?:government|public) service|'
    r'\bcustoms\b|asycuda|smart city|participatory budget|grievance|social (?:assistance|protection|registry|transfer)|'
    r'welfare (?:program|delivery|payment|benefit)|beneficiar|\bfmis\b|financial management information|'
    r'public financial management|billing machine|ration|subsid|targeting of (?:humanitarian|aid|welfare)|'
    r'job portal|civil service|bureaucrat|state capacity|monitoring', re.I)

# Social media and the online information environment. Deliberately excludes WhatsApp, which in
# this repository is a delivery channel for AI tutors and business-advice chatbots, not the subject.
SOCIAL_RE = re.compile(
    r'social media|social-media|social network(?:ing)? (?:site|platform|service)|\bfacebook\b|'
    r'\btwitter\b|instagram|tiktok|\byoutube\b|\bweibo\b|misinformation|disinformation|fake news|'
    r'hate speech|echo chamber|content moderation|online news consumption|news ?feed', re.I)


# Targeted corrections for entries whose fields were crossed during earlier automated merging.
def apply_corrections(data):
    fixed = 0
    for e in data:
        # p188: correct paper (Kelley et al., online job portals, AER:Insights 2023) but its
        # findings text was pasted from an unrelated Aadhaar case study. Restore faithful findings
        # from the paper's own design and headline result, and move it off the DPI axis.
        if 'aeri.20220566' in (e.get('url') or ''):
            e['findings'] = (
                'Run a field experiment with firms recruiting through an online job portal in India, '
                'randomizing access to paid job advertising and to a feature that verifies applicants’ '
                'identity and credentials. Both frictions bind: firms offered paid advertising together with '
                'applicant identity verification increased hiring by 68 percent relative to control, showing '
                'that information frictions — not merely a shortage of applicants — hold back '
                'formal-sector hiring on digital job platforms.')
            e['topics'] = ['transformation']
            e['outcomes'] = ['labor', 'firms']
            fixed += 1
    return fixed


def blob(e):
    return ' '.join(str(e.get(k, '')) for k in
                    ('title', 'findings', 'magnitude', 'design', 'venue', 'region', 'countries'))


def reclassify(data):
    report = {'dpi_split': [], 'payments_added': [], 'social_added': []}
    for e in data:
        text = blob(e)
        topics = list(e['topics'])

        if 'dpi' in topics:
            rest = [t for t in topics if t != 'dpi']
            new = []
            if DPI_RE.search(text): new.append('dpi')
            if GOV_RE.search(text): new.append('govplatforms')
            if PAY_RE.search(text): new.append('payments')
            if not new:
                new = ['govplatforms']          # section was "digital government / public services"
            topics = new + rest
            report['dpi_split'].append((e.get('authors'), e.get('year'),
                                        (e.get('title') or e['findings'])[:52], new))

        # whole-repository scans for the two brand-new topics
        if 'payments' not in topics and PAY_RE.search(text):
            topics.append('payments')
            report['payments_added'].append((e.get('authors'), e.get('year'),
                                              (e.get('title') or e['findings'])[:52], topics))
        if 'social' not in topics and SOCIAL_RE.search(text):
            topics.append('social')
            report['social_added'].append((e.get('authors'), e.get('year'),
                                           (e.get('title') or e['findings'])[:52], topics))

        seen = set()
        e['topics'] = [t for t in topics if not (t in seen or seen.add(t))]
    return report


# ---------------------------------------------------------------- de-duplication
STOP = set('the a an of and or to in on for with by from at as is are be into using use evidence '
           'effect effects impact impacts study analysis data paper new does do how what role case '
           'field experimental experiment among across their its can more less than'.split())


def sig(s):
    return set(w for w in re.findall(r"[a-z]{3,}", deaccent(s).lower()) if w not in STOP)


def title_prefix(s, n=4):
    """First n raw words of a title, lowercased and de-accented — catches papers that share a
    distinctive main title but diverge in the subtitle (e.g. 'From Chalkboards to Chatbots: ...')."""
    words = re.findall(r"[a-z0-9]+", deaccent(s or '').lower())
    return words[:n]


def norm_title(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', deaccent(s or '').lower())).strip()


def distinctive_prefix(ei, ej):
    """True when two titles share an identical first-four-word prefix carrying real content
    (at least two non-stopword tokens), so a generic opener like 'the impact of ...' can't match."""
    pi, pj = title_prefix(ei.get('title')), title_prefix(ej.get('title'))
    if len(pi) < 4 or pi != pj:
        return False
    return sum(1 for w in pi if len(w) > 2 and w not in STOP) >= 2


GENERIC_GEO = set('global cross country countries multi multiple worldwide international world '
                  'developing developed economies economy low middle income lics mics ssa oecd eu '
                  'sub saharan africa asia america europe region regions various several and the'.split())


def geo_tokens(e):
    toks = set(re.findall(r"[a-z]{3,}", deaccent(e.get('countries', '') + ' ' + e.get('region', '')).lower()))
    return toks - GENERIC_GEO


def geo_compatible(ei, ej):
    a, b = geo_tokens(ei), geo_tokens(ej)
    return (not a) or (not b) or bool(a & b)


def surname(authors):
    first = re.split(r'\s*(?:,|&| and )\s*', deaccent(authors).strip())[0]
    words = [w for w in re.findall(r"[A-Za-z][\w'\-]+", first)
             if w.lower() not in ('et', 'al', 'the', 'de', 'van', 'von', 'la', 'del')]
    return words[-1].lower() if words else ''


def strong_id(url):
    u = (url or '').strip().lower()
    if not u:
        return None
    for pat, pre in ((r'nber\.org\S*?/(w\d{4,6})', 'nber'),
                     (r'(10\.\d{4,9}/[-._;()/:a-z0-9]+)', 'doi'),
                     (r'abstract_id=(\d+)', 'ssrn'),
                     (r'arxiv\.org/(?:abs|pdf)/([\d.]+)', 'arxiv')):
        m = re.search(pat, u)
        if m:
            return pre + ':' + m.group(1).rstrip('.')
    return None


def jac(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def dedupe(data):
    n = len(data)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # link by shared strong identifier (NBER / DOI / SSRN / arXiv)
    byid = defaultdict(list)
    for i, e in enumerate(data):
        sid = strong_id(e.get('url'))
        if sid:
            byid[sid].append(i)
    for idxs in byid.values():
        for j in idxs[1:]:
            union(idxs[0], j)

    # link by identical normalised title (catches organisation-authored reports whose author
    # strings differ, e.g. "GSMA" vs "GSMA Connected Women", which never share a surname bucket)
    bytitle = defaultdict(list)
    for i, e in enumerate(data):
        nt = norm_title(e.get('title'))
        if len(nt) >= 22:
            bytitle[nt].append(i)
    for idxs in bytitle.values():
        base = idxs[0]
        for j in idxs[1:]:
            if abs((data[base].get('year') or 0) - (data[j].get('year') or 0)) <= 4:
                union(base, j)

    # link by first-author surname + title / findings similarity
    bysur = defaultdict(list)
    for i, e in enumerate(data):
        s = surname(e.get('authors'))
        if s:
            bysur[s].append(i)
    for s, idxs in bysur.items():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                ei, ej = data[i], data[j]
                ti, tj = sig(ei.get('title')), sig(ej.get('title'))
                fi, fj = sig(ei.get('findings')), sig(ej.get('findings'))
                yi, yj = ei.get('year') or 0, ej.get('year') or 0

                # Strong: (near-)identical title or a shared distinctive main-title prefix. Same
                # first author + same title = same paper, whatever the geography field happens to say.
                strong = (jac(ti, tj) >= 0.6) or distinctive_prefix(ei, ej)
                # Medium: abstracts overlap enough AND the geography is compatible AND the versions
                # are close in time. The geo guard blocks same-author papers on different countries
                # (e.g. Bahia's Nigeria vs Tanzania studies) from collapsing into one. When exactly
                # one side is a legacy stub without a title, the bar is lower but the year must match,
                # because a stub is the repository's own earlier summary of a paper it also lists.
                overlap = max(jac(fi, fj), jac(ti, fj), jac(tj, fi))
                one_titleless = bool(ti) != bool(tj)
                if one_titleless:
                    medium = overlap >= 0.25 and geo_compatible(ei, ej) and abs(yi - yj) <= 1
                else:
                    medium = overlap >= 0.30 and geo_compatible(ei, ej) and abs(yi - yj) <= 3

                if strong or medium:
                    union(i, j)

    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    def rank(e):
        url = (e.get('url') or '').lower()
        preprint = re.search(r'nber\.org|ssrn|arxiv|repec|ideas\.|/wp[-/]|working.?paper|'
                             r'dms_pub|documents\d*\.worldbank|\.gov/|github\.io', url)
        return (e.get('year') or 0,          # latest year = latest version
                0 if preprint else 1,        # then a published link over a preprint
                1 if e.get('title') else 0,
                len(e.get('findings') or ''))

    kept, merges = [], []
    for members in clusters.values():
        if len(members) == 1:
            kept.append(data[members[0]])
            continue
        entries = [data[i] for i in members]
        winner = max(entries, key=rank)
        for e in entries:
            if e is winner:
                continue
            for t in e['topics']:
                if t not in winner['topics']:
                    winner['topics'].append(t)
            for o in e['outcomes']:
                if o not in winner['outcomes']:
                    winner['outcomes'].append(o)
            for fld in ('title', 'venue', 'data', 'magnitude', 'period', 'countries', 'design'):
                if not winner.get(fld) and e.get(fld):
                    winner[fld] = e[fld]
        merges.append((winner.get('authors'), winner.get('year'),
                       (winner.get('title') or winner['findings'])[:48],
                       [(e.get('authors'), e.get('year'),
                         (e.get('url') or '')[:40]) for e in entries if e is not winner]))
        kept.append(winner)
    return kept, merges


def main():
    data = json.load(open(PATH))
    before = len(data)
    nfix = apply_corrections(data)
    print(f'applied {nfix} targeted field correction(s)\n')
    rep = reclassify(data)
    data, merges = dedupe(data)

    for i, e in enumerate(data):
        e['id'] = 'p%03d' % i

    print(f'reclassified dpi entries: {len(rep["dpi_split"])}')
    for a, y, t, new in rep['dpi_split']:
        print(f'   {str(a)[:24]:24} {y}  ->  {"+".join(new):26} | {t}')
    print(f'\npayments tag added to {len(rep["payments_added"])} non-dpi entries:')
    for a, y, t, tp in rep['payments_added']:
        print(f'   {str(a)[:24]:24} {y} | {t}  [{",".join(tp)}]')
    print(f'\nsocial tag added to {len(rep["social_added"])} entries:')
    for a, y, t, tp in rep['social_added']:
        print(f'   {str(a)[:24]:24} {y} | {t}  [{",".join(tp)}]')

    print(f'\nde-duplication merged {before - len(data)} entries ({before} -> {len(data)}):')
    for a, y, t, losers in merges:
        print(f'   KEEP {str(a)[:22]:22} {y} | {t}')
        for la, ly, lu in losers:
            print(f'      drop {str(la)[:22]:22} {ly} | {lu}')

    json.dump(data, open(PATH, 'w'), indent=1, ensure_ascii=False)
    print(f'\nwrote {PATH}  ({len(data)} entries)')


if __name__ == '__main__':
    main()
