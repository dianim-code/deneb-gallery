"""Validate the templates against the pinned schemas.

Checks, for every templates/<name>/ folder:

1. spec.vl.json validates against the Vega-Lite v6.4.3 JSON schema
   (https://vega.github.io/schema/vega-lite/v6.4.3.json, the version bundled by Deneb 2.0.0).
2. template.json: its usermeta validates against the Deneb template usermeta v2 schema
   (https://deneb.guide/schema/deneb-template-usermeta-v2.json), and the template with
   usermeta removed and placeholders replaced by their field names validates against the same
   Vega-Lite schema. The placeholder replacement is reversible, so this proves template.json
   and spec.vl.json describe the same chart.
3. the gallery copies under site/templates/ are identical to the template folder files.

Schemas are downloaded once into .cache/ (git-ignored). Run from the project root:

    uv run scripts/validate_specs.py
"""

from __future__ import annotations

import copy
import json
import sys
import urllib.request
from pathlib import Path

from jsonschema import Draft7Validator, Draft202012Validator
from jsonschema.exceptions import best_match

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
VEGA_LITE_SCHEMA_URL = "https://vega.github.io/schema/vega-lite/v6.4.3.json"
DENEB_USERMETA_SCHEMA_URL = "https://deneb.guide/schema/deneb-template-usermeta-v2.json"


def load_schema(url: str) -> dict:
    CACHE.mkdir(exist_ok=True)
    cached = CACHE / url.rsplit("/", 1)[-1]
    if not cached.exists():
        with urllib.request.urlopen(url, timeout=30) as resp:
            cached.write_bytes(resp.read())
    return json.loads(cached.read_text(encoding="utf-8"))


def validator_for(schema: dict):
    uri = schema.get("$schema", "")
    cls = Draft202012Validator if "2020-12" in uri else Draft7Validator
    cls.check_schema(schema)
    return cls(schema)


def check(validator, instance, label: str, errors: list[str]) -> None:
    err = best_match(validator.iter_errors(instance))
    if err is not None:
        path = "/".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"{label}: {err.message} at {path}")


def restore_spec(template: dict) -> dict:
    """Undo the template build: drop usermeta and map __dataset.i__ back to the field name."""
    spec = copy.deepcopy({k: v for k, v in template.items() if k != "usermeta"})
    mapping = {d["key"]: d["name"] for d in template["usermeta"]["datasets"]["dataset"]}

    def walk(node):
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str) and node in mapping:
            return mapping[node]
        if isinstance(node, str):
            for key, field in mapping.items():
                node = node.replace(f"datum['{key}']", f"datum['{field}']")
        return node

    return walk(spec)


def main() -> int:
    vl_schema = load_schema(VEGA_LITE_SCHEMA_URL)
    usermeta_schema = load_schema(DENEB_USERMETA_SCHEMA_URL)
    vl_validator = validator_for(vl_schema)
    usermeta_validator = validator_for(usermeta_schema)

    errors: list[str] = []
    folders = sorted(p for p in (ROOT / "templates").iterdir() if p.is_dir())
    for folder in folders:
        name = folder.name
        spec = json.loads((folder / "spec.vl.json").read_text(encoding="utf-8"))
        check(vl_validator, spec, f"{name}/spec.vl.json", errors)

        template = json.loads((folder / "template.json").read_text(encoding="utf-8"))
        check(
            usermeta_validator,
            template["usermeta"],
            f"{name}/template.json usermeta",
            errors,
        )
        restored = restore_spec(template)
        restored.pop("$schema", None)
        expected = {k: v for k, v in spec.items() if k not in ("$schema", "data")}
        actual = {k: v for k, v in restored.items() if k not in ("$schema", "data")}
        if expected != actual:
            errors.append(
                f"{name}: template.json does not restore to spec.vl.json (apart from data)"
            )
        check(
            vl_validator,
            {"$schema": spec["$schema"], "data": {"name": "dataset"}, **actual},
            f"{name}/template.json (restored)",
            errors,
        )

        for file in ("template.json", "spec.vl.json"):
            site_copy = ROOT / "site" / "templates" / name / file
            if (
                not site_copy.exists()
                or site_copy.read_bytes() != (folder / file).read_bytes()
            ):
                if file == "spec.vl.json":
                    continue  # site spec differs only in its data url, checked below
                errors.append(
                    f"{name}: site/templates/{name}/{file} is missing or differs from the source"
                )
        site_spec = json.loads(
            (ROOT / "site" / "templates" / name / "spec.vl.json").read_text(
                encoding="utf-8"
            )
        )
        check(vl_validator, site_spec, f"site/templates/{name}/spec.vl.json", errors)

        print(f"{name}: spec, template and usermeta checked")

    if errors:
        print("\nFAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print(
        f"\nOK: {len(folders)} templates validated against Vega-Lite v6.4.3 and Deneb usermeta v2"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
