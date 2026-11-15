"""Grid cell assignment using exact decimal arithmetic.

Primary grid: 5x5 degrees, half-open bins, +90 inside the top band, +180 -> -180.
Shifted grid: origin offset +2.5 degrees on both axes (see docs/contract.md, C1).
"""

from __future__ import annotations

from decimal import Decimal

LAT_BINS_PRIMARY = 36
LON_BINS = 72
LAT_BINS_SHIFTED = 37  # indices 0..36; bands 0 and 36 are 2.5 degrees wide
_FIVE = Decimal(5)


def _d(x: float) -> Decimal:
    # repr() is the shortest string that round-trips, i.e. the decimal text the source meant.
    return Decimal(repr(float(x)))


def normalize_lon(lon: float) -> float:
    """+180 is the same meridian as -180; the grid uses -180. Other values unchanged."""
    return -180.0 if lon == 180.0 else lon


def _check(lat: float, lon: float) -> None:
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise ValueError(f"coordinate out of range: lat={lat!r} lon={lon!r}")


def primary_indices(lat: float, lon: float) -> tuple[int, int]:
    _check(lat, lon)
    lat_idx = min(int((_d(lat) + 90) // _FIVE), LAT_BINS_PRIMARY - 1)
    lon_idx = int((_d(normalize_lon(lon)) + 180) // _FIVE)
    return lat_idx, lon_idx


def shifted_indices(lat: float, lon: float) -> tuple[int, int]:
    _check(lat, lon)
    lat_idx = int((_d(lat) + Decimal("92.5")) // _FIVE)
    lon_idx = int((_d(normalize_lon(lon)) + Decimal("182.5")) // _FIVE) % LON_BINS
    return lat_idx, lon_idx


def primary_cell(lat: float, lon: float) -> str:
    la, lo = primary_indices(lat, lon)
    return f"G{la:02d}_{lo:02d}"


def shifted_cell(lat: float, lon: float) -> str:
    la, lo = shifted_indices(lat, lon)
    return f"S{la:02d}_{lo:02d}"
