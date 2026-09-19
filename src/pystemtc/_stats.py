"""Java-faithful numeric primitives shared by the M1 pipeline.

Summation order and the median rule are replicated from ``Util.java`` so that
float results are bitwise identical to the Java implementation (spec §1.5:
no vectorized-numpy reductions on golden-relevant sums).
"""

from __future__ import annotations

import math
from typing import Sequence


def getmedian(vals: Sequence[float]) -> float:
    """``Util.getmedian`` (Util.java:581-595).

    Sorts ascending; even count takes the mean of the two middle values
    (single ``+`` then ``/2``, in that order), odd count takes the middle.
    """
    s = sorted(vals)
    n = len(s)
    if n % 2 == 0:
        return (s[n // 2 - 1] + s[n // 2]) / 2
    return s[n // 2]


def correlation(
    xvalues: Sequence[float],
    yvalues: Sequence[float],
    includex: Sequence[int],
    includey: Sequence[int],
) -> float:
    """Masked Pearson of ``Util.correlation(x, y, includex, includey)`` (Util.java:481-526).

    Accumulates the five sums in Java's per-index order (dsumx, dsumy,
    dsumxsq, dsumysq, dsumxy); returns 0 when there is no overlapping present
    pair or when ``dvarx * dvary == 0``.
    """
    dsumx = 0.0
    dsumy = 0.0
    dsumxsq = 0.0
    dsumysq = 0.0
    dsumxy = 0.0
    numvalues = 0

    for nindex in range(len(includex)):
        if includex[nindex] != 0 and includey[nindex] != 0:
            xv = xvalues[nindex]
            yv = yvalues[nindex]
            dsumx += xv
            dsumy += yv
            dsumxsq += xv * xv
            dsumysq += yv * yv
            dsumxy += xv * yv
            numvalues += 1

    if numvalues == 0:
        return 0.0

    dvarx = dsumxsq - dsumx * dsumx / numvalues
    dvary = dsumysq - dsumy * dsumy / numvalues

    if dvarx * dvary == 0:
        return 0.0

    # Java Math.sqrt(negative) = NaN (Util.java:468/522); math.sqrt raises.
    product = dvarx * dvary
    droot = math.sqrt(product) if product >= 0 else float("nan")
    return (dsumxy - dsumx * dsumy / numvalues) / droot
