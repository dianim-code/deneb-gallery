# Decision log

Architecture decisions in a light ADR format: **context → decision → trade-offs**. ADR numbers are
shared with the `healthcare-lakehouse` and `healthcare-semantic-model` repositories. Decisions about
the data itself (sources, contract design, licensing) live in `healthcare-lakehouse/docs/decisions.md`.

---

## ADR-001 · Consume the gold contract as a vendored copy

*2026-11-10 · Accepted*

**Decision.** Templates and gallery are built on the gold contract owned by `healthcare-lakehouse`.
This repo keeps a read-only copy in `contract/` and `sample-data/gold/` (see
`contract/VENDORED.md`). The Pages workflow publishes `site/` together with these CSVs under
`data/`.

**Trade-offs.** The gallery has no runtime dependency on other repositories. A contract change has
to be re-vendored from the lakehouse.

## ADR-005 · Language and licensing

*2026-11-10 · Accepted*

**Decision.** Code, templates and docs are in English, under the **MIT** license. Data values stay
in Italian as published. The sample data keeps its own licenses, with attribution in
`contract/VENDORED.md`. The gallery page has to show the same attribution.

## ADR-008 · Deneb chart set

*2026-11-10 · Accepted*

**Decision.** Bullet chart, small multiples by region, year-over-year slope chart, heatmap by
discipline, plus a dumbbell chart and a ranked bar with a reference line.

## ADR-009 · GitHub Pages as a project site of this repository

*2026-11-10 · Accepted*

**Decision.** The gallery is published as the project site of this repository, so the URL becomes
`https://dianim-code.github.io/deneb-gallery/` instead of the `.../dianim-code/` planned for the
monorepo. Use relative paths only in `site/`.

---

## Open items to verify

Resolved by ADR-010 and ADR-011. Items that could not be verified stay listed in ADR-014.

| Item | Status |
|---|---|
| The Vega-Lite version bundled by the current Deneb release, and the `usermeta` template format | Resolved, see ADR-010 and ADR-011 |

## ADR-010 · Deneb template format (usermeta v2)

*2026-11-10 · Accepted*

**Context.** A Deneb template is a Vega-Lite (or Vega) spec with a `usermeta` object. The format changed in Deneb 2.0 (metaVersion 2).

**Decision.** Each `templates/<name>/template.json` follows the v2 format, checked against the official schema:

- Top level: `$schema` (removed by Deneb on import), the spec, and `usermeta`. The spec's data is `{"name": "dataset"}`.
- `usermeta.deneb`: `build`, `metaVersion` 2, `provider` `vegaLite`, `providerVersion` `6.4.3`.
- `usermeta.information`: `name`, `description`, `author`, `uuid` (version-4 shape), `generated`.
- `usermeta.datasets.dataset`: one entry per field with `key` (`__dataset.<i>__`), `name`, `kind` (`column`), `type` (`text`, `numeric`).
- `usermeta.interactivity`: tooltip on, selection off, `dataPointLimit` 250.
- Import: Deneb visual, advanced editor, Create New Specification, Existing template, import or paste, map each placeholder, Create. The visual needs at least one column or measure first.

