"""Candidate model profiles and greedy compaction (Java ``STEM_DataSet``).

- ``enumerate_candidates``  : ``generatemodelprofilesall`` (:1004-1029); the
  all-zero profile is dropped afterwards by ``generatemodelprofiles``
  (:780-796), which removes the middle row of the enumeration.  Because
  ``2*max_unit_change+1`` is odd, that middle row is exactly the all-zero
  profile.
- ``sample_candidates``     : ``generatemodelsampled`` (:812-835) with the
  pinned seed 3733246; sample 0 is the strictly descending profile
  ``{0, -u, -2u, ...}`` and consumes no RNG.
- ``compact_profiles2``     : the greedy max-min diversity selection
  (:1561-1711) with ``FLOATERROR = 1e-7`` (:15), the monotone seed profile
  (:1582-1587) and the max|value| tie-break (:1612-1667).

Float discipline (spec §1.5): every cross-column accumulation runs as an
explicit scalar loop in Java's column order.  For candidate sets above
``_BULK_THRESHOLD`` (dispatch is by candidate COUNT, so the *enumeration*
path also takes the bulk branch when it exceeds the threshold) the *same*
per-candidate formulas are additionally evaluated in a vectorized-over-
candidates form (``_compact_profiles2_bulk``); the per-element arithmetic
there is identical (column loop order preserved, elementwise ops only, no
cross-element reductions), and model profile values are integers, so the
cross-column sums are exact in any order — the two implementations produce
bitwise-identical selections (unit-tested).
"""

from __future__ import annotations

import math

import numpy as np

from .rng import JavaRandom


def _java_div(a: float, b: float) -> float:
    """IEEE-754 division as Java defines it (Python raises on b == 0.0);
    needed when a sampled candidate is a constant profile (dsqrty == 0)."""
    if b == 0.0:
        if a == 0.0 or math.isnan(a):
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def _java_sqrt(x: float) -> float:
    """``Math.sqrt``: NaN for negative inputs (Python raises)."""
    if x < 0:
        return math.nan
    return math.sqrt(x)

# STEM_DataSet.java:15
FLOATERROR = 1e-7

# Candidate count above which the vectorized compaction path is used.
_BULK_THRESHOLD = 100_000


def enumerate_candidates(max_unit_change: int, numcols: int) -> list[list[float]]:
    """``generatemodelprofilesall`` (:1004-1029), all-zero row removed.

    Full enumeration: first column always 0, each later column is the
    previous one plus a step in ``[-u, u]`` with the LAST column varying
    fastest.  The removal follows ``generatemodelprofiles`` :780-796
    positionally (rows ``0..len/2-1`` and ``len/2+1..end``), which for the
    odd base ``2u+1`` drops exactly the all-zero row.
    """
    if numcols <= 1:
        raise ValueError("numcols must be >= 2 (Java returns null for GO-only mode)")
    if max_unit_change < 1:
        raise ValueError("max_unit_change must be >= 1 (ST.java:3220-3223)")

    patterns: list[list[float]] = [[0.0]]
    nchoices = 2 * max_unit_change + 1
    for length in range(2, numcols + 1):
        newpatterns: list[list[float]] = []
        for parent in patterns:
            tail = parent[length - 2]
            for step in range(nchoices):
                row = parent[: length - 1] + [tail + step - max_unit_change]
                newpatterns.append(row)
        patterns = newpatterns

    # generatemodelprofiles (:780-796): drop the middle row positionally.
    middle = len(patterns) // 2
    modelprofiles = patterns[:middle] + patterns[middle + 1 :]
    return modelprofiles


