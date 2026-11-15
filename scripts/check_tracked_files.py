"""CI guard: fail if real or derived USGS data is tracked by git.

Real snapshot and derived outputs must stay local while redistribution terms are unresolved.
This is a check on tracked files, not a substitute for .gitignore. A local pre-commit hook may
call it too, but a hook is not reliable enforcement; CI is.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_PREFIXES = (
    "data/",
    "output/",
    "reports/local/",
    "work/",
    "dist/",
    "build/",
    "web/dist/",
    "web/public/data/",
)
# USGS-looking event ids (network prefix + 7-9 alphanumerics with a run of digits), lowercase.
REAL_ID = re.compile(r"\b(?:us|nc|ci|ak|hv|uw|pr|se|nn|ok|tx|av)(?=[0-9a-z]*\d{3})[0-9a-z]{7,9}\b")
SCAN_SUFFIXES = {".json", ".geojson", ".csv", ".md", ".py", ".ts", ".txt", ".yml", ".yaml", ".html", ".toml"}
SKIP_NAMES = {"package-lock.json", "requirements.lock"}
MAX_SCAN_BYTES = 2 * 1024 * 1024
ID_ALLOWANCE = 0  # synthetic fixtures use "fx-" ids; no real-looking id may be tracked


def find_violations(root: Path, tracked: list[str]) -> list[str]:
    problems: list[str] = []
    for rel in tracked:
        norm = rel.replace("\\", "/")
        if norm == ".gitignore" or norm.endswith(".gitkeep"):
            continue
        if any(norm.startswith(p) for p in FORBIDDEN_PREFIXES):
            problems.append(f"tracked path is reserved for local data: {norm}")
            continue
        if norm.endswith(".geojson") and not norm.startswith("fixtures/"):
            problems.append(f"tracked .geojson outside fixtures/: {norm}")
        path = root / norm
        if path.suffix.lower() not in SCAN_SUFFIXES or path.name in SKIP_NAMES or not path.is_file():
            continue
        if path.stat().st_size > MAX_SCAN_BYTES:
            problems.append(f"tracked text file larger than {MAX_SCAN_BYTES} bytes: {norm}")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits = sorted(set(REAL_ID.findall(text)))
        if len(hits) > ID_ALLOWANCE:
            problems.append(f"{norm}: contains {len(hits)} USGS-looking event id(s), e.g. {hits[0]!r}")
    return problems


def git_tracked(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p]


def scan_dir_for_real_data(directory: Path) -> list[str]:
    """Scan a build output (e.g. web/dist) for anything that looks like real USGS data."""
    problems: list[str] = []
    if not directory.is_dir():
        return [f"scan directory does not exist: {directory}"]
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        if path.suffix.lower() not in SCAN_SUFFIXES | {".js", ".css"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if '"dataset_kind":"real"' in text.replace(" ", ""):
            problems.append(f"{path}: contains dataset_kind real")
        hits = sorted(set(REAL_ID.findall(text)))
        if hits:
            problems.append(f"{path}: contains {len(hits)} USGS-looking event id(s), e.g. {hits[0]!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(__file__).resolve().parent.parent
    problems = find_violations(root, git_tracked(root))
    if "--scan-dir" in args:
        problems += scan_dir_for_real_data(Path(args[args.index("--scan-dir") + 1]))
    for p in problems:
        print(f"GUARD FAIL: {p}", file=sys.stderr)
    if problems:
        return 1
    print("tracked-file guard: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
