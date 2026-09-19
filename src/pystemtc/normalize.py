"""Normalization to the first time point (Java ``DataSetCore.logratio2``).

Three modes (spec §1.4 of the Java call graph):
- ``"log"``       : log2(v_t / v_0)
- ``"normalize"`` : v_t - v_0
- ``"none_add0"`` : synthetic 0 column added at read time; values kept as-is
                    (Java still runs logratio2 with btakelog=false, i.e.
                    v_t - v_0 where v_0 is the synthetic 0)
"""

from __future__ import annotations

import math

import numpy as np

MODES = ("log", "normalize", "none_add0")


def _log_java(x: float) -> float:
    # Math.log edge cases: log(0) = -Infinity, log(<0) = NaN
    if x > 0:
        return math.log(x)
    if x == 0.0:
        return -math.inf
    return math.nan


def log_ratio(data: np.ndarray, pma: np.ndarray, mode: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (normalized data, pma) copies; inputs are not mutated.

    t0 itself becomes exactly 0.0 (pma unchanged).  If t0 is missing the whole
    rest of the row is marked missing with data +Infinity
    (DataSetCore.java:740-744).  Non-log modes subtract v0 from every cell,
    including cells whose pma is 0 (Java does the same; those values are
    masked everywhere downstream).
    """
    if mode not in MODES:
        raise ValueError(f"unknown normalize mode: {mode!r}")

    data = np.array(data, dtype=np.float64, copy=True)
    pma = np.array(pma, dtype=np.int8, copy=True)
    nrow, numcols = data.shape
    dlog2 = math.log(2)

    for i in range(nrow):
        dnormval = float(data[i, 0])
        data[i, 0] = 0.0
        if pma[i, 0] == 0:
            for j in range(1, numcols):
                data[i, j] = np.inf
                pma[i, j] = 0
        else:
            for j in range(1, numcols):
                if mode == "log":
                    data[i, j] = _log_java(float(data[i, j]) / dnormval) / dlog2
                else:
                    data[i, j] = float(data[i, j]) - dnormval
    return data, pma