def sample_candidates(max_unit_change: int, numcols: int, cap: int) -> list[list[float]]:
    """``generatemodelsampled`` (:812-835) with ``Random(3733246)``.

    Sample 0 is the strictly descending profile ``{0, -u, -2u, ...}`` set
    before the RNG is used; samples 1..cap-1 are random walks whose steps are
    ``Math.floor(nextDouble()*(2u+1) - u)``.
    """
    if numcols <= 1:
        raise ValueError("numcols must be >= 2 (Java returns null for GO-only mode)")
    if max_unit_change < 1:
        raise ValueError("max_unit_change must be >= 1 (ST.java:3220-3223)")
    if cap < 1:
        raise ValueError("cap must be >= 1 (ST.java:3296-3299)")

    nchoices = 2 * max_unit_change + 1
    the_random = JavaRandom(3733246)  # STEM_DataSet.java:816
    next_double = the_random.next_double

    rows = np.empty((cap, numcols), dtype=np.float64)
    first = rows[0]
    first[0] = 0.0
    for nindex in range(1, numcols):
        first[nindex] = first[nindex - 1] - max_unit_change

    row = [0.0] * numcols
    for nsample in range(1, cap):
        value = 0.0
        row[0] = 0.0
        for nindex in range(1, numcols):
            # verbatim expression: Math.floor(nd*(2u+1) - u), STEM_DataSet.java:829-830
            value = value + math.floor(next_double() * nchoices - max_unit_change)
            row[nindex] = value
        rows[nsample] = row

    return [rows[i].tolist() for i in range(cap)]


def compact_profiles2(
    candidates: list[list[float]],
    max_profiles: int,
    max_corr: float,
    max_unit_change: int,
) -> tuple[list[list[float]], list[int]]:
    """Public entry; dispatches between the scalar and the (bitwise-equal)
    vectorized implementation by candidate count."""
    if len(candidates) > _BULK_THRESHOLD:
        return _compact_profiles2_bulk(candidates, max_profiles, max_corr, max_unit_change)
    return _compact_profiles2_scalar(candidates, max_profiles, max_corr, max_unit_change)


