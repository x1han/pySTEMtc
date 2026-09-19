"""Hand-computed unit tests for the M1 chain (DoD M1-2)."""

import math
from pathlib import Path

import numpy as np
import pytest

from pystemtc.config import STEMConfig
from pystemtc.dataio import dataframe_to_spotset, read_stem_file
from pystemtc.dataset import SpotSet, build_stem_dataset, gene_names
from pystemtc.errors import STEMTCValueError
from pystemtc.filtering import (
    GeneTable,
    filter_missing,
    filter_threshold,
    merge_duplicates,
    merge_repeats,
    repeat_correlation_filter,
)
from pystemtc.normalize import log_ratio
from pystemtc._stats import correlation, getmedian
from pystemtc.rng import JavaRandom

GOLDEN = Path(__file__).parent / "golden"


def _spotset(data, pma, spots, genes, labels=("t1", "t2", "t3")):
    return SpotSet(
        raw_data=np.array(data, dtype=np.float64),
        raw_pma=np.array(pma, dtype=np.int8),
        spot_ids=list(spots),
        gene_ids=list(genes),
        probe_ids=list(spots),
        sample_labels=list(labels),
    )


# ---------------------------------------------------------------- getmedian


def test_getmedian_odd_even_unsorted():
    assert getmedian([3.0, 1.0, 2.0]) == 2.0
    assert getmedian([4.0, 1.0, 3.0, 2.0]) == 2.5
    assert getmedian([10.0, 0.0, 5.0, 15.0]) == 7.5
    assert getmedian([7.5]) == 7.5


# --------------------------------------------------------------- correlation


def test_correlation_hand_computed():
    x = [1.0, 2.0, 3.0]
    ones = [2, 2, 2]
    assert correlation(x, [2.0, 4.0, 6.0], ones, ones) == 1.0
    assert correlation(x, [-2.0, -4.0, -6.0], ones, ones) == -1.0
    # constant series -> zero variance -> 0 (Util.java:462-465)
    assert correlation(x, [5.0, 5.0, 5.0], ones, ones) == 0.0
    # no overlapping present pairs -> 0
    assert correlation(x, [1.0, 2.0, 3.0], [2, 0, 2], [0, 2, 2]) == 0.0
    # masking excludes pairs from every sum
    masked = correlation([1.0, 2.0, 3.0], [1.0, 20.0, 3.0], [2, 0, 2], [2, 2, 2])
    assert masked == correlation([1.0, 3.0], [1.0, 3.0], [2, 2], [2, 2])


# --------------------------------------------------------- duplicate merging


def test_merge_duplicates_median_probes_pma():
    # gene AAA has rows 0 and 2; BBB row 1
    ss = _spotset(
        data=[[10.0, 0.0, 4.0], [1.0, 2.0, 3.0], [2.0, 0.0, 6.0]],
        pma=[[2, 2, 2], [2, 2, 2], [2, 0, 2]],
        spots=["P1", "P2", "P3"],
        genes=["AAA", "BBB", "AAA"],
    )
    gt = merge_duplicates(ss)

    assert gt.genes == ["AAA", "BBB"]
    assert gt.probes == ["P1;P3", "P2"]
    # col0: median(10, 2) = 6; col1: only row0 present -> 0.0 with pma 2
    # col2: median(4, 6) = 5
    assert gt.data[0].tolist() == [6.0, 0.0, 5.0]
    assert gt.pma[0].tolist() == [2, 2, 2]
    assert gt.data[1].tolist() == [1.0, 2.0, 3.0]

    # storage-time hard constraint (spec §1.2): the primary row carries the
    # merged values, the duplicate row its pre-merge values
    assert gt.spot_data[0].tolist() == [6.0, 0.0, 5.0]
    assert gt.spot_data[2].tolist() == [2.0, 0.0, 6.0]
    assert gt.spot_pma[2].tolist() == [2, 0, 2]
    assert gt.spot_genes == ["AAA", "BBB", "AAA"]


