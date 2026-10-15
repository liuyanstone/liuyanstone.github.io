#!/usr/bin/env python3
"""Check that every figure in data/summaries.json comes from a study the sentence cites.

    python3 tools/check_summaries.py                 # checks data/summaries.json
    python3 tools/check_summaries.py draft.json      # checks another file with the same structure

Each summary sentence cites studies with their key in braces, e.g. "{bahia-2023}". For every sentence
this script checks that (1) each cited key exists in data/evidence.json, (2) a sentence that states a
number cites at least one study, and (3) each number it states appears in the text of one of the
studies it cites (title, design, data, findings or magnitude). Years are ignored.

A number that fails check (3) is not necessarily wrong — it may be written differently in the source
("one-third" vs "33%") — but it must be confirmed by hand before publishing. Exit status 1 if anything
needs attention.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_RE = re.compile(r'\{([a-z0-9][a-z0-9\-]*)\}')
NUM_RE = re.compile(r'(?<![\w.])[−-]?\d[\d,]*(?:\.\d+)?')


def nums(text):
    out = []
    for m in NUM_RE.finditer(TOKEN_RE.sub(' ', text)):
        raw = m.group(0).replace('−', '-').lstrip('-').replace(',', '')
        if re.fullmatch(r'(19|20)\d\d', raw):         # a year
            continue
        out.append(raw)
    return out


def source_numbers(entry):
    txt = ' '.join(str(entry.get(f, '')) for f in ('title', 'design', 'data', 'findings', 'magnitude', 'period'))
    found = set()
    for m in NUM_RE.finditer(txt):
        raw = m.group(0).replace('−', '-').lstrip('-').replace(',', '')
        found.add(raw)
        if '.' in raw:                                   # 1.50 matches 1.5
            found.add(raw.rstrip('0').rstrip('.'))
    return found


def main():
    papers = {p['key']: p for p in json.load(open(os.path.join(ROOT, 'data', 'evidence.json')))}
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    sums = json.load(open(args[0] if args else os.path.join(ROOT, 'data', 'summaries.json')))
    issues, checked = [], 0
    for topic, s in sums.items():
        if topic.startswith('_'):
            continue
        sentences = [('headline', s.get('headline', ''))]
        for fld in ('findings', 'mechanisms', 'gaps'):
            sentences += [(f'{fld}[{i}]', t) for i, t in enumerate(s.get(fld, []))]
        for where, text in sentences:
            checked += 1
            keys = TOKEN_RE.findall(text)
            for k in keys:
                if k not in papers:
                    issues.append((topic, where, f'unknown study key {{{k}}}'))
            numbers = nums(text)
            if numbers and not keys:
                issues.append((topic, where, f'states {", ".join(numbers)} but cites no study'))
                continue
            pool = set()
            for k in keys:
                if k in papers:
                    pool |= source_numbers(papers[k])
            for n in numbers:
                if n not in pool and n.rstrip('0').rstrip('.') not in pool:
                    issues.append((topic, where, f'{n} not found in the cited studies ({", ".join(keys)})'))
    for topic, where, msg in issues:
        print(f'{topic}.{where}: {msg}')
    print(f'\n{checked} sentences checked, {len(issues)} issue(s).')
    sys.exit(1 if issues else 0)


if __name__ == '__main__':
    main()
