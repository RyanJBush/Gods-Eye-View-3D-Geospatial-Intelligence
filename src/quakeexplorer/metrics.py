"""Partition-agreement metrics (descriptive; not accuracy)."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from math import comb
from typing import Hashable, Sequence

NOISE = -1


def noise_as_singletons(labels: Sequence[int]) -> list[Hashable]:
    """Primary convention: every noise event is its own group. A convention, not a noise label."""
    return [("noise", i) if lab == NOISE else ("c", lab) for i, lab in enumerate(labels)]


def noise_as_one_group(labels: Sequence[int]) -> list[Hashable]:
    """Secondary convention: all noise events form a single group."""
    return [("noise",) if lab == NOISE else ("c", lab) for lab in labels]


def adjusted_rand_index(a: Sequence[Hashable], b: Sequence[Hashable]) -> float:
    """Adjusted Rand index. Mirrors scikit-learn's edge rule: 1.0 when both partitions are a
    single group or both are all singletons."""
    if len(a) != len(b):
        raise ValueError("partitions must have equal length")
    n = len(a)
    if n == 0:
        raise ValueError("empty partition")
    ka, kb = len(set(a)), len(set(b))
    if (ka == kb == 1) or (ka == kb == n):
        return 1.0
    cells = Counter(zip(a, b))
    sum_cells = sum(comb(v, 2) for v in cells.values())
    sum_a = sum(comb(v, 2) for v in Counter(a).values())
    sum_b = sum(comb(v, 2) for v in Counter(b).values())
    total = comb(n, 2)
    expected = Fraction(sum_a * sum_b, total)
    mean = Fraction(sum_a + sum_b, 2)
    denominator = mean - expected
    if denominator == 0:
        return 0.0
    return float((sum_cells - expected) / denominator)


def ari_both_conventions(dbscan_labels: Sequence[int], other: Sequence[Hashable]) -> dict[str, float]:
    return {
        "noise_singleton": adjusted_rand_index(noise_as_singletons(dbscan_labels), other),
        "noise_one_group": adjusted_rand_index(noise_as_one_group(dbscan_labels), other),
    }


def partition_ari_both(
    labels_a: Sequence[int], labels_b: Sequence[int]
) -> dict[str, float]:
    """ARI between two DBSCAN-style label vectors, applying each noise convention to both."""
    return {
        "noise_singleton": adjusted_rand_index(
            noise_as_singletons(labels_a), noise_as_singletons(labels_b)
        ),
        "noise_one_group": adjusted_rand_index(
            noise_as_one_group(labels_a), noise_as_one_group(labels_b)
        ),
    }


def coverage(labels: Sequence[int]) -> float:
    """Share of events assigned to a non-noise group."""
    return sum(1 for lab in labels if lab != NOISE) / len(labels)