def _compact_profiles2_scalar(
    candidates: list[list[float]],
    max_profiles: int,
    max_corr: float,
    max_unit_change: int,
) -> tuple[list[list[float]], list[int]]:
    """Direct port of ``compactprofiles2`` (STEM_DataSet.java:1561-1711).

    Returns ``(models, ids)`` where ``models`` are the selected candidate
    rows re-sorted by candidate index (:1705-1710) and ``ids`` the candidate
    indices (which become the Profile IDs, spec A5).
    """
    modelprofiles = [list(row) for row in candidates]
    numcols = len(modelprofiles[0])
    nprofiles = len(modelprofiles)

    selected = [False] * nprofiles

    dsumy = [0.0] * nprofiles
    dsumysq = [0.0] * nprofiles
    dsqrty = [0.0] * nprofiles
    for nrow in range(nprofiles):
        row = modelprofiles[nrow]
        sy = 0.0
        sysq = 0.0
        for ncol in range(numcols):
            v = row[ncol]
            sy += v
            sysq += v * v
        dsumy[nrow] = sy
        dsumysq[nrow] = sysq
        dsqrty[nrow] = _java_sqrt(sysq - sy * sy / numcols)  # :1551-1552

    # :1574-1579
    dstopval = min(max_corr, 1.5)
    nstopnum = min(nprofiles, max_profiles)
    if nstopnum <= 0:
        nstopnum = nprofiles

    selectedindex = [0] * nstopnum

    # :1582-1587 — the seed index; algebraically the candidate index of the
    # monotone unit-step profile {0, 1, ..., numcols-1}.
    r = 1.0 / (2 * max_unit_change + 1)
    rsum = ((r ** numcols - 1.0) / (r - 1.0)) - 1.0
    ndown = int(nprofiles * (max_unit_change + 1) * rsum)
    selected[ndown] = True

    nsetsize = 1

    if nstopnum > 1:
        selectedindex[0] = ndown

        # :1594-1610 — closestcorr vs the seed profile
        seed = modelprofiles[ndown]
        closestcorr = [0.0] * nprofiles
        for nindex in range(nprofiles):
            dsumxy = 0.0
            row = modelprofiles[nindex]
            for ninnerindex in range(numcols):
                dsumxy += seed[ninnerindex] * row[ninnerindex]
            closestcorr[nindex] = _java_div(
                dsumxy - dsumy[nindex] * dsumy[ndown] / numcols,
                dsqrty[nindex] * dsqrty[ndown],
            )

        # :1612-1626 — max |value| per profile (column 0 taken raw, per source)
        maxrawval = [0.0] * nprofiles
        for nprofile in range(nprofiles):
            row = modelprofiles[nprofile]
            m = row[0]
            for nrawindex in range(1, numcols):
                dtempval = abs(row[nrawindex])
                if dtempval > m:
                    m = dtempval
            maxrawval[nprofile] = m

        # :1628-1695 — greedy rounds
        while True:
            nminindex = -1
            dminval = 2.0  # correlation
            dminmaxabs = float(max_unit_change * numcols)  # :1632
            for nindex in range(nprofiles):
                if not selected[nindex]:
                    btry = True
                    # :1639-1667 — FLOATERROR tie with the current best,
                    # resolved by the smaller max|value| when the two
                    # candidates are (near-)identical profiles
                    if (abs(closestcorr[nindex] - dminval) <= FLOATERROR) and (
                        maxrawval[nindex] < dminmaxabs
                    ):
                        best = modelprofiles[nminindex]
                        cand = modelprofiles[nindex]
                        dsumxy = 0.0
                        for ninnerindex in range(numcols):
                            dsumxy += best[ninnerindex] * cand[ninnerindex]
                        dcorrval = _java_div(
                            dsumxy - dsumy[nindex] * dsumy[nminindex] / numcols,
                            dsqrty[nindex] * dsqrty[nminindex],
                        )

                        if dcorrval + FLOATERROR >= 1:
                            dminval = closestcorr[nindex]
                            nminindex = nindex
                            dminmaxabs = maxrawval[nindex]
                            btry = False

                    if btry and (closestcorr[nindex] < dminval):
                        dminval = closestcorr[nindex]
                        nminindex = nindex
                        dminmaxabs = maxrawval[nindex]

            # :1671-1694 — add condition and closestcorr update
            if (nminindex > -1) and (dminval + FLOATERROR < max_corr):
                selected[nminindex] = True
                selectedindex[nsetsize] = nminindex
                nsetsize += 1
                newest = modelprofiles[nminindex]
                for npindex in range(nprofiles):
                    row = modelprofiles[npindex]
                    dsumxy = 0.0
                    for ninnerindex in range(numcols):
                        dsumxy += newest[ninnerindex] * row[ninnerindex]
                    ddistnew = _java_div(
                        dsumxy - dsumy[nminindex] * dsumy[npindex] / numcols,
                        dsqrty[nminindex] * dsqrty[npindex],
                    )
                    if ddistnew > closestcorr[npindex]:
                        closestcorr[npindex] = ddistnew

            # :1695 — stop condition
            if not ((dminval + FLOATERROR < dstopval) and (nsetsize < nstopnum)):
                break

    # :1703-1710 — re-sort by candidate index; index order = Profile ID order
    chosen = sorted(selectedindex[:nsetsize])
    models = [modelprofiles[i] for i in chosen]
    return models, chosen


