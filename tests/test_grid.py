import itertools
import math
import random
from fractions import Fraction

import pytest

from fixture_table import TABLE
from quakeexplorer.grid import primary_cell, primary_indices, shifted_cell, shifted_indices


@pytest.mark.parametrize("row", TABLE, ids=[r[0] for r in TABLE])
def test_table_cells(row):
    _, lat, lon, _, _, _, grid, shifted = row
    assert primary_cell(lat, lon) == grid
    assert shifted_cell(lat, lon) == shifted


def _oracle_primary(lat: str, lon: str):
    """Independent: exact rational arithmetic, floor via integer division, no Decimal."""
    la, lo = Fraction(lat), Fraction(lon)
    if lo == 180:
        lo = Fraction(-180)
    li = math.floor((la + 90) / 5)
    return min(li, 35), math.floor((lo + 180) / 5)


def _oracle_shifted(lat: str, lon: str):
    la, lo = Fraction(lat), Fraction(lon)
    if lo == 180:
        lo = Fraction(-180)
    return math.floor((la + Fraction(185, 2)) / 5), math.floor((lo + Fraction(365, 2)) / 5) % 72


BOUNDARY_LATS = ["-90", "-89.9999", "-87.5", "-87.4999", "-85", "-0.0001", "0", "0.0001", "2.5", "14.9999",
                 "15", "87.4999", "87.5", "89.9999", "90"]
BOUNDARY_LONS = ["-180", "-179.9999", "-177.5", "-177.4999", "-65.0001", "-65", "-0.0001", "0", "2.5", "177.4999",
                 "177.5", "179.9999", "180"]


@pytest.mark.parametrize("lat,lon", list(itertools.product(BOUNDARY_LATS, BOUNDARY_LONS)))
def test_boundaries_match_exact_oracle(lat, lon):
    la, lo = float(lat), float(lon)
    assert primary_indices(la, lo) == _oracle_primary(lat, lon)
    assert shifted_indices(la, lo) == _oracle_shifted(lat, lon)


def test_random_points_match_exact_oracle():
    rng = random.Random(14)
    for _ in range(2000):
        lat = f"{rng.uniform(-90, 90):.4f}"
        lon = f"{rng.uniform(-180, 180):.4f}"
        assert primary_indices(float(lat), float(lon)) == _oracle_primary(lat, lon)
        assert shifted_indices(float(lat), float(lon)) == _oracle_shifted(lat, lon)


def test_primary_conventions():
    assert primary_cell(90.0, 0.0) == "G35_36"      # +90 inside the top band
    assert primary_cell(-90.0, 0.0) == "G00_36"
    assert primary_cell(0.0, 180.0) == primary_cell(0.0, -180.0) == "G18_00"  # +180 -> -180
    assert primary_cell(14.9999, 0.0) != primary_cell(15.0, 0.0)               # half-open bins
    assert primary_cell(15.0, 0.0) == "G21_36"


def test_shifted_latitude_range_and_short_bands():
    idx = {shifted_indices(lat / 4, 0.0)[0] for lat in range(-360, 361)}
    assert min(idx) == 0 and max(idx) == 36 and len(idx) == 37
    assert shifted_cell(-90.0, 0.0).startswith("S00_")
    assert shifted_cell(-87.5001, 0.0).startswith("S00_") and shifted_cell(-87.5, 0.0).startswith("S01_")
    assert shifted_cell(87.4999, 0.0).startswith("S35_") and shifted_cell(87.5, 0.0).startswith("S36_")
    assert shifted_cell(90.0, 0.0).startswith("S36_")     # +90 inclusive, no clamp


def test_shifted_longitude_wraps_with_seam_at_177_5():
    assert shifted_indices(0, 177.4999)[1] == 71
    assert shifted_indices(0, 177.5)[1] == 0
    assert shifted_indices(0, 180.0)[1] == shifted_indices(0, -180.0)[1] == shifted_indices(0, -177.5001)[1] == 0
    assert shifted_indices(0, -177.5)[1] == 1
    assert {shifted_indices(0, x / 2)[1] for x in range(-360, 360)} == set(range(72))


def test_rejects_out_of_range():
    with pytest.raises(ValueError):
        primary_cell(90.0001, 0.0)
    with pytest.raises(ValueError):
        shifted_cell(0.0, 180.0001)
