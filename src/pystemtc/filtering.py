"""Filtering and duplicate/repeat aggregation (M1 chain stages 3-9 of ST.java:2695-2791)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ._stats import correlation, getmedian


@dataclass
class GeneTable:
    """Gene-level view produced by :func:`merge_duplicates`.

    ``data``/``pma`` are the analysis matrices (one row per dup-merged gene).
    ``spot_data``/``spot_pma`` flatten Java's ``genespottimedata`` over the
    original spot rows: the primary row of a duplicate group holds the
    post-merge median values, duplicate rows hold their pre-merge values
    (Java stores array *references* and overwrites the primary row in place,
    DataSetCore.java:681-720).
    """

    data: np.ndarray  # (n_genes, T) float64
    pma: np.ndarray  # (n_genes, T) int8
    genes: list[str]
    probes: list[str]  # per gene, spot ids joined with ";"
    spot_data: np.ndarray  # (n_spots, T) float64, original row order
    spot_pma: np.ndarray  # (n_spots, T) int8
    spot_genes: list[str]  # gene owning each original spot row
    spot_ids: list[str]


def merge_duplicates(spotset) -> GeneTable:
    """``DataSetCore.averageAndFilterDuplicates`` (DataSetCore.java:641-725).

    ``spotset.raw_data``/``raw_pma`` must hold the *current* (post-
    normalization) values.  Duplicate genes are merged by per-column median
    over present (pma != 0) values; merged pma is the max over the group;
    probe ids are concatenated with ";" in original row order.
    """
    data = np.asarray(spotset.raw_data, dtype=np.float64)
    pma = np.asarray(spotset.raw_pma)
    genes = list(spotset.gene_ids)
    probes = list(spotset.probe_ids)
    nrows, numcols = data.shape

    groups: dict[str, list[int]] = {}
    order: list[int] = []
    for nrow, g in enumerate(genes):
        if g in groups:
            groups[g].append(nrow)
        else:
            groups[g] = []
            order.append(nrow)

    gdata = np.empty((len(order), numcols), dtype=np.float64)
    gpma = np.empty((len(order), numcols), dtype=np.int8)
    spot_data = data.copy()
    spot_pma = pma.copy()
    gprobes: list[str] = []

    d_list = data.tolist()
    p_list = pma.tolist()

    for gi, prow in enumerate(order):
        dups = groups[genes[prow]]
        newprobe = probes[prow]
        for drow in dups:
            newprobe += ";" + probes[drow]
        gprobes.append(newprobe)

        for ncol in range(numcols):
            vals: list[float] = []
            npma = 0
            if p_list[prow][ncol] != 0:
                vals.append(d_list[prow][ncol])
                npma = p_list[prow][ncol]
            for drow in dups:
                if p_list[drow][ncol] != 0:
                    vals.append(d_list[drow][ncol])
                    npma = max(npma, p_list[drow][ncol])
            if vals:
                mval = getmedian(vals)
            else:
                # all-missing column: Java leaves data[nrow][ncol] untouched
                mval = d_list[prow][ncol]
            gdata[gi, ncol] = mval
            gpma[gi, ncol] = npma
            # genespottimedata[gene][0] aliases data[prow]: the primary spot
            # row must show the merged (median / max-pma) content.
            spot_data[prow, ncol] = mval
            spot_pma[prow, ncol] = npma

    return GeneTable(
        data=gdata,
        pma=gpma,
        genes=[genes[p] for p in order],
        probes=gprobes,
        spot_data=spot_data,
        spot_pma=spot_pma,
        spot_genes=list(spotset.gene_ids),
        spot_ids=list(spotset.spot_ids),
    )


def _cellwise_median(data0, pma0, datas, pmas) -> tuple[np.ndarray, np.ndarray]:
    """``DataSetCore.mergeDataSets`` cellwise median (DataSetCore.java:794-828)."""
    nrows, numcols = data0.shape
    merged = np.zeros((nrows, numcols), dtype=np.float64)
    mpma = np.zeros((nrows, numcols), dtype=np.int8)
    d0 = data0.tolist()
    p0 = pma0.tolist()
    dsets = [d.tolist() for d in datas]
    psets = [p.tolist() for p in pmas]

    for nrow in range(nrows):
        for ncol in range(numcols):
            vals: list[float] = []
            npma = 0
            if p0[nrow][ncol] != 0:
                vals.append(d0[nrow][ncol])
                npma = p0[nrow][ncol]
            for k in range(len(dsets)):
                if psets[k][nrow][ncol] != 0:
                    vals.append(dsets[k][nrow][ncol])
                    npma = max(npma, psets[k][nrow][ncol])
            if vals:
                merged[nrow, ncol] = getmedian(vals)
            mpma[nrow, ncol] = npma
    return merged, mpma


def merge_repeats(main, repeats: list, mode: str):
    """Merge the main set with its repeats (DataSetCore.java:772-840).

    ``different_periods``: ``main``/``repeats`` are normalized, dup-merged
    GeneTables (bfullrepeat=true); returns a GeneTable whose cell values are
    the cross-repeat medians and whose spot content is the main set's.
    ``same_period``: ``main``/``repeats`` are raw SpotSets (bfullrepeat=false,
    merge happens BEFORE normalization); returns a merged raw SpotSet.
    """
    if mode == "same_period":
        merged, mpma = _cellwise_median(
            main.raw_data, main.raw_pma, [r.raw_data for r in repeats], [r.raw_pma for r in repeats]
        )
        # duck-typed SpotSet construction to avoid an import cycle
        return type(main)(
            raw_data=merged,
            raw_pma=mpma,
            spot_ids=list(main.spot_ids),
            gene_ids=list(main.gene_ids),
            probe_ids=list(main.probe_ids),
            sample_labels=list(main.sample_labels),
        )
    if mode == "different_periods":
        merged, mpma = _cellwise_median(
            main.data, main.pma, [r.data for r in repeats], [r.pma for r in repeats]
        )
        return GeneTable(
            data=merged,
            pma=mpma,
            genes=list(main.genes),
            probes=list(main.probes),
            spot_data=main.spot_data,
            spot_pma=main.spot_pma,
            spot_genes=list(main.spot_genes),
            spot_ids=list(main.spot_ids),
        )
    raise ValueError(f"unknown repeat mode: {mode!r}")


def repeat_correlation_filter(
    main: GeneTable, repeats: list[GeneTable], dmincorrelation: float
) -> tuple[np.ndarray, list[float]]:
    """``DataSetCore.filterdistprofiles`` (DataSetCore.java:848-884).

    Average pairwise correlation over the (R+1)*R/2 main/repeat pairs with
    equal weight 1/npairs; a gene is kept when the average is strictly
    greater than ``dmincorrelation``.  Returns (keep mask, ascending-sorted
    correlation values of ALL genes — Java sorts ``sortedcorrvals`` before
    filtering and later filters do not touch it).
    """
    npairs = (len(repeats) + 1) * len(repeats) // 2
    dweight = 1.0 / npairs
    nrows = main.data.shape[0]
    corrvals = np.zeros(nrows, dtype=np.float64)
    keep = np.zeros(nrows, dtype=bool)

    md = main.data.tolist()
    mp = main.pma.tolist()
    rds = [r.data.tolist() for r in repeats]
    rps = [r.pma.tolist() for r in repeats]

    for nrow in range(nrows):
        total = 0.0
        for nrepeatset in range(len(repeats)):
            total += dweight * correlation(
                md[nrow], rds[nrepeatset][nrow], mp[nrow], rps[nrepeatset][nrow]
            )
            for nrepeatset2 in range(nrepeatset + 1, len(repeats)):
                total += dweight * correlation(
                    rds[nrepeatset][nrow],
                    rds[nrepeatset2][nrow],
                    rps[nrepeatset][nrow],
                    rps[nrepeatset2][nrow],
                )
        corrvals[nrow] = total
        keep[nrow] = total > dmincorrelation

    return keep, sorted(corrvals.tolist())


def filter_missing(pma: np.ndarray, max_missing: int) -> np.ndarray:
    """``DataSetCore.filterMissing`` (DataSetCore.java:574-604).

    A row is dropped when t0 is missing or when the number of missing values
    exceeds ``max_missing`` (missing count is re-checked after every column,
    so the loop stops early — semantically: total missing <= max_missing).
    """
    nrows, numcols = pma.shape
    keep = np.zeros(nrows, dtype=bool)
    p = pma.tolist()
    for nrow in range(nrows):
        if p[nrow][0] == 0:
            continue
        bgood = True
        nmissing = 0
        for ncol in range(numcols):
            if p[nrow][ncol] == 0:
                nmissing += 1
            bgood = nmissing <= max_missing
            if not bgood:
                break
        keep[nrow] = bgood
    return keep


def filter_threshold(data: np.ndarray, pma: np.ndarray, threshold: float, maxmin: bool) -> np.ndarray:
    """``DataSetCore.filtergenesthreshold2`` (DataSetCore.java:969-1038).

    ``maxmin=True``: keep when max - min (over present cells in columns
    1..T-1; dmax/dmin start at 0) >= threshold.
    ``maxmin=False``: keep when the largest |value| (same column range,
    initialized to 0) >= threshold.  Both comparisons are >=, so a gene
    exactly at the threshold passes.
    """
    nrows, numcols = data.shape
    keep = np.zeros(nrows, dtype=bool)
    d = data.tolist()
    p = pma.tolist()
    for nrow in range(nrows):
        if maxmin:
            dmax = 0.0
            dmin = 0.0
            for ncol in range(1, numcols):
                if p[nrow][ncol] > 0:
                    v = d[nrow][ncol]
                    if v > dmax:
                        dmax = v
                    if v < dmin:
                        dmin = v
            keep[nrow] = (dmax - dmin) >= threshold
        else:
            dmaxval = 0.0
            for ncol in range(1, numcols):
                if p[nrow][ncol] > 0:
                    a = abs(d[nrow][ncol])
                    if a > dmaxval:
                        dmaxval = a
            keep[nrow] = dmaxval >= threshold
    return keep
