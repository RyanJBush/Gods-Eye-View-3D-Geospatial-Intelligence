"""Regenerate fixtures/synthetic_usgs.geojson from the reviewed fixture table (synthetic only)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from fixture_builder import table_geojson_bytes  # noqa: E402

target = ROOT / "fixtures" / "synthetic_usgs.geojson"
target.parent.mkdir(exist_ok=True)
target.write_bytes(table_geojson_bytes())
print(f"wrote {target}")
