"""Permutation test for expected profile counts.

Ports ``generatepermutations`` / ``generatepermutationsExcept0``
(STEM_DataSet.java:1403-1521) and ``computeaveragetally`` (:1038-1375),
including its pinned quirks (spec 03 §1.6):

- RNG: one ``Random(9873287)`` created outside the gene loop (:1131).
  ``ballperms`` consumes no RNG; the universe-subsample path consumes
  ``n`` doubles per gene (``floor(nextDouble()*universe)``, then
  ``Arrays.sort`` — sampling WITH replacement, :1158-1168); the on-the-fly
  path consumes ``numcols - npermstart`` doubles per permutation (:1170-1198).
- Re-referencing: the baseline is moved to the permuted time point 0 and the
  per-spot normalized series are re-differenced against it
  (``v[c] - v[nbegin]``, :1237/:1271 — NOT algebraically simplifiable),
  median over spots, then median over the per-repeat medians.  The main set
  is repeat index 0, the repeat files are 1..R, so ``numrepeats = R+1``
  (:1083, :796/:811 in DataSetCore.java).
- Stale buffers: ``logdata`` is only rewritten for columns where some spot is
  present (:1242-1246), and ``davgx``/``dsqrtx``/``numx`` are only recomputed
  when the baseline changes — using the PREVIOUS permutation's pma pattern
  (``permutedpmavalues`` is read before it is overwritten for the current
  permutation, :1296 vs :1312).  Both buffers persist ACROSS genes
  (allocated at :1066-1068, ``nbegin`` reset per row at :1150 but the
  buffers themselves are not).
"""

from __future__ import annotations

import math

import numpy as np

from .rng import JavaRandom

# STEM_DataSet.java:16
ALLPERMSTHRESH = 9


def _java_div(a: float, b: float) -> float:
    """IEEE-754 division as Java defines it (Python raises on b == 0.0)."""
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