def _compact_profiles2_bulk(
    candidates: list[list[float]],
    max_profiles: int,
    max_corr: float,
    max_unit_change: int,
) -> tuple[list[list[float]], list[int]]:
    """Vectorized-over-candidates twin of :func:`_compact_profiles2_scalar`
    for the sampled path (up to millions of candidates).

    Every cross-column accumulation is still an explicit loop over columns in
    Java order, evaluated elementwise across candidates; all other steps are
    elementwise ops on independent per-candidate values.  Model profile
    values are integers, so the cross-column sums are exact, and the
    selection produced is bitwise identical to the scalar port (unit-tested
    in tests/test_units_m2.py).
    """
    P = np.asarray(candidates, dtype=np.float64)
    numcols = P.shape[1]
    nprofiles = P.shape[0]

    # modelprofilestats (:1538-1554), column order preserved per candidate
    dsumy = P[:, 0].copy()
    dsumysq = (P[:, 0] * P[:, 0]).copy()
    for ncol in range(1, numcols):
        dsumy = dsumy + P[:, ncol]
        dsumysq = dsumysq + P[:, ncol] * P[:, ncol]
    with np.errstate(invalid="ignore", divide="ignore"):
        dsqrty = np.sqrt(dsumysq - (dsumy * dsumy) / numcols)

    dstopval = min(max_corr, 1.5)
    nstopnum = min(int(nprofiles), max_profiles)
    if nstopnum <= 0:
        nstopnum = int(nprofiles)

    selectedindex = [0] * nstopnum

    r = 1.0 / (2 * max_unit_change + 1)
    rsum = ((r ** numcols - 1.0) / (r - 1.0)) - 1.0
    ndown = int(nprofiles * (max_unit_change + 1) * rsum)

    selected = np.zeros(nprofiles, dtype=bool)
    selected[ndown] = True
    nsetsize = 1

    if nstopnum > 1:
        selectedindex[0] = ndown

        seed = P[ndown]
        seed_list = seed.tolist()
        # closestcorr vs the seed (:1594-1610)
        dsumxy = P[:, 0] * seed_list[0]
        for ninnerindex in range(1, numcols):
            dsumxy = dsumxy + P[:, ninnerindex] * seed_list[ninnerindex]
        with np.errstate(invalid="ignore", divide="ignore"):
            closestcorr = (dsumxy - (dsumy * dsumy[ndown]) / numcols) / (
                dsqrty * dsqrty[ndown]
            )

        # max |value| (:1612-1626)
        maxrawval = P[:, 0].copy()
        for nrawindex in range(1, numcols):
            maxrawval = np.maximum(maxrawval, np.abs(P[:, nrawindex]))

        cc_list = closestcorr.tolist()
        mr_list = maxrawval.tolist()
        sel_list = selected.tolist()
        dsumy_list = dsumy.tolist()
        dsqrty_list = dsqrty.tolist()

        while True:
            # Sequential scan (:1630-1669) in candidate-index order.
            nminindex = -1
            dminval = 2.0
            dminmaxabs = float(max_unit_change * numcols)
            for nindex in range(nprofiles):
                if not sel_list[nindex]:
                    btry = True
                    cc = cc_list[nindex]
                    if abs(cc - dminval) <= FLOATERROR and mr_list[nindex] < dminmaxabs:
                        best = P[nminindex]
                        cand = P[nindex]
                        dsumxy = 0.0
                        best_list = best.tolist()
                        cand_list = cand.tolist()
                        for ninnerindex in range(numcols):
                            dsumxy += best_list[ninnerindex] * cand_list[ninnerindex]
                        dcorrval = (
                            dsumxy
                            - dsumy_list[nindex] * dsumy_list[nminindex] / numcols
                        ) / (dsqrty_list[nindex] * dsqrty_list[nminindex])
                        if dcorrval + FLOATERROR >= 1:
                            dminval = cc
                            nminindex = nindex
                            dminmaxabs = mr_list[nindex]
                            btry = False
                    if btry and cc < dminval:
                        dminval = cc
                        nminindex = nindex
                        dminmaxabs = mr_list[nindex]

            if (nminindex > -1) and (dminval + FLOATERROR < max_corr):
                selected[nminindex] = True
                sel_list[nminindex] = True
                selectedindex[nsetsize] = nminindex
                nsetsize += 1

                newest = P[nminindex]
                newest_list = newest.tolist()
                # closestcorr update (:1677-1693)
                dsumxy = P[:, 0] * newest_list[0]
                for ninnerindex in range(1, numcols):
                    dsumxy = dsumxy + P[:, ninnerindex] * newest_list[ninnerindex]
                with np.errstate(invalid="ignore", divide="ignore"):
                    ddistnew = (dsumxy - (dsumy * dsumy[nminindex]) / numcols) / (
                        dsqrty * dsqrty[nminindex]
                    )
                # Java: if (ddistnew > closestcorr) closestcorr = ddistnew —
                # NaN comparisons are false on both sides (Java and numpy).
                closestcorr = np.where(ddistnew > closestcorr, ddistnew, closestcorr)
                cc_list = closestcorr.tolist()

            if not ((dminval + FLOATERROR < dstopval) and (nsetsize < nstopnum)):
                break

    chosen = sorted(selectedindex[:nsetsize])
    models = [P[i].tolist() for i in chosen]
    return models, chosen
