"""ARI implementation checks on small, hand-specified partitions. These verify the metric code;
they say nothing about clustering validity on real earthquakes."""

import pytest
from sklearn.metrics import adjusted_rand_score

from quakeexplorer.metrics import (
    adjusted_rand_index,
    ari_both_conventions,
    coverage,
    noise_as_one_group,
    noise_as_singletons,
    partition_ari_both,
)

# Hand-derived (see comments): sums of C(n,2) over contingency cells, rows, columns.


def test_identical_partitions_are_1():
    assert adjusted_rand_index([0, 0, 1, 1, 2], ["a", "a", "b", "b", "c"]) == 1.0


def test_label_names_do_not_matter():
    assert adjusted_rand_index([0, 0, 1, 1], [5, 5, 3, 3]) == 1.0


def test_hand_example_four_over_seven():
    # a=[0,0,1,1], b=[0,0,1,2]: cells 1, rows 2, cols 1, total 6
    # expected = 2*1/6 = 1/3; max = 3/2; ARI = (1-1/3)/(3/2-1/3) = 4/7
    assert adjusted_rand_index([0, 0, 1, 1], [0, 0, 1, 2]) == pytest.approx(4 / 7)


def test_complete_disagreement_example():
    # a splits {0,1}{2,3}; b splits {0,2}{1,3}: cells 0, rows 2, cols 2, total 6
    # expected = 4/6 = 2/3; max = 2; ARI = (0-2/3)/(2-2/3) = -1/2
    assert adjusted_rand_index([0, 0, 1, 1], [0, 1, 0, 1]) == pytest.approx(-0.5)


DB = [0, 0, -1, -1, 1, 1]
GRID = [0, 0, 0, 1, 1, 1]


def test_noise_singleton_convention_three_eighths():
    # db -> A,A,s2,s3,B,B ; cells 2, rows 2, cols 6, total 15
    # expected = 2*6/15 = 4/5; max = 4; ARI = (2-0.8)/(4-0.8) = 0.375
    assert adjusted_rand_index(noise_as_singletons(DB), GRID) == pytest.approx(0.375)


def test_noise_one_group_convention_eight_thirty_thirds():
    # db -> A,A,N,N,B,B ; cells 2, rows 3, cols 6, total 15
    # expected = 3*6/15 = 6/5; max = 4.5; ARI = (2-1.2)/(4.5-1.2) = 8/33
    assert adjusted_rand_index(noise_as_one_group(DB), GRID) == pytest.approx(8 / 33)


def test_both_conventions_helper_and_coverage():
    r = ari_both_conventions(DB, GRID)
    assert r["noise_singleton"] == pytest.approx(0.375) and r["noise_one_group"] == pytest.approx(8 / 33)
    assert coverage(DB) == pytest.approx(4 / 6)


def test_all_noise_conventions_differ_at_the_extremes():
    labels = [-1, -1, -1, -1]
    other = [0, 0, 1, 1]
    # singletons: every event alone; cells 0 rows 0 cols 2 -> expected 0, max 1 -> ARI 0
    assert adjusted_rand_index(noise_as_singletons(labels), other) == pytest.approx(0.0)
    # one group: rows 6, cols 2, total 6, cells 2 -> expected 2; max 4; ARI 0
    assert adjusted_rand_index(noise_as_one_group(labels), other) == pytest.approx(0.0)
    # both all-noise against each other
    assert partition_ari_both(labels, labels) == {"noise_singleton": 1.0, "noise_one_group": 1.0}


def test_trivial_partitions_edge_rule():
    assert adjusted_rand_index([0, 0, 0], [7, 7, 7]) == 1.0
    assert adjusted_rand_index([0, 1, 2], [4, 5, 6]) == 1.0
    assert adjusted_rand_index([0, 0, 0], [0, 1, 2]) == 0.0
    assert adjusted_rand_index([0], [0]) == 1.0


def test_validation_errors():
    with pytest.raises(ValueError):
        adjusted_rand_index([0], [0, 1])
    with pytest.raises(ValueError):
        adjusted_rand_index([], [])


@pytest.mark.parametrize("a,b", [
    ([0, 0, 1, 1, 2, 2, 2], [0, 1, 1, 1, 2, 2, 0]),
    ([0, 1, 2, 0, 1, 2, 0, 1], [0, 0, 0, 1, 1, 1, 2, 2]),
])
def test_matches_scikit_learn(a, b):
    assert adjusted_rand_index(a, b) == pytest.approx(adjusted_rand_score(a, b))
