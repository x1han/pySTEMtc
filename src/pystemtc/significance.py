"""Profile significance: binomial tail p-values and multiple-testing
correction (``StatUtil.binomialtail`` StatUtil.java:286-336 and
``computePvaluesAssignments`` STEM_DataSet.java:287-335)."""

from __future__ import annotations

import math

# cache for logbinomcoeff (StatUtil.java:16); the cache cannot change values
_logbinom_cache: dict[tuple[int, int], float] = {}


def logbinomcoeff(ni: int, N: int) -> float:
    """``StatUtil.logbinomcoeff`` (StatUtil.java:27-58): the log binomial
    coefficient via the cancelled-factorial sums, in the original loop order:
    first ``sum_{j=dmax+1..N} log j``, then subtract ``sum_{j=2..dmin} log j``
    with ``dmax = max(ni, N-ni)``, ``dmin = min(ni, N-ni)``."""
    key = (ni, N)
    cached = _logbinom_cache.get(key)
    if cached is not None:
        return cached

    dsum = 0.0
    dmax = max(ni, N - ni)
    dmin = min(ni, N - ni)

    nj = dmax + 1
    while nj <= N:
        dsum += math.log(nj)
        nj += 1

    nj = 2
    while nj <= dmin:
        dsum -= math.log(nj)
        nj += 1

    _logbinom_cache[key] = dsum
    return dsum


def binomial_tail(x: int, N: int, dp: float) -> float:
    """``StatUtil.binomialtail`` (StatUtil.java:286-336), boundary semantics
    pinned by spec 03 §1.6:

    - ``x > N`` -> 0.0 (impossible tail; checked BEFORE the increment);
    - ``x < 0`` or ``dp <= 0`` or ``dp >= 1`` -> 1.0 (never significant;
      dp == 1 also returns 1);
    - otherwise ``x`` is incremented and the STRICT tail ``P(X > x_orig)``
      (= P(X >= x_orig + 1)) is summed in log space: first term
      ``log C(x_new, N) + x_new*log(dp) + (N-x_new)*log(1-dp)``, then the
      recurrence ``dterm += log(N-ni+1) - log(ni) + (log dp - log(1-dp))``
      for ``ni = x_new+1 .. N`` with the exact
      ``log(1 + Math.pow(Math.E, diff))`` accumulation shape, finally
      ``exp`` and clamping to [0, 1].

    Quirk kept verbatim: for ``x_orig == N`` the incremented ``x_new = N+1``
    enters the formula with ``log C(N+1, N) = 0`` and ``(N - (N+1))`` — the
    result is a tiny nonzero value, not 0.
    """
    if x > N:
        return 0.0
    if (x < 0) or (dp <= 0) or (dp >= 1):
        return 1.0

    x += 1  # :297
    dterm = logbinomcoeff(x, N)
    dpv1 = math.log(dp)
    dpv2 = math.log(1.0 - dp)

    dterm += x * dpv1 + (N - x) * dpv2

    dlogprob = dterm
    dpdiff = dpv1 - dpv2
    for ni in range(x + 1, N + 1):
        dterm += math.log(N - ni + 1) - math.log(ni) + dpdiff

        if dterm >= dlogprob:
            dlogprob = dterm + math.log(1 + math.pow(math.e, dlogprob - dterm))
        else:
            dlogprob = dlogprob + math.log(1 + math.pow(math.e, dterm - dlogprob))

    dprob = math.pow(math.e, dlogprob)

    if dprob <= 0:
        return 0.0
    if dprob >= 1:
        return 1.0
    return dprob


def _int_ceil(dval: float) -> int:
    """``(int) Math.ceil(dval)`` (STEM_DataSet.java:295): NaN casts to 0,
    otherwise truncates the already-integral ceil value."""
    if math.isnan(dval):
        return 0
    return int(math.ceil(dval))


def count_pvalue(count: float, numrows: int, expected_fraction: float) -> float:
    """The p-value of one profile (STEM_DataSet.java:293-295):
    ``binomialtail((int) ceil(count-1), numrows, expected/numrows)``."""
    return binomial_tail(_int_ceil(count - 1), numrows, expected_fraction)


def correct(
    pvals, alpha: float, method: str, counts=None
) -> tuple[list[bool], list[float]]:
    """Multiple-testing correction (STEM_DataSet.java:298-334).

    ``method``: ``"fdr"`` (nfdr=1), ``"bonferroni"`` (nfdr=2) or ``"none"``
    (nfdr=0).  Returns ``(significant_mask, pvalues)``.

    FDR — NOT Benjamini-Hochberg: walk the ascending-sorted p-value copy
    while ``pvalcopy[i] < ((i+1)*alpha)/n`` (multiply-then-divide order),
    ``dthresh`` = last satisfying value (initially 0), then
    ``significant = p <= dthresh`` (<=).

    ⚠ Quirk replicated: if EVERY profile satisfies the walk condition, Java
    reads ``pvalcopy[nprofiles]`` and dies with
    ``ArrayIndexOutOfBoundsException``; this port raises the equivalent
    :class:`IndexError` at that point (the natural out-of-range read on the
    Python list) and must NOT be "fixed".

    Non-FDR: ``dcorrectedalpha = alpha`` (none) or ``alpha/n`` (Bonferroni);
    ``significant = p < dcorrectedalpha AND count > 1`` (strict <,
    :331-332) — hence ``counts`` is required for those methods.
    """
    pvalues = [float(p) for p in pvals]
    nprofiles = len(pvalues)

    if method == "fdr":
        # Arrays.sort double total order: NaN sorts last (reachable when
        # ntotalassignments==0 makes expected NaN and binomialtail NaN)
        pvalcopy = sorted(pvalues, key=lambda v: (math.isnan(v), v))
        npvalindex = 0
        dthresh = 0.0
        # :306-310 — the out-of-range read pvalcopy[nprofiles] when every
        # value qualifies replicates Java's ArrayIndexOutOfBounds crash
        while pvalcopy[npvalindex] < ((npvalindex + 1) * alpha) / nprofiles:
            dthresh = pvalcopy[npvalindex]
            npvalindex += 1

        significant = [p <= dthresh for p in pvalues]
    else:
        if method == "none":
            dcorrectedalpha = alpha
        elif method == "bonferroni":
            dcorrectedalpha = alpha / nprofiles
        else:
            raise ValueError(f"unknown correction method: {method!r}")
        if counts is None:
            raise ValueError("counts are required for non-FDR correction methods")

        significant = [
            (p < dcorrectedalpha) and (c > 1)
            for p, c in zip(pvalues, counts)
        ]

    return significant, pvalues
