"""Build the gallery data, the Deneb template files and the site copies.

Reads the vendored gold CSVs in sample-data/gold/ and writes:

- site/data/<dataset>.json        flat, pre-aggregated records, one file per data shape
- templates/<name>/template.json  Deneb template (Vega-Lite spec + usermeta, v2 format)
- site/templates/<name>/          copies published by GitHub Pages (template.json, spec.vl.json)
- site/templates.json             gallery manifest (titles, descriptions, README links)

Metric: ordinary beds per 1,000 residents = beds_ordinary / population * 1000, same region and
year, all disciplines. Beds are active on 1 January, population is on 1 January.

Usage (from the project root):
    uv run scripts/build_gallery_data.py           # write all outputs
    uv run scripts/build_gallery_data.py --check   # exit 1 if any output is stale
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "sample-data" / "gold"
SITE = ROOT / "site"
TEMPLATES = ROOT / "templates"
REPO_URL = "https://github.com/dianim-code/deneb-gallery"
VEGA_LITE_SCHEMA = "https://vega.github.io/schema/vega-lite/v6.4.3.json"
GENERATED = "2026-11-10T00:00:00Z"
TOP_DISCIPLINES = 10
FOCUS_YEAR = 2023

# Each template declares the flat table it expects. Field i becomes the placeholder __dataset.i__.
# (field name, Deneb type, description)
TEMPLATES_META = {
    "bullet-beds-per-1000": {
        "title": "Bullet chart: beds per 1,000 residents",
        "description": "Ordinary beds per 1,000 residents by region against the national value, one bar per region with a national tick.",
        "data": "regions_2023",
        "fields": [
            ("region_name", "text", "Region or autonomous province"),
            (
                "beds_per_1000",
                "numeric",
                "Ordinary beds per 1,000 residents, region, 2023",
            ),
            (
                "national_per_1000",
                "numeric",
                "Ordinary beds per 1,000 residents, Italy, 2023",
            ),
        ],
    },
    "ranked-bar-national-average": {
        "title": "Ranked bar with national average",
        "description": "Regions ranked by ordinary beds per 1,000 residents, with a dashed reference line at the national average.",
        "data": "regions_2023",
        "fields": [
            ("region_name", "text", "Region or autonomous province"),
            (
                "beds_per_1000",
                "numeric",
                "Ordinary beds per 1,000 residents, region, 2023",
            ),
            (
                "national_per_1000",
                "numeric",
                "Ordinary beds per 1,000 residents, Italy, 2023",
            ),
        ],
    },
    "small-multiples-region-trend": {
        "title": "Small multiples by region",
        "description": "One mini line chart per region showing ordinary beds per 1,000 residents from 2021 to 2023, with an independent y scale per panel.",
        "data": "regions_by_year",
        "fields": [
            ("region_name", "text", "Region or autonomous province"),
            (
                "region_order",
                "numeric",
                "Ministry display order of the region (sort key)",
            ),
            ("year", "numeric", "Reference year (1 January)"),
            (
                "beds_per_1000",
                "numeric",
                "Ordinary beds per 1,000 residents, region and year",
            ),
        ],
    },
    "slope-chart-yoy": {
        "title": "Year-over-year slope chart",
        "description": "Ordinary beds per 1,000 residents from 2022 to 2023 for each region, one line per region coloured by macro area.",
        "data": "regions_by_year",
        "fields": [
            ("region_name", "text", "Region or autonomous province"),
            ("macro_area", "text", "Three-way macro area (Nord, Centro, Sud e Isole)"),
            ("year", "numeric", "Reference year (1 January)"),
            (
                "beds_per_1000",
                "numeric",
                "Ordinary beds per 1,000 residents, region and year",
            ),
        ],
    },
    "dumbbell-2021-2023": {
        "title": "Dumbbell chart: 2021 vs 2023",
        "description": "For each region, the ordinary beds per 1,000 residents in 2021 and 2023 joined by a line, so the change is visible at a glance.",
        "data": "regions_by_year",
        "fields": [
            ("region_name", "text", "Region or autonomous province"),
            (
                "region_order",
                "numeric",
                "Ministry display order of the region (sort key)",
            ),
            ("year", "numeric", "Reference year (1 January)"),
            (
                "beds_per_1000",
                "numeric",
                "Ordinary beds per 1,000 residents, region and year",
            ),
        ],
    },
    "heatmap-discipline-region": {
        "title": "Heatmap: discipline by region",
        "description": "Ordinary beds per 1,000 residents for the ten largest disciplines (by national ordinary beds) across all regions, 2023.",
        "data": "discipline_region_2023",
        "fields": [
            ("discipline_name", "text", "Hospital discipline (Ministry name)"),
            ("region_name", "text", "Region or autonomous province"),
            (
                "region_order",
                "numeric",
                "Ministry display order of the region (sort key)",
            ),
            (
                "beds_per_1000",
                "numeric",
                "Ordinary beds per 1,000 residents, discipline and region, 2023",
            ),
        ],
    },
}


def load_gold() -> dict[str, pd.DataFrame]:
    return {
        "beds": pd.read_csv(
            GOLD / "fact_hospital_beds.csv",
            dtype={"discipline_code": str, "region_code": str},
        ),
        "pop": pd.read_csv(GOLD / "fact_population.csv", dtype={"region_code": str}),
        "region": pd.read_csv(
            GOLD / "dim_region.csv", dtype={"region_code": str, "sort_order": int}
        ),
        "discipline": pd.read_csv(
            GOLD / "dim_discipline.csv", dtype={"discipline_code": str}
        ),
    }


def to_rows(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    return json.loads(df[cols].to_json(orient="records", force_ascii=False))


def build_datasets(gold: dict[str, pd.DataFrame]) -> dict[str, list[dict]]:
    beds, pop, region = gold["beds"], gold["pop"], gold["region"]

    # Contract 1.1.0: chart the 20 ISTAT regions. The two autonomous provinces share
    # istat_region_name (Trentino-Alto Adige); beds and population are summed before any ratio.
    code_to_istat = dict(zip(region["region_code"], region["istat_region_name"]))
    beds = beds.assign(region_code=beds["region_code"].map(code_to_istat))
    pop = (
        pop.assign(region_code=pop["region_code"].map(code_to_istat))
        .groupby(["year", "region_code"], as_index=False)["population"]
        .sum()
    )
    region = region.groupby("istat_region_name", as_index=False).agg(
        sort_order=("sort_order", "min"), macro_area=("macro_area", "first")
    )
    region["region_code"] = region["istat_region_name"]
    region["region_name"] = region["istat_region_name"]

    # Region-year ordinary beds joined to population (same year, same region).
    ry = beds.groupby(["year", "region_code"], as_index=False)["beds_ordinary"].sum()
    ry = ry.merge(pop, on=["year", "region_code"], how="outer", indicator=True)
    assert (ry["_merge"] == "both").all(), (
        "beds and population do not join one-to-one by year and region"
    )
    ry = ry.drop(columns="_merge").merge(
        region[["region_code", "region_name", "sort_order", "macro_area"]],
        on="region_code",
    )
    assert ry.groupby("year")["region_code"].nunique().eq(20).all(), (
        "expected 20 ISTAT regions per year"
    )
    ry["beds_per_1000"] = (ry["beds_ordinary"] / ry["population"] * 1000).round(2)
    ry = ry.rename(columns={"sort_order": "region_order"})

    # National value per year: total ordinary beds over total population.
    nat = (
        beds.groupby("year", as_index=False)["beds_ordinary"]
        .sum()
        .merge(pop.groupby("year", as_index=False)["population"].sum(), on="year")
    )
    nat["national_per_1000"] = (nat["beds_ordinary"] / nat["population"] * 1000).round(
        2
    )
    ry = ry.merge(nat[["year", "national_per_1000"]], on="year")

    focus = ry[ry["year"] == FOCUS_YEAR].sort_values("region_order")
    regions_2023 = to_rows(focus, ["region_name", "beds_per_1000", "national_per_1000"])

    by_year = ry[ry["year"].between(2021, 2023)].sort_values(["region_order", "year"])
    regions_by_year = to_rows(
        by_year, ["region_name", "region_order", "macro_area", "year", "beds_per_1000"]
    )

    # Discipline x region for the focus year, top disciplines by national ordinary beds.
    disc = gold["discipline"][["discipline_code", "discipline_name"]]
    b_focus = beds[beds["year"] == FOCUS_YEAR]
    top = (
        b_focus.groupby("discipline_code", as_index=False)["beds_ordinary"]
        .sum()
        .sort_values(["beds_ordinary", "discipline_code"], ascending=[False, True])
        .head(TOP_DISCIPLINES)
        .merge(disc, on="discipline_code")
    )
    dr = b_focus.groupby(["discipline_code", "region_code"], as_index=False)[
        "beds_ordinary"
    ].sum()
    dr = dr.merge(top[["discipline_code", "discipline_name"]], on="discipline_code")
    dr = dr.merge(
        pop[pop["year"] == FOCUS_YEAR][["region_code", "population"]],
        on="region_code",
        how="left",
    )
    assert dr["population"].notna().all(), (
        "missing population for a discipline-region pair"
    )
    dr = dr.merge(
        region[["region_code", "region_name", "sort_order"]], on="region_code"
    )
    dr["beds_per_1000"] = (dr["beds_ordinary"] / dr["population"] * 1000).round(2)
    dr = dr.rename(columns={"sort_order": "region_order"}).sort_values(
        ["region_order", "discipline_name"]
    )
    discipline_region = to_rows(
        dr, ["discipline_name", "region_name", "region_order", "beds_per_1000"]
    )

    return {
        "regions_2023": regions_2023,
        "regions_by_year": regions_by_year,
        "discipline_region_2023": discipline_region,
    }


def stable_uuid(name: str) -> str:
    """Deterministic version-4 shaped UUID (the v2 usermeta schema requires version 4 and RFC variant)."""
    h = hashlib.sha256(name.encode("utf-8")).hexdigest()
    variant = "89ab"[int(h[16], 16) % 4]
    return f"{h[0:8]}-{h[8:12]}-4{h[13:16]}-{variant}{h[17:20]}-{h[20:32]}"


def replace_strings(node, mapping: dict[str, str]):
    """Replace string values that exactly equal a field name (never keys, never titles)."""
    if isinstance(node, dict):
        return {k: replace_strings(v, mapping) for k, v in node.items()}
    if isinstance(node, list):
        return [replace_strings(v, mapping) for v in node]
    if isinstance(node, str) and node in mapping:
        return mapping[node]
    if isinstance(node, str):
        # Field references inside expressions, written as datum['field'] (Deneb fills placeholders in any string).
        for field, key in mapping.items():
            node = node.replace(f"datum['{field}']", f"datum['{key}']")
    return node


def make_template(name: str, meta: dict, spec: dict) -> dict:
    fields = meta["fields"]
    mapping = {field: f"__dataset.{i}__" for i, (field, _, _) in enumerate(fields)}
    body = replace_strings({k: v for k, v in spec.items() if k != "$schema"}, mapping)
    body["data"] = {"name": "dataset"}
    usermeta = {
        "deneb": {
            "build": "2.0.0",
            "metaVersion": 2,
            "provider": "vegaLite",
            "providerVersion": "6.4.3",
        },
        "information": {
            "name": meta["title"][:100],
            "description": meta["description"][:300],
            "author": "deneb-gallery project",
            "uuid": stable_uuid(name),
            "generated": GENERATED,
        },
        "datasets": {
            "dataset": [
                {
                    "key": f"__dataset.{i}__",
                    "name": field,
                    "description": desc,
                    "kind": "column",
                    "type": ftype,
                }
                for i, (field, ftype, desc) in enumerate(fields)
            ]
        },
        "interactivity": {
            "tooltip": True,
            "contextMenu": True,
            "contextMenuSelector": True,
            "selection": False,
            "highlight": False,
            "dataPointLimit": 250,
        },
    }
    return {"$schema": VEGA_LITE_SCHEMA, **body, "usermeta": usermeta}


def serialise(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def build_outputs() -> dict[Path, str]:
    datasets = build_datasets(load_gold())
    outputs: dict[Path, str] = {}

    for ds, rows in datasets.items():
        outputs[SITE / "data" / f"{ds}.json"] = (
            json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n"
        )

    manifest = []
    for name, meta in TEMPLATES_META.items():
        spec_path = TEMPLATES / name / "spec.vl.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        rows = datasets[meta["data"]]
        present = set(rows[0].keys())
        missing = [f for f, _, _ in meta["fields"] if f not in present]
        assert not missing, f"{name}: fields not in dataset {meta['data']}: {missing}"

        template = make_template(name, meta, spec)
        outputs[TEMPLATES / name / "template.json"] = serialise(template)

        data_url_src = f"../../site/data/{meta['data']}.json"
        data_url_site = f"data/{meta['data']}.json"
        assert spec["data"]["url"] == data_url_src, (
            f"{name}: spec data url must be {data_url_src}"
        )
        site_spec = json.loads(json.dumps(spec).replace(data_url_src, data_url_site))
        outputs[SITE / "templates" / name / "template.json"] = serialise(template)
        outputs[SITE / "templates" / name / "spec.vl.json"] = serialise(site_spec)

        manifest.append(
            {
                "id": name,
                "title": meta["title"],
                "description": meta["description"],
                "readme": f"{REPO_URL}/blob/main/templates/{name}/README.md",
                "template": f"templates/{name}/template.json",
                "spec": f"templates/{name}/spec.vl.json",
            }
        )
    outputs[SITE / "templates.json"] = serialise(manifest)
    return outputs


def main() -> int:
    check = "--check" in sys.argv
    outputs = build_outputs()
    stale = []
    for path, text in outputs.items():
        rel = path.relative_to(ROOT).as_posix()
        if check:
            if not path.exists() or path.read_bytes().decode("utf-8") != text:
                stale.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
            print(f"wrote {rel}")
    if check:
        if stale:
            print("stale outputs (run scripts/build_gallery_data.py):")
            for s in stale:
                print(" ", s)
            return 1
        print(f"{len(outputs)} outputs up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