def _median_java(vals: list[float]) -> float:
    """``Util.getmedian`` (Util.java:581-595) with Java's ``Arrays.sort``
    double total order: NaN sorts AFTER every other value (and -0.0 before
    0.0).  This matters for the log-normalize mode, where the re-reference
    differences can be NaN/±Infinity at spot level (a spot whose baseline
    cell is missing): Python's ``sorted`` leaves NaN positions
    input-dependent, which would corrupt the median.
    """
    ordered = sorted(vals, key=lambda v: (math.isnan(v), v))
    n = len(ordered)
    if n % 2 == 0:
        return (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    return ordered[n // 2]


def all_permutations(numcols: int, fix_t0: bool) -> np.ndarray:
    """All permutations in Java's enumeration order (Knuth 7.2.1.2 as coded
    at STEM_DataSet.java:1403-1521 — lexicographic).

    ``fix_t0=True``  -> ``generatepermutationsExcept0``: (numcols-1)!
    permutations, column 0 fixed to 0.
    ``fix_t0=False`` -> ``generatepermutations``: numcols! permutations.
    """
    if numcols < 1:
        raise ValueError("numcols must be >= 1")

    if fix_t0:
        numelements = numcols - 1
        out = np.zeros((math.factorial(numelements), numcols), dtype=np.int64)
        if numelements == 0:
            out[0, 0] = 0
            return out
        elements = [i + 1 for i in range(numelements)]
        out[0, 0] = 0
        for nindex in range(numelements):
            out[0, nindex + 1] = nindex + 1
        col_offset = 1
    else:
        numelements = numcols
        out = np.zeros((math.factorial(numelements), numcols), dtype=np.int64)
        elements = list(range(numelements))
        for nindex in range(numelements):
            out[0, nindex] = nindex
        col_offset = 0

    nfact = out.shape[0]
    npermutationnum = 0
    j = numelements - 2
    while j >= 0:
        row = out[npermutationnum]
        for nindex in range(numelements):
            row[nindex + col_offset] = elements[nindex]
        npermutationnum += 1
        if npermutationnum >= nfact:
            break

        j = numelements - 2
        while (j >= 0) and (elements[j] >= elements[j + 1]):
            j -= 1

        if j >= 0:
            l = numelements - 1
            while elements[j] >= elements[l]:
                l -= 1
            elements[j], elements[l] = elements[l], elements[j]
            k = j + 1
            l = numelements - 1
            while k < l:
                elements[k], elements[l] = elements[l], elements[k]
                k += 1
                l -= 1

    return out


def _gene_spot_spans(spot_genes: list[str]) -> list[tuple[int, int]]:
    """(start, end) row span per gene over the flat spot rows; genes appear
    contiguously in gene order (dataset.build_stem_dataset guarantees this,
    mirroring Java's ``genespottimedata`` grouping)."""
    spans: list[tuple[int, int]] = []
    start = 0
    current = spot_genes[0] if spot_genes else None
    for i, g in enumerate(spot_genes):
        if g != current:
            spans.append((start, i))
            start = i
            current = g
    if spot_genes:
        spans.append((start, len(spot_genes)))
    return spans


def expected_counts(
    ds, models: list[list[float]], n_perms: int, permute_t0: bool
) -> tuple[np.ndarray, dict]:
    """``computeaveragetally`` (STEM_DataSet.java:1038-1375).

    Returns ``(expected, metadata)`` where ``expected`` is scaled by
    ``numrows / ntotalassignments`` (:1371-1374) and the metadata carries
    ``permutation_mode`` (``exact`` | ``subsample_universe`` |
    ``on_the_fly``), ``n_permutations_requested`` and
    ``legacy_with_replacement`` per spec 03 §1.6 (round-5 semantics: true
    whenever permutations are drawn with replacement — ``subsample_universe``
    and ``on_the_fly`` — false only for ``exact``).
    """
    numcols = int(ds.gene_data.shape[1])
    numrows = int(ds.gene_data.shape[0])
    nprofiles = len(models)

    if numrows == 0:
        raise ValueError("no genes survived filtering")

    # :1043
    bgenallperms = (numcols < ALLPERMSTHRESH) or (n_perms <= 0)

    expected = [0.0] * nprofiles
    ntotalassignments = 0

    # :1062 modelprofilestats
    dsumy = [0.0] * nprofiles
    dsqrty = [0.0] * nprofiles
    for p, row in enumerate(models):
        sy = 0.0
        sysq = 0.0
        for ncol in range(numcols):
            v = row[ncol]
            sy += v
            sysq += v * v
        dsumy[p] = sy
        dsqrty[p] = _java_sqrt(sysq - sy * sy / numcols)

    # Repeat layout: generepeatspottimedata[nrow] = [main, rep1, ..., repR].
    # It exists only for different-periods repeat runs (DataSetCore.java:783-792).
    repeat_sets = list(ds.repeat_sets) if ds.repeat_sets else []
    numrepeats = len(repeat_sets) + 1  # including the main set (:1083)

    gene_data = ds.gene_data.tolist()
    gene_pma = ds.gene_pma.tolist()
    spot_data = ds.spot_data.tolist()
    spot_pma = ds.spot_pma.tolist()
    # repeat_sets are SpotSets whose per-spot normalized content lives in
    # raw_data/raw_pma (dataset.build_stem_dataset convention); the layout is
    # generepeatspottimedata[nrow][1..R] = the repeat's spot rows
    rep_data = [rs.raw_data.tolist() for rs in repeat_sets]
    rep_pma = [rs.raw_pma.tolist() for rs in repeat_sets]
    spans = _gene_spot_spans(list(ds.spot_genes))
    if len(spans) != numrows:
        raise ValueError("spot row grouping does not match gene rows")

    permutations: np.ndarray | None = None
    permbuffer: list[list[int]] | None = None
    selectedperms: list[int]

    if bgenallperms:
        # :1087-1117 — all permutations materialized
        permutations = all_permutations(numcols, fix_t0=not permute_t0)
        universe = permutations.shape[0]
        nselectedperms = min(n_perms, universe)
        if (nselectedperms <= 0) or (nselectedperms == universe):
            ballperms = True
            selectedperms = list(range(universe))
        else:
            ballperms = False
            selectedperms = [0] * nselectedperms
    else:
        # :1119-1146 — permutations generated on the fly per gene
        ballperms = False
        selectedperms = list(range(n_perms))
        permbuffer = [[0] * numcols for _ in range(n_perms)]  # zero-init slots
        npermstart = 0 if permute_t0 else 1  # :1140-1143
        picked = [False] * (numcols - npermstart)

    # Stale buffers, allocated once and carried across genes (:1066-1069)
    permutedpmavalues = [0] * numcols
    logdata = [0.0] * numcols
    permutedlogdata = [0.0] * numcols
    bestbuf = [0] * nprofiles
    maxspots = max((s1 - s0) for (s0, s1) in spans)
    # re-reference scratch buffer (Java doubles it as needed, :1224-1227);
    # only vals[0:nvalindex] is ever read
    vals = [0.0] * (maxspots + 1)
    repeatvals = [0.0] * numrepeats

    # :1131 — one RNG for the whole run
    the_random = JavaRandom(9873287)
    next_double = the_random.next_double

    # persistent correlation state (recomputed only on renormalization)
    davgx = 0.0
    dsqrtx = 0.0
    numx = 0

    dsumxy_closed = [0.0] * nprofiles
    # profile columns for the closed-form inner loop (column-major)
    profcols = [[models[p][c] for p in range(nprofiles)] for c in range(numcols)]
    # cache of masked profile sums for the Util.correlation fallback,
    # keyed by the permuted pma pattern (bitmask over columns)
    masked_sums_cache: dict[int, tuple[list[float], list[float], int]] = {}

    for nrow in range(numrows):
        nbegin = -1  # :1150
        currpmavalues = gene_pma[nrow]

        if not ballperms:
            if bgenallperms:
                # :1160-1168 — universe subsample with replacement
                for nindex in range(len(selectedperms)):
                    selectedperms[nindex] = int(next_double() * permutations.shape[0])
                selectedperms.sort()
            else:
                # :1170-1198 — on-the-fly permutation generation
                for nindex in range(len(selectedperms)):
                    curr = permbuffer[nindex]
                    for njindex in range(numcols - npermstart):
                        picked[njindex] = False
                    for njindex in range(npermstart, numcols):
                        # nmove ~ uniform over [0, numcols-nj)
                        nmove = int(math.floor((numcols - njindex) * next_double()))
                        nkindex = 0
                        ncount = 0
                        while (ncount < nmove) or (picked[nkindex]):
                            if not picked[nkindex]:
                                ncount += 1
                            nkindex += 1
                        picked[nkindex] = True
                        curr[njindex] = nkindex + npermstart

        for npermutationnum in range(len(selectedperms)):
            if bgenallperms:
                currperm = permutations[selectedperms[npermutationnum]].tolist()
            else:
                currperm = permbuffer[npermutationnum]

            if currpmavalues[currperm[0]] != 0:  # :1207
                if nbegin != currperm[0]:
                    # renormalize to the new baseline (:1210-1305)
                    nbegin = currperm[0]

                    if not repeat_sets:
                        # single data set (:1216-1247)
                        s0, s1 = spans[nrow]
                        for ncol in range(numcols):
                            nvalindex = 0
                            for nspot in range(s0, s1):
                                if spot_pma[nspot][ncol] != 0:
                                    vals[nvalindex] = (
                                        spot_data[nspot][ncol]
                                        - spot_data[nspot][nbegin]
                                    )
                                    nvalindex += 1
                            if nvalindex > 0:
                                logdata[ncol] = _median_java(vals[:nvalindex])
                    else:
                        # repeats: per-repeat spot median, then median over
                        # the repeat medians (:1250-1288)
                        s0, s1 = spans[nrow]
                        for ncol in range(numcols):
                            nrepeatvalsindex = 0
                            for nrepeat in range(numrepeats):
                                if nrepeat == 0:
                                    rdata, rpma = spot_data, spot_pma
                                else:
                                    rdata, rpma = rep_data[nrepeat - 1], rep_pma[nrepeat - 1]
                                nvalindex = 0
                                for nspot in range(s0, s1):
                                    if rpma[nspot][ncol] != 0:
                                        vals[nvalindex] = (
                                            rdata[nspot][ncol] - rdata[nspot][nbegin]
                                        )
                                        nvalindex += 1
                                if nvalindex > 0:
                                    repeatvals[nrepeatvalsindex] = _median_java(
                                        vals[:nvalindex]
                                    )
                                    nrepeatvalsindex += 1
                            if nrepeatvalsindex > 0:
                                logdata[ncol] = _median_java(
                                    repeatvals[:nrepeatvalsindex]
                                )

                    # :1291-1305 — stats over the STALE permutedpmavalues
                    davgx = 0.0
                    dsumxsq = 0.0
                    numx = 0
                    for ncol in range(numcols):
                        if permutedpmavalues[ncol] != 0:
                            numx += 1
                            davgx += logdata[ncol]
                            dsumxsq += logdata[ncol] * logdata[ncol]
                    dsqrtx = _java_sqrt(
                        dsumxsq - _java_div(davgx * davgx, numx)
                    )
                    davgx = _java_div(davgx, numx)

                # :1308-1313 — permute the series and the pma pattern
                for ncol in range(numcols):
                    permutedlogdata[ncol] = logdata[currperm[ncol]]
                    permutedpmavalues[ncol] = currpmavalues[currperm[ncol]]

                numbest = 0
                dcorrmax = -2.0

                if numx == numcols:
                    # closed-form path (:1324-1334) — unmasked sums, computed
                    # per (column, profile) in the same accumulation order as
                    # Java's (profile-outer, column-inner) loop
                    for p in range(nprofiles):
                        dsumxy_closed[p] = 0.0
                    for ncol in range(numcols):
                        xv = permutedlogdata[ncol]
                        col = profcols[ncol]
                        for p in range(nprofiles):
                            dsumxy_closed[p] += xv * col[p]
                    for p in range(nprofiles):
                        dcorr = _java_div(
                            dsumxy_closed[p] - davgx * dsumy[p], dsqrtx * dsqrty[p]
                        )
                        if dcorr == dcorrmax:
                            bestbuf[numbest] = p
                            numbest += 1
                        elif dcorr > dcorrmax:
                            bestbuf[0] = p
                            numbest = 1
                            dcorrmax = dcorr
                else:
                    # masked Util.correlation path (:1336-1340); the masked
                    # profile sums are integers, so the cached column-order
                    # sums equal the values Util.correlation recomputes
                    maskbits = 0
                    for ncol in range(numcols):
                        if permutedpmavalues[ncol] != 0:
                            maskbits |= 1 << ncol
                    cached = masked_sums_cache.get(maskbits)
                    if cached is None:
                        msumy = [0.0] * nprofiles
                        msumysq = [0.0] * nprofiles
                        nmask = 0
                        for ncol in range(numcols):
                            if permutedpmavalues[ncol] != 0:
                                nmask += 1
                                col = profcols[ncol]
                                for p in range(nprofiles):
                                    v = col[p]
                                    msumy[p] += v
                                    msumysq[p] += v * v
                        cached = (msumy, msumysq, nmask)
                        masked_sums_cache[maskbits] = cached
                    msumy, msumysq, nmask = cached

                    # x-side sums (Util.java:440-451 accumulation order)
                    dsumx = 0.0
                    dsumxsq_x = 0.0
                    for ncol in range(numcols):
                        if permutedpmavalues[ncol] != 0:
                            xv = permutedlogdata[ncol]
                            dsumx += xv
                            dsumxsq_x += xv * xv
                    dvarx = dsumxsq_x - dsumx * dsumx / nmask
                    for p in range(nprofiles):
                        dvary = msumysq[p] - msumy[p] * msumy[p] / nmask
                        if dvarx * dvary == 0:
                            dcorr = 0.0
                        else:
                            # dsumxy over the masked columns, Java order
                            dsumxy = 0.0
                            for ncol in range(numcols):
                                if permutedpmavalues[ncol] != 0:
                                    dsumxy += permutedlogdata[ncol] * models[p][ncol]
                            dcorr = _java_div(
                                dsumxy - dsumx * msumy[p] / nmask,
                                _java_sqrt(dvarx * dvary),
                            )
                        if dcorr == dcorrmax:
                            bestbuf[numbest] = p
                            numbest += 1
                        elif dcorr > dcorrmax:
                            bestbuf[0] = p
                            numbest = 1
                            dcorrmax = dcorr

                if numbest > 0:  # :1356-1365
                    ntotalassignments += 1
                    dweight = 1.0 / numbest
                    for nindex in range(numbest):
                        expected[bestbuf[nindex]] += dweight

    # :1371-1374 — verbatim evaluation order: (expected * numrows) / ntotal
    for nindex in range(nprofiles):
        expected[nindex] = _java_div(expected[nindex] * numrows, ntotalassignments)

    if ballperms:
        mode = "exact"
    elif bgenallperms:
        mode = "subsample_universe"
    else:
        mode = "on_the_fly"

    meta = {
        "permutation_mode": mode,
        "n_permutations_requested": n_perms,
        # on_the_fly draws each permutation independently, so repeats across
        # permutations are possible there too — sampling is with replacement
        # for every mode except exact (round-5 review, spec 03 §1.7).
        "legacy_with_replacement": mode != "exact",
    }
    return np.asarray(expected, dtype=np.float64), meta