def test_merge_duplicates_all_missing_column_keeps_primary_value():
    # DDD rows both missing in col2: merged pma is 0 and the value stays the
    # primary row's pre-merge value (Java leaves data[nrow][ncol] untouched)
    ss = _spotset(
        data=[[42.0, 1.0, 9.0], [7.0, 2.0, 8.0]],
        pma=[[2, 2, 0], [2, 2, 0]],
        spots=["P5", "P6"],
        genes=["DDD", "DDD"],
    )
    gt = merge_duplicates(ss)
    assert gt.pma[0].tolist() == [2, 2, 0]
    # col0 median(42,7)=24.5, col1 median(1,2)=1.5; col2 all-missing keeps 9.0
    assert gt.data[0].tolist() == [24.5, 1.5, 9.0]
    assert gt.spot_data[0].tolist() == [24.5, 1.5, 9.0]
    assert gt.spot_data[1].tolist() == [7.0, 2.0, 8.0]


# ------------------------------------------------------ synthesized gene name


def test_synthesized_gene_names_from_file(tmp_path):
    path = tmp_path / "synth.txt"
    path.write_text(
        "SPOT\tGene Symbol\tt1\tt2\n"
        "s1\tAAA\t1\t2\n"
        "\n"  # blank line skipped
        "s2\t\t3\t4\n"
        "s3\t0\t5\t6\n"
        "s4\t0\t7\t8\n",
        encoding="utf-8",
    )
    ss = read_stem_file(path)
    assert ss.gene_ids == ["AAA", "0 (SPOT_S2)", "0 (SPOT_S3)", "0 (SPOT_S4)"]
    assert ss.spot_ids == ["S1", "S2", "S3", "S4"]
    # a gene literally named "0" keeps its data (DataSetCore.java:476-479)
    assert ss.raw_data[2].tolist() == [5.0, 6.0]
    assert ss.raw_data[3].tolist() == [7.0, 8.0]


def test_synthesized_gene_names_without_spot_column(tmp_path):
    path = tmp_path / "nospot.txt"
    path.write_text("GENE\tt1\tt2\nAAA\t1\t2\n0\t3\t4\n\t5\t6\n", encoding="utf-8")
    ss = read_stem_file(path, spot_included=False)
    assert ss.spot_ids == ["ID_0", "ID_1", "ID_2"]
    assert ss.gene_ids == ["AAA", "0 (SPOT_ID_1)", "0 (SPOT_ID_2)"]
    assert ss.raw_data[2].tolist() == [5.0, 6.0]


def test_file_reader_quote_stripping_uppercase_and_duplicates(tmp_path):
    path = tmp_path / "quotes.txt"
    path.write_text('SPOT\tGene Symbol\tt1\n"p1"\t"aaa"\t1\nP1\tBBB\t2\n', encoding="utf-8")
    ss = read_stem_file(path)
    assert ss.gene_ids == ["AAA", "BBB"]
    # Java strips quotes from GENE tokens only; spot tokens keep them
    # (DataSetCore.java:454 vs :481-485)
    assert ss.spot_ids == ['"P1"', "P1"]

    dup = tmp_path / "dup.txt"
    dup.write_text("SPOT\tGene Symbol\tt1\nA\tG\t1\nA\tH\t2\n", encoding="utf-8")
    with pytest.raises(STEMTCValueError, match="not unique"):
        read_stem_file(dup)

    blank = tmp_path / "blank.txt"
    blank.write_text("SPOT\tGene Symbol\tt1\n\tG\t1\n", encoding="utf-8")
    with pytest.raises(STEMTCValueError, match="Missing a Spot Name"):
        read_stem_file(blank)


