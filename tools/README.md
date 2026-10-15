# Evidence repository — build notes

`digital-evidence.html` is a generated file. Edit the data or the templates, then rebuild:

```bash
python3 tools/check_duplicates.py     # no duplicate studies?
python3 tools/check_summaries.py      # every figure in the summaries traceable to a cited study?
python3 tools/build_dashboard.py      # write digital-evidence.html
```

No dependencies beyond the Python standard library. The output is a **single self-contained HTML
file**: the study data, the topic summaries and the fonts are embedded, so the page makes no external
requests and can be uploaded as-is to GitHub Pages, Posit Connect or any static host.

## Layout

| Path | What it is |
|---|---|
| `data/evidence.json` | The studies. This is the file to edit. |
| `data/summaries.json` | The "Evidence summary" text for each topic. |
| `tools/templates/head.html` | Design tokens and all CSS. |
| `tools/templates/body.html` | Page markup and the dashboard's JavaScript. |
| `tools/fonts/` | Inter and Playfair Display (SIL Open Font License; licence texts alongside), embedded at build time. |
| `tools/build_dashboard.py` | Validates the data and renders the page. |
| `tools/check_duplicates.py` | Reports duplicate studies; `--fix` merges them, keeping the latest version. |
| `tools/check_summaries.py` | Checks every number in the summaries against the studies each sentence cites. |
| `digital-evidence.html` | Generated output — do not hand-edit. |

## Adding a study

Append an object to `data/evidence.json`. The build validates every entry and refuses to write the
page if a topic, outcome, lever or tier is unrecognised, so a typo fails loudly rather than silently
dropping a study from the filters.

```json
{
  "key":       "muralidharan-2016",
  "topics":    ["dpi", "govplatforms"],
  "outcomes":  ["govt", "inclusion"],
  "levers":    ["investment"],
  "tier":      "rct",
  "design":    "Randomized rollout across 157 sub-districts",
  "authors":   "Muralidharan, Niehaus and Sukhtankar",
  "year":      2016,
  "title":     "Building state capacity: evidence from biometric smartcards in India",
  "venue":     "American Economic Review 106(10)",
  "url":       "https://www.aeaweb.org/articles?id=10.1257/aer.20141346",
  "region":    "South Asia",
  "countries": "India",
  "period":    "2010-2012",
  "data":      "Administrative payment records plus a 19,000-household survey",
  "findings":  "Prose summary. Lead with the identification strategy, then the reported magnitudes.",
  "magnitude": "One headline statistic."
}
```

`key` is the study's stable identifier — the summaries cite it — so do not change a key once a summary
uses it. Leave it out and the build derives one (first author's surname and year). `cite`, the short
citation shown in the summaries ("Muralidharan et al. (2016)"), is also derived when absent. `id` is
assigned at build time; anything you put there is overwritten.

Run `python3 tools/check_duplicates.py` after adding studies: a working paper and its published version,
or the same paper under two spellings of an author's name, are easy to enter twice.

### Vocabularies

All four are closed sets — the dashboard's matrix and filters are built from them, so a new value needs
adding to `tools/build_dashboard.py` and to the matching array in `tools/templates/body.html`.

**Topics** — `broadband`, `devices`, `ixp`, `datacenters`, `cloud`, `dpi` (foundational digital public
infrastructure — ID, e-signature, data-exchange layers), `govplatforms` (digital government platforms &
services — tax, procurement, land registries, service delivery), `payments` (digital payments & mobile
money), `skills`, `transformation`, `ai`, `social` (social media), `cyber`, `datagov`

**Outcomes** — `growth`, `labor`, `firms`, `welfare`, `inclusion`, `govt`, `humancap`, `environment`

**Levers — what the study evaluates** — one or more of:

| Lever | Use it for |
|---|---|
| `policy` | A change in the rules: regulation and law, spectrum and licensing, competition and market entry, infrastructure-sharing obligations, taxes and subsidies, mandates such as compulsory biometric authentication. |
| `investment` | Building or rolling something out — network coverage, cables, data centers, digital ID, GovTech systems, payment digitization — or delivering a program (training, devices, pilots). |
| `adoption` | Firms, workers or households taking up or using a technology, where variation comes from adoption or exposure rather than a rule or a rollout. Includes exposure indices and models of economy-wide adoption. |

A bundle — a platform plus a mandate to use it — takes more than one lever.

**Tiers — strength of identification**

| Tier | Use it for |
|---|---|
| `rct` | Randomized controlled trials and field experiments. |
| `quasi` | Difference-in-differences, instrumental variables, regression discontinuity, event studies, synthetic controls. |
| `structural` | Structural, general-equilibrium and task-based models; scenario projections. |
| `descriptive` | Cross-sectional correlations, panel associations, case studies, agency statistics. |
| `review` | Literature reviews, meta-analyses, evidence syntheses. |

Only `rct` and `quasi` count towards the "causal" figures on the page. Grade by the identification
strategy the authors actually use, not by how convincing the finding sounds.

## Editing the summaries

`data/summaries.json` has one entry per topic with a `headline`, and lists of `findings`, `mechanisms`
and `gaps`. Cite studies inline by key in braces — `"... by 6.9-13.2 percentage points {hjort-2019}."` —
and the build turns each into a linked short citation. Every number must be copied from a study the
same sentence cites; `tools/check_summaries.py` enforces this and lists anything it cannot trace.
The counts shown with each summary (studies, causal, by lever) are computed from the data at build time.

## Conventions worth keeping

- **Magnitudes belong in `findings`.** The page highlights percentages, currency amounts, percentage
  points and standard deviations automatically.
- **Link to the definitive version** — the published article where one exists, the working paper otherwise.
- **Record null and negative results.** A repository that only holds positive findings misrepresents
  the literature.
