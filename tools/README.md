# Evidence repository — build notes

`digital-evidence.html` is a generated file. Edit the data or the templates, then rebuild:

```bash
python3 tools/build_dashboard.py
```

No dependencies beyond the Python standard library. The output is a single
self-contained page with the study data embedded, so it works over `file://`,
GitHub Pages, or anywhere else static files are served.

## Layout

| Path | What it is |
|---|---|
| `data/evidence.json` | The studies. This is the file to edit. |
| `tools/templates/head.html` | Design tokens and all CSS. |
| `tools/templates/body.html` | Page markup and the dashboard's JavaScript. |
| `tools/build_dashboard.py` | Validates the data and renders the page. |
| `digital-evidence.html` | Generated output — do not hand-edit. |

## Adding a study

Append an object to `data/evidence.json`. The build validates every entry and
refuses to write the page if a topic, outcome, or tier is unrecognised, so a
typo fails loudly rather than silently dropping a study from the filters.

```json
{
  "topics":    ["dpi"],
  "outcomes":  ["govt", "inclusion"],
  "tier":      "rct",
  "design":    "Randomised rollout across 157 sub-districts",
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

`id` is assigned at build time; anything you put there is overwritten.

### Vocabularies

Both axes are closed sets — the dashboard's matrix is built from them, so a new
value needs adding to `tools/build_dashboard.py` and to the `TOPICS` /
`OUTCOMES` arrays in `tools/templates/body.html`.

**Topics** — `broadband`, `devices`, `ixp`, `datacenters`, `cloud`, `dpi`,
`skills`, `transformation`, `ai`, `cyber`, `datagov`

**Outcomes** — `growth`, `labor`, `firms`, `welfare`, `inclusion`, `govt`,
`humancap`, `environment`

A study can carry several of each; it then appears in every matching cell.

### Grading a study

`tier` is the spine of the repository. Grade it by the identification strategy
the authors actually use, not by how confident the abstract sounds.

| Tier | Use it for |
|---|---|
| `rct` | Randomised controlled trials and field experiments. |
| `quasi` | Difference-in-differences, instrumental variables, regression discontinuity, event studies, synthetic controls. |
| `structural` | Structural, general-equilibrium and task-based models. |
| `descriptive` | Cross-sectional correlations, panel associations, case studies, agency statistics. |
| `review` | Literature reviews, meta-analyses, evidence syntheses. |

Only `rct` and `quasi` count towards the "causally identified" figures on the
page. Putting a correlational study in `quasi` because its finding is
convincing defeats the purpose of the dashboard.

## Conventions worth keeping

- **Magnitudes belong in `findings`.** The page highlights percentages, currency
  amounts, percentage points and standard deviations automatically, so numbers
  written in prose become scannable without extra markup.
- **Link to the definitive version** — the published article where one exists,
  the working paper otherwise.
- **Record null and negative results.** A repository that only holds positive
  findings misrepresents the literature, and the thin cells in the matrix are
  the most useful thing on the page.