def test_dataframe_reader_contract():
    import pandas as pd

    df = pd.DataFrame(
        {
            "spot": ["s1", "s2"],
            "gene": ["AA", "0"],
            "0h": [1.0, 3.0],
            "1h": [np.nan, 4.0],
        }
    )
    ss = dataframe_to_spotset(df)
    assert ss.spot_ids == ["S1", "S2"]
    assert ss.gene_ids == ["AA", "0 (SPOT_S2)"]
    assert ss.sample_labels == ["0h", "1h"]
    assert ss.raw_pma[0].tolist() == [2, 0]  # NaN is missing
    assert ss.raw_data[0].tolist() == [1.0, 0.0]
    assert ss.raw_data[1].tolist() == [3.0, 4.0]

    no_spot = dataframe_to_spotset(df.drop(columns=["spot"]))
    assert no_spot.spot_ids == ["SPOT_0", "SPOT_1"]

    with pytest.raises(STEMTCValueError):
        dataframe_to_spotset(df.drop(columns=["gene"]))


# ----------------------------------------------------------------- normalize


def test_log_mode_nonpositive_marked_missing_at_read(tmp_path):
    path = tmp_path / "log.txt"
    path.write_text("SPOT\tGENE\tt1\tt2\tt3\ns1\tG\t2\t-1\t0\n", encoding="utf-8")
    ss = read_stem_file(path, takelog=True)
    # raw values are kept as parsed; only pma changes (DataSetCore.java:530-534)
    assert ss.raw_data[0].tolist() == [2.0, -1.0, 0.0]
    assert ss.raw_pma[0].tolist() == [2, 0, 0]


def test_add0_synthetic_zero_column(tmp_path):
    path = tmp_path / "add0.txt"
    path.write_text("SPOT\tGENE\tt1\tt2\ns1\tG\t1\t2\n", encoding="utf-8")
    ss = read_stem_file(path, add0=True)
    assert ss.raw_data.shape == (1, 3)
    assert ss.raw_data[0].tolist() == [0.0, 1.0, 2.0]
    assert ss.raw_pma[0].tolist() == [2, 2, 2]
    assert ss.sample_labels == ["0", "t1", "t2"]


def test_log_ratio_t0_missing_cascades_both_modes():
    # normalize mode: row with missing t0 -> everything after t0 missing/+inf
    nd, npma = log_ratio(np.array([[3.0, 4.0, 5.0]]), np.array([[0, 2, 2]], np.int8), "normalize")
    assert nd[0].tolist() == [0.0, np.inf, np.inf]
    assert npma[0].tolist() == [0, 0, 0]

    # log mode: same cascade (DataSetCore.java:740-744)
    nd, npma = log_ratio(np.array([[2.0, -1.0, 4.0]]), np.array([[0, 0, 2]], np.int8), "log")
    assert nd[0].tolist() == [0.0, np.inf, np.inf]
    assert npma[0].tolist() == [0, 0, 0]


def test_log_ratio_modes_values():
    nd, npma = log_ratio(np.array([[3.0, 4.0, 5.0]]), np.array([[2, 2, 2]], np.int8), "normalize")
    assert nd[0].tolist() == [0.0, 1.0, 2.0]
    assert npma[0].tolist() == [2, 2, 2]

    nd, _ = log_ratio(np.array([[2.0, 8.0, 4.0]]), np.array([[2, 2, 2]], np.int8), "log")
    assert nd[0].tolist() == [0.0, 2.0, 1.0]

    # none_add0: v0 is the synthetic zero column, so values are unchanged
    nd, npma = log_ratio(np.array([[0.0, 3.0, -1.0]]), np.array([[2, 2, 2]], np.int8), "none_add0")
    assert nd[0].tolist() == [0.0, 3.0, -1.0]
    assert npma[0].tolist() == [2, 2, 2]

    with pytest.raises(ValueError):
        log_ratio(np.zeros((1, 2)), np.zeros((1, 2), np.int8), "bogus")


# ------------------------------------------------------------------- filters


def test_filter_missing_rules():
    pma = np.array([[2, 2, 2], [0, 2, 2], [2, 0, 2], [2, 2, 0]], dtype=np.int8)
    keep = filter_missing(pma, 0)
    assert keep.tolist() == [True, False, False, False]
    keep = filter_missing(pma, 1)
    assert keep.tolist() == [True, False, True, True]
    keep = filter_missing(pma, 2)
    assert keep.tolist() == [True, False, True, True]


