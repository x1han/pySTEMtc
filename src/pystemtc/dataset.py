"""Internal data model and the M1 processing chain (spec §1.2/§1.3)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .errors import STEMTCValueError
from .filtering import (
    GeneTable,
    filter_missing,
    filter_threshold,
    merge_duplicates,
    merge_repeats,
    repeat_correlation_filter,
)
from .normalize import log_ratio


@dataclass
class SpotSet:
    """Parsed per-spot input (one row per spot/probe observation).

    ``raw_data``/``raw_pma`` hold the values as currently parsed: raw
    expression straight from :mod:`pystemtc.dataio`, or — once the builder has
    normalized — the normalized values in their place (Java's logratio2
    replaces ``data`` in the same object).
    """

    raw_data: np.ndarray  # (n_spots, T) float64; missing cells hold 0.0
    raw_pma: np.ndarray  # (n_spots, T) int8; 0 = missing, 2 = present
    spot_ids: list[str]
    gene_ids: list[str]
    probe_ids: list[str]
    sample_labels: list[str]
    # round-7.2: original Java-STEM file column headers for the spot/probe
    # and gene columns (parsed by read_stem_file, propagated to writer).
    # path entry keeps the verbatim header text; DataFrame entry uses
    # canonical Python defaults ("spot" / "gene").
    probe_header: str = ""
    gene_header: str = ""


@dataclass
class STEMDataset:
    """Analysis-ready dataset (spec §1.2).

    ``spot_data`` replicates the effective content of Java's
    ``genespottimedata`` (DataSetCore.java:672-719): flat over spot rows
    grouped by surviving gene (gene order = ``gene_data`` row order; within a
    gene the primary row holds post-merge median values, duplicate rows hold
    pre-merge normalized values).  ``repeat_sets`` carries the same layout
    per repeat file (different_periods mode only).
    """

    spot_data: np.ndarray  # (n_spots, T) float64
    spot_pma: np.ndarray  # (n_spots, T) int8
    spot_ids: list[str]
    spot_genes: list[str]
    gene_data: np.ndarray  # (n_genes, T) float64
    gene_pma: np.ndarray  # (n_genes, T) int8
    gene_probes: list[str]
    repeat_sets: list  # list[SpotSet-like]
    repeat_corr_sorted: list[float] | None
    sample_labels: list[str]
    filtered_genes: list[tuple[str, str, str]] = field(default_factory=list)  # (gene, probe, reason)
    # round-7.2: same Java-STEM file column headers, propagated from
    # SpotSet (path entry) or canonical defaults (DataFrame entry).
    probe_header: str = ""
    gene_header: str = ""


def gene_names(dataset: STEMDataset) -> list[str]:
    """Gene symbol per ``gene_data`` row (first occurrence over ``spot_genes``)."""
    seen: set[str] = set()
    out: list[str] = []
    for g in dataset.spot_genes:
        if g not in seen:
            seen.add(g)
            out.append(g)
    return out


def _normalized(spotset: SpotSet, mode: str) -> SpotSet:
    nd, npma = log_ratio(spotset.raw_data, spotset.raw_pma, mode)
    return SpotSet(
        raw_data=nd,
        raw_pma=npma,
        spot_ids=list(spotset.spot_ids),
        gene_ids=list(spotset.gene_ids),
        probe_ids=list(spotset.probe_ids),
        sample_labels=list(spotset.sample_labels),
    )


def _errorcheck(main: SpotSet, rep: SpotSet, check_probes: bool) -> None:
    """``ST.errorcheck`` (ST.java:2321-2402): repeats must align row-by-row.

    The different-periods variant compares the raw gene symbols only
    (ST.java:2773); the same-period variant also compares probe names
    (ST.java:2881).  Java's probe-mismatch message says "gene symbol"
    (copy-paste quirk at ST.java:2352).
    """
    nc_main, nc_rep = main.raw_data.shape[1], rep.raw_data.shape[1]
    if nc_main != nc_rep:
        raise STEMTCValueError(
            "Repeat data set must have same number of columns as original, "
            f"expecting {nc_main} found {nc_rep} in the repeat"
        )
    nr_main, nr_rep = main.raw_data.shape[0], rep.raw_data.shape[0]
    if nr_main != nr_rep:
        raise STEMTCValueError(
            "Repeat data set must have same number of spots as the original, "
            f"expecting {nr_main} found {nr_rep} in the repeat"
        )
    for nrow in range(nr_main):
        g1, g2 = main.gene_ids[nrow], rep.gene_ids[nrow]
        if g1 != g2:
            raise STEMTCValueError(
                f"In row {nrow} of the repeat set expecting gene symbol {g1} found {g2}"
            )
        if check_probes:
            p1, p2 = main.probe_ids[nrow], rep.probe_ids[nrow]
            if p1 != p2:
                raise STEMTCValueError(
                    f"In row {nrow} of the repeat set expecting gene symbol {p1} found {p2}"
                )


def build_stem_dataset(main: SpotSet, repeats: list[SpotSet], mode: str, config) -> STEMDataset:
    """Run the M1 chain in the exact Java order (ST.java:2695-2791).

    different_periods: normalize -> duplicate merge (main and each repeat) ->
    cellwise repeat median merge -> repeat correlation filter -> filter
    missing -> threshold filter.

    same_period: raw repeat merge -> normalize -> duplicate merge -> filter
    missing -> threshold filter (no correlation filter, no sortedcorrvals).
    """
    numcols = main.raw_data.shape[1]
    if numcols < 2:
        raise STEMTCValueError(
            "Data must contain at least 2 time points (including a synthetic "
            "add0 column); the original STEM switches to Gene Ontology "
            "enrichment mode for fewer columns, which pySTEMTC does not implement"
        )

    if mode == "different_periods":
        gt_main = merge_duplicates(_normalized(main, config.normalize))
        gt_repeats: list[GeneTable] = []
        for rep in repeats:
            _errorcheck(main, rep, check_probes=False)
            gt_repeats.append(merge_duplicates(_normalized(rep, config.normalize)))

        merged = merge_repeats(gt_main, gt_repeats, mode)

        if gt_repeats:
            keep_corr, repeat_corr_sorted = repeat_correlation_filter(
                gt_main, gt_repeats, config.repeat_min_correlation
            )
        else:
            keep_corr, repeat_corr_sorted = None, None

        keep_missing = filter_missing(merged.pma, config.max_missing)
        keep_thr = filter_threshold(merged.data, merged.pma, config.min_abs_expr, config.maxmin)
        survivors, filtered = _compose(merged, keep_corr, keep_missing, keep_thr)

        # Flat spot rows grouped by surviving gene, in gene_data row order.
        rows_by_gene: dict[str, list[int]] = {}
        for si, g in enumerate(gt_main.spot_genes):
            rows_by_gene.setdefault(g, []).append(si)
        spot_rows = [
            si for gi in survivors for si in rows_by_gene[gt_main.genes[gi]]
        ]

        repeat_sets = [
            SpotSet(
                raw_data=rep.spot_data[spot_rows],
                raw_pma=rep.spot_pma[spot_rows],
                spot_ids=[rep.spot_ids[si] for si in spot_rows],
                gene_ids=[rep.spot_genes[si] for si in spot_rows],
                probe_ids=[rep.spot_ids[si] for si in spot_rows],
                sample_labels=list(main.sample_labels),
                probe_header=main.probe_header,
                gene_header=main.gene_header,
            )
            for rep in gt_repeats
        ]

    elif mode == "same_period":
        for rep in repeats:
            _errorcheck(main, rep, check_probes=True)
        merged_raw = merge_repeats(main, repeats, mode)
        gt = merge_duplicates(_normalized(merged_raw, config.normalize))

        keep_corr = None
        repeat_corr_sorted = None
        keep_missing = filter_missing(gt.pma, config.max_missing)
        keep_thr = filter_threshold(gt.data, gt.pma, config.min_abs_expr, config.maxmin)
        merged = gt
        survivors, filtered = _compose(merged, keep_corr, keep_missing, keep_thr)

        rows_by_gene = {}
        for si, g in enumerate(gt.spot_genes):
            rows_by_gene.setdefault(g, []).append(si)
        spot_rows = [si for gi in survivors for si in rows_by_gene[gt.genes[gi]]]
        repeat_sets = []

    else:
        raise ValueError(f"unknown repeat mode: {mode!r}")

    return STEMDataset(
        spot_data=merged.spot_data[spot_rows],
        spot_pma=merged.spot_pma[spot_rows],
        spot_ids=[merged.spot_ids[si] for si in spot_rows],
        spot_genes=[merged.spot_genes[si] for si in spot_rows],
        gene_data=merged.data[survivors],
        gene_pma=merged.pma[survivors],
        gene_probes=[merged.probes[gi] for gi in survivors],
        repeat_sets=repeat_sets,
        repeat_corr_sorted=repeat_corr_sorted,
        sample_labels=list(main.sample_labels),
        filtered_genes=filtered,
        probe_header=main.probe_header,
        gene_header=main.gene_header,
    )


def _compose(merged: GeneTable, keep_corr, keep_missing, keep_thr):
    """Intersection of the filter masks, with the reason attributed in the
    order Java applies the filters: correlation, missing, threshold."""
    nrows = merged.data.shape[0]
    survivors: list[int] = []
    filtered: list[tuple[str, str, str]] = []
    for i in range(nrows):
        if keep_corr is not None and not keep_corr[i]:
            filtered.append((merged.genes[i], merged.probes[i], "repeat_correlation"))
        elif not keep_missing[i]:
            filtered.append((merged.genes[i], merged.probes[i], "missing"))
        elif not keep_thr[i]:
            filtered.append((merged.genes[i], merged.probes[i], "threshold"))
        else:
            survivors.append(i)
    if not survivors:
        raise STEMTCValueError("All Genes Filtered")
    return survivors, filtered
