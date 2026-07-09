"""Unit test for the reusable island-assignment seam of the ADR-0009 projection probe.

Only the assignment rule is a reusable seam worth pinning (per the probe PRE-REG): a
machine doc is "in" the nearest island iff its PCA-space distance to that island's centroid
is <= the island's own 90th-pct member radius, else "blob/noise" (label -1). Ties -> lowest
island id.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))
from step3_machine_projection import _assign_islands  # noqa: E402


def test_assign_islands_within_and_outside_radius():
    # Two islands in 2D PCA space: island id 3 at origin (radius 1.0), island id 7 at (10,0)
    # (radius 2.0). islands list mirrors the sorted non-noise ids used by the probe.
    islands = [3, 7]
    centroids = np.array([[0.0, 0.0], [10.0, 0.0]])
    radii = np.array([1.0, 2.0])

    pts = np.array(
        [
            [0.5, 0.0],   # inside island 3's ball -> 3
            [2.0, 0.0],   # nearest is island 3 (dist 2.0) but > radius 1.0 -> blob (-1)
            [10.0, 1.5],  # inside island 7's ball (dist 1.5 <= 2.0) -> 7
            [10.0, 3.0],  # nearest island 7, dist 3.0 > radius 2.0 -> blob (-1)
        ]
    )
    label, nearest, dist = _assign_islands(pts, centroids, radii, islands)

    assert label.tolist() == [3, -1, 7, -1]
    assert nearest.tolist() == [3, 3, 7, 7]
    np.testing.assert_allclose(dist, [0.5, 2.0, 1.5, 3.0])


def test_assign_islands_tie_goes_to_lowest_id():
    # Equidistant from both centroids -> argmin picks index 0 == lowest island id (islands
    # are passed sorted, matching the probe).
    islands = [1, 4]
    centroids = np.array([[0.0, 0.0], [4.0, 0.0]])
    radii = np.array([5.0, 5.0])  # both large enough to accept
    pts = np.array([[2.0, 0.0]])  # dist 2.0 to each

    label, nearest, _ = _assign_islands(pts, centroids, radii, islands)
    assert label.tolist() == [1]
    assert nearest.tolist() == [1]