def test_filter_threshold_change_variant_boundary_passes():
    data = np.array(
        [
            [0.0, 0.4, -0.8, 0.3],  # max |v| = 0.8 == threshold -> keep
            [0.0, 0.79, -0.1, 0.0],  # 0.79 < 0.8 -> filtered
            [5.0, 0.1, 0.1, 0.1],  # col 0 ignored despite huge value
            [0.0, 2.0, -0.9, 0.0],  # missing col1 value ignored
        ]
    )
    pma = np.array([[2, 2, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2], [2, 0, 2, 2]], dtype=np.int8)
    keep = filter_threshold(data, pma, 0.8, maxmin=False)
    assert keep.tolist() == [True, False, False, True]


def test_filter_threshold_maxmin_variant_boundary_and_zero_init():
    data = np.array(
        [
            [0.0, 1.0, -0.5, 0.2],  # range 1.5 >= 1.0 -> keep
            [0.0, 0.6, -0.3, 0.0],  # range 0.9 < 1.0 -> filtered
            [0.0, 0.2, 0.1, 0.0],  # dmax=0.2, dmin stays 0 -> filtered
            [0.0, -0.2, -1.4, 0.0],  # dmax stays 0, dmin=-1.4 -> range 1.4 -> keep
            [0.0, 0.75, 0.0, -0.25],  # range exactly 1.0 -> keep (>=)
        ]
    )
    pma = np.full((5, 4), 2, dtype=np.int8)
    keep = filter_threshold(data, pma, 1.0, maxmin=True)
    assert keep.tolist() == [True, False, False, True, True]


# -------------------------------------------------------------- repeat merge


def _gene_table(data, pma, genes, probes):
    data = np.array(data, dtype=np.float64)
    pma = np.array(pma, dtype=np.int8)
    return GeneTable(
        data=data,
        pma=pma,
        genes=list(genes),
        probes=list(probes),
        spot_data=data.copy(),
        spot_pma=pma.copy(),
        spot_genes=list(genes),
        spot_ids=list(probes),
    )


def test_merge_repeats_different_periods_median_order():
    main = _gene_table(
        data=[[1.0, 2.0, 3.0], [10.0, 0.0, 30.0]],
        pma=[[2, 2, 2], [2, 0, 2]],
        genes=["A", "B"],
        probes=["P1", "P2"],
    )
    rep1 = _gene_table(
        data=[[2.0, 3.0, 4.0], [20.0, 5.0, 40.0]],
        pma=[[2, 2, 2], [2, 2, 2]],
        genes=["A", "B"],
        probes=["Q1", "Q2"],
    )
    rep2 = _gene_table(
        data=[[3.0, 9.0, 6.0], [30.0, 7.0, 60.0]],
        pma=[[2, 0, 2], [2, 0, 2]],
        genes=["A", "B"],
        probes=["R1", "R2"],
    )
    merged = merge_repeats(main, [rep1, rep2], "different_periods")
    # gene A: col0 median(1,2,3)=2; col1 median(2,3)=2.5 (rep2 missing);
    # col2 median(3,4,6)=4. gene B col1: only rep1 present -> 5.0.
    assert merged.data[0].tolist() == [2.0, 2.5, 4.0]
    assert merged.pma[0].tolist() == [2, 2, 2]
    assert merged.data[1].tolist() == [20.0, 5.0, 40.0]
    assert merged.pma[1].tolist() == [2, 2, 2]
    # the merged table keeps the main set's probe strings
    assert merged.probes == ["P1", "P2"]