**Sources.** [Templates documentation](https://deneb.guide/docs/templates) (structure, placeholders, import and export steps); [usermeta v2 JSON schema](https://deneb.guide/schema/deneb-template-usermeta-v2.json) (served from `deneb-viz.github.io/schema/`, which redirects here); [Deneb changelog](https://deneb.guide/docs/changelog) (v2: `usermeta.datasets` keyed by dataset name); [Deneb repository](https://github.com/deneb-viz/deneb) (`apps/deneb`, the v2 app).

**Verification.** `scripts/validate_specs.py` checks each `usermeta` against the v2 schema and checks that the template, with placeholders reversed to field names, equals `spec.vl.json`.

**Trade-offs.** The placeholder-to-field replacement inside the spec was not confirmed in text: the docs define the placeholder keys and the import flow ("all placeholders filled out as specified"), not how they appear in the spec. The generator puts placeholders in exact field-name positions only. A real Power BI test is still needed (see ADR-014).

## ADR-011 · Pin Vega, Vega-Lite and vega-embed to the Deneb 2.0.1 versions

*2026-11-10 · Accepted*

**Decision.** The gallery loads the same major.minor versions Deneb bundles, from `cdn.jsdelivr.net/npm/` with exact versions:

| Library | Version | Source |
|---|---|---|
| vega | 6.4.0 | `apps/deneb/package.json` at tag `2.0.1.0`, release 2.0.1 of 2026-10-18 (the latest; `main` has the same versions) |
| vega-lite | 6.4.3 | same |
| vega-embed | 7.1.0 | same |

The specs declare `$schema` `https://vega.github.io/schema/vega-lite/v6.4.3.json`, and the validator uses that schema. Previews use vl-convert-python with `vl_version="6.4"` (its bundled Vega-Lite 6.4 line).

**Checked.** The three CDN build files return HTTP 200. `vega-lite` 6.4.3 was published 2026-04-24; npm's `latest` is 6.5.0, which is not used because Deneb does not bundle it.

**Trade-offs.** When Deneb moves to a new release, bump the three versions, the `$schema` URL, the `providerVersion` and the validator schema together, then re-run the build and validator.

## ADR-012 · Flat, pre-aggregated data per template

*2026-11-10 · Accepted*

**Decision.** Each template expects one flat table, as Deneb gives it to the spec: one row per region, year, or discipline and region, with fields named as the template's placeholders. The browser does no joins. `scripts/build_gallery_data.py` builds three JSON files in `site/data/`:

- `regions_2023.json`: region, beds per 1,000, national value (bullet, ranked bar).
- `regions_by_year.json`: region, region order, macro area, year, beds per 1,000, for 2021 to 2023 (small multiples, slope, dumbbell). Years are filtered in the spec.
- `discipline_region_2023.json`: discipline, region, region order, beds per 1,000, for the ten largest disciplines by national ordinary beds (heatmap).

**Metric.** `beds_per_1000` = `beds_ordinary` summed over disciplines / population on 1 January × 1000, same region and year. The national value is the total over regions. Only the ordinary regime is used, because it is the internationally comparable one; the other regimes are excluded from every chart.

**Trade-offs.** Files are KB in size and committed. The build script must be re-run after a data change, and `--check` detects a stale output.

## ADR-013 · Palette, dark mode and charts' colour handling

*2026-11-10 · Accepted*

**Decision.** Three categorical colours, one per macro area: blue `#2a78d6`, orange `#eb6834`, aqua `#1baf7a` (light) and `#3987e5`, `#d95926`, `#199e70` (dark). All pairs stay distinguishable under the common colour-vision deficiencies in both modes. Okabe-Ito was rejected because its colours fall outside a readable lightness range on the dark surface. Light-mode aqua has only 2.74:1 contrast against white, so the slope chart labels its highlighted lines directly and gives every line a tooltip. The heatmap uses the ColorBrewer `blues` single-hue ramp, which is colour-vision-deficiency safe.

Specs are written in light colours. `site/app.js` maps the light hex values to dark steps when the OS is in dark mode, reverses sequential scales, and sets a transparent chart background. Charts re-render on a change of scheme. The Deneb templates keep the light colours (Deneb applies its own theme); this is a known trade-off.

**Trade-offs.** The mapping is a fixed table, not a theme system. A new chart needs its colours added to the table.

*Update 2026-11-11.* A dark-mode check of the six charts found three light colours missing from the table: the slope chart's direct labels `#252423` (nearly invisible on the dark surface), the subtitles `#767676` (low contrast) and the ranked bar's muted bars `#c8c6c4` (as bright as the highlighted bars). They now map to `#e4e3df`, `#9c9b94` and `#5b5a56`. The specs are unchanged, so Power BI is not affected.

## ADR-014 · Publishing, local preview and open verification items

*2026-11-10 · Accepted*

**Decision.** `site/` is self-contained. The build script writes the site copies (`site/templates/<name>/template.json` and `spec.vl.json`, with the data URL rewritten to `data/`), so the Pages workflow publishes `site/` alone. Local preview serves the same directory with `uv run python -m http.server 8000 --directory site`, so the relative paths match GitHub Pages.

**Verified in Power BI Desktop (2026-11-10, `ranked-bar-national-average`).** Imported through Create New
Specification > Existing template on the `healthcare-semantic-model` report, then read back from the saved
PBIR `visual.json`:
- Deneb replaces every `__dataset.N__` in the spec with the display name of the mapped field
  (`region_name`, `Ordinary Beds per 1,000 Residents`, `Ordinary Beds per 1,000 Residents (Italy)`); no
  placeholder is left. `$schema` is removed, `"width": "container"` is kept.
- `usermeta.interactivity` becomes visual properties (tooltips and context menu on, selection and
  highlight off, `selectionMaxDataPoints` 250); the provider version is stored as 6.4.3.
- The values behind the visual (semantic model, DAX) equal the gallery data: Piemonte 3.8421,
  Emilia-Romagna 3.6905, Trento 3.6741, Italy 3.2467, rounded to two decimals in `site/data`.

**Not verified (flagged).**
- The other five templates were not imported through the Deneb dialog; they use the same format and generator. Four of them (slope, dumbbell, small multiples, heatmap) run in the report, applied with the same placeholder substitution; the bullet chart has not run in Power BI.
- The `bandSize` property on bar and tick marks: accepted by the schema but ignored by the renderer, so it is not used.
- Light-mode aqua has low contrast against white (2.74:1, ADR-013).
- Vega-embed logs benign warnings in the browser ("Dropping fit-y because spec has discrete height", and one union-sort notice). The rendered order was checked and is correct.

## ADR-015 · The gallery charts the 20 ISTAT regions

*2026-11-11 · Accepted (contract 1.1.0)*

**Decision.** `scripts/build_gallery_data.py` maps each Ministry region code to `istat_region_name` and
sums beds and population before computing the ratios, so every chart shows the 20 ISTAT regions:
Trentino-Alto Adige instead of the two autonomous provinces. The region order is the lowest Ministry
order of the region. The templates are unchanged: they still expect one row per region.

**Trade-offs.** The provinces of Bolzano and Trento are no longer visible in the gallery. Power BI users
can still bind the Ministry region column if they need them.
