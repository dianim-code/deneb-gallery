"""Render templates/<name>/preview.png from spec.vl.json, reproducibly.

Uses vl-convert-python with Vega-Lite 6.4 (the version the gallery and Deneb 2.0.0 use).
The data URL is replaced in memory by the rows of site/data/<dataset>.json, so the PNG does
not depend on a running web server. Responsive width ("container") is replaced by a fixed
width for the image only.

Usage (from the project root):
    uv run scripts/render_previews.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import vl_convert as vlc

ROOT = Path(__file__).resolve().parent.parent
PREVIEW_WIDTH = 640
VL_VERSION = "6.4"


def render(folder: Path) -> Path:
    spec = json.loads((folder / "spec.vl.json").read_text(encoding="utf-8"))
    url = spec["data"]["url"]
    data_file = (folder / url).resolve()
    spec["data"] = {"values": json.loads(data_file.read_text(encoding="utf-8"))}
    if spec.get("width") == "container":
        spec["width"] = PREVIEW_WIDTH
    png = vlc.vegalite_to_png(spec, vl_version=VL_VERSION, scale=1.5)
    out = folder / "preview.png"
    out.write_bytes(png)
    return out


def main() -> int:
    for folder in sorted(p for p in (ROOT / "templates").iterdir() if p.is_dir()):
        out = render(folder)
        print(
            f"wrote {out.relative_to(ROOT).as_posix()} ({out.stat().st_size // 1024} KB)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