def test_merge_repeats_same_period_raw_median_before_normalize():
    main = _spotset(
        data=[[1.0, 2.0, 3.0], [5.0, 5.0, 5.0]],
        pma=[[2, 2, 2], [2, 2, 2]],
        spots=["S1", "S2"],
        genes=["G", "G"],
        labels=("t1", "t2", "t3"),
    )
    rep = _spotset(
        data=[[3.0, 4.0, 6.0], [7.0, 9.0, 11.0]],
        pma=[[2, 2, 2], [2, 2, 2]],
        spots=["S1", "S2"],
        genes=["G", "G"],
        labels=("t1", "t2", "t3"),
    )
    merged = merge_repeats(main, [rep], "same_period")
    # raw cellwise medians first: (1,3)/2=2, (2,4)/2=3, (3,6)/2=4.5
    assert merged.raw_data[0].tolist() == [2.0, 3.0, 4.5]
    assert merged.raw_data[1].tolist() == [6.0, 7.0, 8.0]
    # duplicates survive the raw merge (dup-merge happens after normalize)
    assert merged.gene_ids == ["G", "G"]

    nd, npma = log_ratio(merged.raw_data, merged.raw_pma, "normalize")
    normalized = SpotSet(
        raw_data=nd,
        raw_pma=npma,
        spot_ids=merged.spot_ids,
        gene_ids=merged.gene_ids,
        probe_ids=merged.probe_ids,
        sample_labels=merged.sample_labels,
    )
    gt = merge_duplicates(normalized)
    # normalized spot rows: S1=[0,1,2.5], S2=[0,1,2]; dup-merged medians:
    # median(0,0)=0, median(1,1)=1, median(2.5,2)=2.25
    assert gt.data[0].tolist() == [0.0, 1.0, 2.25]
    assert gt.probes == ["S1;S2"]


# ------------------------------------------------- no-repeat passthrough (P1)


def test_merge_repeats_no_repeats_passthrough_different_periods():
    """No-repeat passthrough contract (P1 fix, spec 03 §1.7): with zero
    repeats Java never calls mergeDataSets (ST.java:2577 keeps
    ``theDataSet1``), so the merged table IS the main table and all-missing
    cells keep the primary row's stored payload.  Constructed with a
    log-mode negative-value-missing cell (the loader keeps the negative
    value and marks pma=0, DataSetCore.java:530-533 -> log(negative) = NaN):
    pre-fix the zero-initialized median matrix zeroed it, post-fix the NaN
    payload survives.  No Java oracle exists for this isolated call shape
    (Java skips the call entirely); this pins the contract, not an
    oracle-verified value."""
    main = _gene_table(
        data=[[0.0, 1.5, math.nan]],
        pma=[[2, 2, 0]],
        genes=["G"],
        probes=["P1"],
    )
    merged = merge_repeats(main, [], "different_periods")
    assert merged is main
    assert merged.pma[0].tolist() == [2, 2, 0]
    assert math.isnan(merged.data[0, 2])
    assert merged.data[0, :2].tolist() == [0.0, 1.5]


def test_merge_repeats_no_repeats_passthrough_same_period():
    """Same-period analogue: raw SpotSet passthrough keeps the raw payload of
    missing cells (log-mode negative marked missing at read, value kept)."""
    main = _spotset(
        data=[[2.0, -1.0, 0.5]],
        pma=[[2, 0, 2]],
        spots=["S1"],
        genes=["G"],
    )
    merged = merge_repeats(main, [], "same_period")
    assert merged is main
    assert merged.raw_pma[0].tolist() == [2, 0, 2]
    assert merged.raw_data[0].tolist() == [2.0, -1.0, 0.5]


def test_merge_repeats_no_repeats_leaves_main_unmutated():
    """Passthrough must not mutate the main table (bit-for-bit before/after),
    guarding against future copy-and-rebake implementations."""
    main = _gene_table(
        data=[[0.0, 1.5, -math.inf], [0.0, 2.5, math.nan]],
        pma=[[2, 2, 0], [2, 2, 2]],
        genes=["A", "B"],
        probes=["P1", "P2"],
    )
    data_before = main.data.copy()
    pma_before = main.pma.copy()
    spot_before = main.spot_data.copy()
    spot_pma_before = main.spot_pma.copy()
    merged = merge_repeats(main, [], "different_periods")
    assert merged is main
    assert np.array_equal(merged.data, data_before, equal_nan=True)
    assert np.array_equal(merged.pma, pma_before)
    assert np.array_equal(merged.spot_data, spot_before, equal_nan=True)
    assert np.array_equal(merged.spot_pma, spot_pma_before)


