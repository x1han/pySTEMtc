"""Greedy ball clustering of significant profiles
(``clusterprofiles`` STEM_DataSet.java:870-997)."""

from __future__ import annotations

import math

from ._stats import correlation


def _sorted_insert(candidates: list[tuple[float, int]], item: tuple[float, int]) -> None:
    """Java ``TreeSet`` with the descending-distance comparator
    (``Profilerecdistcomparator``, :341-361): keeps entries ordered by
    distance descending and REJECTS an entry whose distance equals an
    existing one (compare == 0 treats it as a duplicate; ``add`` is a no-op).
    Insertion order is the significant-profile scan order, so among equal
    distances the earliest-scanned profile is the one kept."""
    dist = item[0]
    for pos, existing in enumerate(candidates):
        if existing[0] == dist:
            return  # duplicate per comparator: add() rejected
        if existing[0] < dist:
            candidates.insert(pos, item)
            return
    candidates.append(item)


def cluster_profiles(
    sig_ids,
    gene_counts,
    models: list[list[float]],
    thr: float,
    percentile_thr: float,
    repeat_corr_sorted=None,
) -> list[list[int]]:
    """Cluster the significant profiles (:870-997).

    ``sig_ids``: significant profile ids in ascending order (Java builds the
    significant list by scanning ids 0..n-1, :904-912).  ``gene_counts``:
    per-profile assigned gene counts (the ball score).  ``thr``:
    ``Clustering_Minimum_Correlation``.  The threshold is raised to
    ``repeat_corr_sorted[floor(percentile * len)]`` (clamped to len-1) when
    that value is larger (:878-885) — only for different-periods repeat runs,
    where the list is the pre-filter correlation values of ALL dup-merged
    genes (``sortedcorrvals``).

    Semantics pinned by the Java source: neighbor candidates need correlation
    STRICTLY greater than the threshold (:937), ball members must be
    correlation >= threshold with ALL current members
    (``closeToAllNeighbors`` :844-863), ball score = sum of member gene
    counts, the best-scoring ball (strict >) is removed each round and
    becomes one cluster; cluster ids are creation order 0,1,2,....
    """
    dmaxminclustdist = thr

    if (repeat_corr_sorted is not None) and (percentile_thr >= 0):
        nindex = int(
            min(
                len(repeat_corr_sorted) - 1,
                math.floor(percentile_thr * len(repeat_corr_sorted)),
            )
        )
        if repeat_corr_sorted[nindex] > dmaxminclustdist:
            dmaxminclustdist = repeat_corr_sorted[nindex]

    # significantprofiles in ascending profile-id order (:904-912)
    significant: list[tuple[int, float]] = [(int(pid), float(gene_counts[pid])) for pid in sorted(sig_ids)]

    correlations: dict[tuple[int, int], float] = {}

    def corr(a: int, b: int) -> float:
        key = (a, b) if a < b else (b, a)
        value = correlations.get(key)
        if value is None:
            value = correlation(models[a], models[b], [1] * len(models[a]), [1] * len(models[b]))
            correlations[key] = value
        return value

    clusters: list[list[int]] = []

    while significant:
        dbestnumgenes = 0.0
        bestball: list[tuple[float, int]] = []

        for nprofileindex in range(len(significant)):
            center_id, center_count = significant[nprofileindex]

            # neighbor candidates: strictly greater than the threshold (:937)
            candidates: list[tuple[float, int]] = []
            for notherindex in range(len(significant)):
                if notherindex == nprofileindex:
                    continue
                other_id = significant[notherindex][0]
                dtempcorrval = corr(center_id, other_id)
                if dtempcorrval > dmaxminclustdist:
                    _sorted_insert(candidates, (dtempcorrval, other_id))

            # greedy ball expansion (:954-963)
            ball: list[tuple[float, int]] = []
            dnumgenessig = center_count
            for dist, cand_id in candidates:
                bclose = True
                for _, member_id in ball:
                    if corr(cand_id, member_id) < dmaxminclustdist:
                        bclose = False
                        break
                if bclose:
                    # the add can be rejected by the TreeSet (equal distance)
                    # while the score is STILL incremented (:958-962)
                    _sorted_insert(ball, (dist, cand_id))
                    dnumgenessig += gene_counts[cand_id]

            if dnumgenessig > dbestnumgenes:
                dbestnumgenes = dnumgenessig
                _sorted_insert(ball, (1.0, center_id))  # :968
                bestball = ball

        # remove the best ball's members from the significant set (:974-994)
        bestcluster = [pid for _, pid in bestball]
        for pid in bestcluster:
            for pos, (sig_id, _) in enumerate(significant):
                if sig_id == pid:
                    del significant[pos]
                    break
        clusters.append(bestcluster)

    return clusters
