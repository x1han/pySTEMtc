"""Gene -> model profile assignment (``findbestgroupassignments``,
STEM_DataSet.java:1718-1758)."""

from __future__ import annotations

import numpy as np

from ._stats import correlation


def best_assignments(
    gene_data: np.ndarray, gene_pma: np.ndarray, models: list[list[float]]
) -> list[list[int]]:
    """Best-matching profile(s) per gene row; ALL argmax ties are kept.

    Correlation is the masked Pearson of ``Util.correlation`` (3-arg overload
    called with the gene's pma as the single mask, :1739-1740) via
    :func:`pystemtc._stats.correlation` (same accumulation order).  Ties keep
    every argmax in ascending model-index order (:1742-1751).  Quirk: if no
    correlation is ever ``> -2`` or ``== -2`` (all-NaN correlations), the
    gene keeps the initial full-profile list (:1736, ``allprofiles``).
    """
    data = gene_data.tolist()
    pma = gene_pma.tolist()
    numrows = len(data)
    numprofiles = len(models)

    allprofiles = list(range(numprofiles))
    best: list[list[int]] = []

    for nrow in range(numrows):
        dcorrmax = -2.0
        assignments = allprofiles  # Compatibility contract (STEM v1.3.14 ST.java:1736): initial value is the all-profiles vector; preserved so downstream correlation assignments reference the same baseline the Java reference uses.
        for nmodelprofile in range(numprofiles):
            dcorr = correlation(
                data[nrow], models[nmodelprofile], pma[nrow], pma[nrow]
            )
            if dcorr == dcorrmax:
                assignments.append(nmodelprofile)
            elif dcorr > dcorrmax:
                dcorrmax = dcorr
                assignments = [nmodelprofile]
        best.append(assignments)
    return best