def test_merge_repeats_rejects_unknown_mode_even_without_repeats():
    """Mode validation is hoisted above the passthrough so the internal
    contract (unknown mode raises) does not silently narrow for the
    no-repeat call shape."""
    main = _gene_table(
        data=[[0.0, 1.5]],
        pma=[[2, 2]],
        genes=["G"],
        probes=["P1"],
    )
    with pytest.raises(ValueError, match="unknown repeat mode"):
        merge_repeats(main, [], "bogus")


# -------------------------------------------------------- repeat correlation


def test_repeat_correlation_filter_mask_and_sort():
    main = _gene_table(
        data=[[0.0, 1.0, 2.0], [0.0, 1.0, 2.0], [0.0, 2.0, 1.0]],
        pma=[[2, 2, 2], [2, 2, 2], [2, 2, 2]],
        genes=["A", "B", "C"],
        probes=["P1", "P2", "P3"],
    )
    rep = _gene_table(
        data=[[0.0, 2.0, 4.0], [2.0, 1.0, 0.0], [0.0, 1.0, 2.0]],
        pma=[[2, 2, 2], [2, 2, 2], [2, 2, 2]],
        genes=["A", "B", "C"],
        probes=["Q1", "Q2", "Q3"],
    )
    keep, sortedcorr = repeat_correlation_filter(main, [rep], 0.0)
    # A vs rep: +1; B vs rep: -1; C [0,2,1] vs rep [0,1,2]: 0.5
    # -> all strictly greater than 0
    assert keep.tolist() == [True, False, True]
    assert sortedcorr == sorted(sortedcorr)
    assert sortedcorr == [-1.0, 0.5, 1.0]

    # masked cell: the middle point of the repeat is missing; the correlation
    # is computed from the two remaining columns only
    main2 = _gene_table([[0.0, 1.0, 2.0]], [[2, 2, 2]], ["A"], ["P1"])
    rep2 = _gene_table([[0.0, 50.0, 4.0]], [[2, 0, 2]], ["A"], ["Q1"])
    keep2, corr2 = repeat_correlation_filter(main2, [rep2], 0.0)
    assert keep2.tolist() == [True]
    assert corr2[0] == 1.0  # points (0,0) and (2,4): perfectly correlated

    # variance 0 within the masked overlap (cols 1-2 of main are both 1.0)
    # -> correlation 0 -> filtered with a strictly-positive threshold
    flat = _gene_table([[0.0, 1.0, 1.0]], [[2, 2, 2]], ["A"], ["P1"])
    rep3 = _gene_table([[7.0, 50.0, 4.0]], [[0, 2, 2]], ["A"], ["Q1"])
    keep3, corr3 = repeat_correlation_filter(flat, [rep3], 0.0)
    assert keep3.tolist() == [False]
    assert corr3[0] == 0.0


def test_repeat_correlation_two_repeats_pair_count():
    # (R+1)*R/2 = 3 pairs for two repeats, equal weight 1/3.  Java's pair
    # order is (main,r0), (r0,r1), (main,r1) (DataSetCore.java:857-871).
    main = _gene_table([[0.0, 1.0, 2.0]], [[2, 2, 2]], ["A"], ["P1"])
    rep1 = _gene_table([[0.0, 2.0, 4.0]], [[2, 2, 2]], ["A"], ["Q1"])
    rep2 = _gene_table([[0.0, -1.0, -2.0]], [[2, 2, 2]], ["A"], ["R1"])
    keep, corr = repeat_correlation_filter(main, [rep1, rep2], 0.0)
    # corr(main,rep1)=+1, corr(rep1,rep2)=-1, corr(main,rep2)=-1 -> -1/3
    assert corr[0] == pytest.approx(-1.0 / 3.0)
    assert keep.tolist() == [False]


# ------------------------------------------------------------- builder (M1)


def _three_spot_main_with_replicate():
    """1 gene x 2 spots (dup) in main and repeat, 3 time points."""
    main = _spotset(
        data=[[1.0, 2.0, 4.0], [3.0, 4.0, 8.0]],
        pma=[[2, 2, 2], [2, 2, 2]],
        spots=["S1", "S2"],
        genes=["G", "G"],
    )
    rep = _spotset(
        data=[[2.0, 1.0, 2.0], [4.0, 3.0, 6.0]],
        pma=[[2, 2, 2], [2, 2, 2]],
        spots=["S1", "S2"],
        genes=["G", "G"],
    )
    return main, rep


def test_build_stem_dataset_same_period_end_to_end():
    main, rep = _three_spot_main_with_replicate()
    config = STEMConfig(normalize="normalize", max_missing=0, min_abs_expr=0.5, maxmin=False)
    ds = build_stem_dataset(main, [rep], mode="same_period", config=config)
    # raw medians per spot: S1=[1.5,1.5,3], S2=[3.5,3.5,7]; normalized:
    # S1=[0,0,1.5], S2=[0,0,3.5]; dup-merged median: [0,0,2.5]
    assert ds.gene_data.tolist() == [[0.0, 0.0, 2.5]]
    assert ds.gene_probes == ["S1;S2"]
    assert ds.repeat_sets == []
    assert ds.repeat_corr_sorted is None
    assert ds.filtered_genes == []
    # spot content: primary row merged, duplicate row pre-merge normalized
    assert ds.spot_data[0].tolist() == [0.0, 0.0, 2.5]
    assert ds.spot_data[1].tolist() == [0.0, 0.0, 3.5]
    assert ds.spot_genes == ["G", "G"]
    assert gene_names(ds) == ["G"]


def test_build_stem_dataset_different_periods_end_to_end():
    main, rep = _three_spot_main_with_replicate()
    config = STEMConfig(normalize="normalize", max_missing=0, min_abs_expr=0.5, maxmin=False)
    ds = build_stem_dataset(main, [rep], mode="different_periods", config=config)
    # main dup-merged normalized: [0,1,3]; repeat: [0,-1,2];
    # merged medians: [0, 0, 2.5]
    assert ds.gene_data.tolist() == [[0.0, 0.0, 2.5]]
    assert ds.repeat_corr_sorted is not None
    assert len(ds.repeat_corr_sorted) == 1
    assert len(ds.repeat_sets) == 1
    assert ds.repeat_sets[0].raw_data.shape == (2, 3)
    assert ds.gene_probes == ["S1;S2"]


def test_build_stem_dataset_filters_and_reasons():
    main = _spotset(
        data=[
            [1.0, 1.1, 1.2, 1.05],  # FLAT: max |diff| 0.2 < 0.5
            [2.0, 2.6, 2.1, 2.0],  # EDGE: max |diff| 0.6 >= 0.5
            [3.0, 3.9, 2.9, 3.0],  # NEG: max |diff| 0.9 >= 0.5
        ],
        pma=[[2, 2, 2, 2]] * 3,
        spots=["S1", "S2", "S3"],
        genes=["FLAT", "EDGE", "NEG"],
        labels=("t1", "t2", "t3", "t4"),
    )
    config = STEMConfig(normalize="normalize", max_missing=0, min_abs_expr=0.5, maxmin=False)
    ds = build_stem_dataset(main, [], mode="different_periods", config=config)
    # normalized rows: FLAT [0,.1,.2,.05]; EDGE [0, 2.6-2.0, 2.1-2.0, 0];
    # NEG [0, 3.9-3.0, 2.9-3.0, 0] (written as the same float expressions)
    assert ds.gene_data.tolist() == [
        [0.0, 2.6 - 2.0, 2.1 - 2.0, 0.0],
        [0.0, 3.9 - 3.0, 2.9 - 3.0, 0.0],
    ]
    assert [g for g, _, _ in ds.filtered_genes] == ["FLAT"]
    assert ds.filtered_genes[0] == ("FLAT", "S1", "threshold")
    assert gene_names(ds) == ["EDGE", "NEG"]


def test_build_stem_dataset_missing_filter_reason():
    main = _spotset(
        data=[[1.0, 2.0, 3.0], [1.0, 0.0, 3.0]],
        pma=[[2, 2, 2], [2, 0, 2]],
        spots=["S1", "S2"],
        genes=["OK", "HOLE"],
    )
    config = STEMConfig(normalize="normalize", max_missing=0, min_abs_expr=0.1, maxmin=False)
    ds = build_stem_dataset(main, [], mode="different_periods", config=config)
    assert [g for g, _, _ in ds.filtered_genes] == ["HOLE"]
    assert ds.filtered_genes[0][2] == "missing"
    assert ds.gene_probes == ["S1"]


def test_build_stem_dataset_requires_two_time_points():
    main = _spotset(data=[[1.0]], pma=[[2]], spots=["S1"], genes=["G"], labels=("t1",))
    with pytest.raises(STEMTCValueError, match="at least 2 time points"):
        build_stem_dataset(main, [], mode="different_periods", config=STEMConfig())


def test_build_stem_dataset_all_filtered_raises():
    main = _spotset(data=[[1.0, 1.0, 1.0]], pma=[[2, 2, 2]], spots=["S1"], genes=["G"])
    with pytest.raises(STEMTCValueError, match="All Genes Filtered"):
        build_stem_dataset(
            main,
            [],
            mode="different_periods",
            config=STEMConfig(normalize="normalize", min_abs_expr=5.0, maxmin=False),
        )


def test_build_stem_dataset_repeat_misaligned_raises():
    main = _spotset(data=[[1.0, 2.0, 3.0]], pma=[[2, 2, 2]], spots=["S1"], genes=["G"])
    rep = _spotset(data=[[1.0, 2.0, 3.0]], pma=[[2, 2, 2]], spots=["S1"], genes=["H"])
    with pytest.raises(STEMTCValueError, match="expecting gene symbol G found H"):
        build_stem_dataset(
            main, [rep], mode="different_periods", config=STEMConfig(normalize="normalize")
        )


# -------------------------------------------------------------------- config


def test_config_from_c01_defaults_file():
    config = STEMConfig.from_defaults_file(GOLDEN / "java_configs" / "c01_guillemin_core.txt")
    assert config.normalize == "normalize"
    assert config.max_missing == 0
    assert config.min_abs_expr == 0.8
    assert config.maxmin is False  # "Difference From 0"
    assert config.repeat_min_correlation == 0.0
    assert config.spot_included is True
    assert config.repeat_mode == "different_periods"
    assert config.takelog is False
    assert config.add0 is False


# ----------------------------------------------------------------- JavaRandom


def test_java_random_seed_zero_doubles():
    # values exported from the real java.util.Random via jjs (JRE 8)
    rng = JavaRandom(0)
    assert [rng.next_double() for _ in range(5)] == [
        0.730967787376657,
        0.24053641567148587,
        0.6374174253501083,
        0.5504370051176339,
        0.5975452777972018,
    ]


def test_java_random_power_of_two_bound():
    # nextInt(1024) exercises the (bound & -bound) == bound fast path
    rng = JavaRandom(42)
    assert [rng.next_int(1024) for _ in range(8)] == [745, 55, 699, 49, 316, 964, 283, 724]


def test_java_random_rejection_overflow_path():
    # bound 2**30 + 1 is the Javadoc's worst case (rejection probability 1/2);
    # this stream crosses the int-overflow rejection branch repeatedly
    rng = JavaRandom(9873287)
    assert [rng.next_int(2**30 + 1) for _ in range(10)] == [
        901924909, 129129964, 165827717, 185405313, 935698338,
        594822234, 70912003, 787504116, 735555787, 164654130,
    ]
    rng = JavaRandom(7)
    assert [rng.next_int(1000) for _ in range(5)] == [236, 164, 485, 44, 380]


def test_java_random_signed_next32_and_invalid_bound():
    # fresh java.util.Random(42).nextInt(), confirmed via jjs (JRE 8)
    assert JavaRandom(42).next(32) == -1170105035
    assert JavaRandom(42).next(31) >= 0
    with pytest.raises(ValueError):
        JavaRandom(42).next_int(0)
    with pytest.raises(ValueError):
        JavaRandom(42).next_int(-1)
