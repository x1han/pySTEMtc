"""Schema-v2 contract tests for ``STEMResult.to_dict`` (spec 03 §1.10).

Covers the top-level key set, the ``_encode_value`` five-state truth table,
the lossless encoding of c14's non-finite payloads, the config/input/metadata
shapes, the timing stage keys, strict-JSON compatibility and determinism
(two ``to_dict()`` calls on the same result are identical, timestamp
included).  Golden-driven cases reuse the cached runs of
``test_golden._run_case``; a toy engine run pins the ``stem_dataset`` input
form.
"""

import dataclasses
import json
import math
import re

import numpy as np
import pytest

from pystemtc.config import STEMConfig
from pystemtc.dataset import SpotSet, build_stem_dataset
from pystemtc.engine import STEM
from pystemtc.result import CONFIG_ALGORITHM_KEYS, STEMResult, _encode_value
from test_golden import _run_case

TIMING_KEYS = {
    "input_read",
    "normalize_filter",
    "profile_generation",
    "assignment",
    "permutation",
    "significance",
    "clustering",
    "wall",
}

TOP_LEVEL_KEYS = {
    "schema_version",
    "reference",
    "generator",
    "config",
    "input",
    "metadata",
    "profiles",
    "gene_assignments",
    "filtered_genes",
    "clusters",
    "timing",
}


def _by_gene(payload):
    return {row["gene"]: row for row in payload["gene_assignments"]}


def _toy_result() -> STEMResult:
    """3 genes x 4 time points; gene B is flat (all-zero after normalize)."""
    data = np.array(
        [[1.0, 2.0, 3.0, 4.0], [5.0, 5.0, 5.0, 5.0], [2.0, 4.0, 6.0, 8.0]],
        dtype=np.float64,
    )
    pma = np.full((3, 4), 2, dtype=np.int8)
    main = SpotSet(
        raw_data=data,
        raw_pma=pma,
        spot_ids=["S1", "S2", "S3"],
        gene_ids=["A", "B", "C"],
        probe_ids=["S1", "S2", "S3"],
        sample_labels=["0h", "1h", "2h", "4h"],
    )
    cfg = STEMConfig(normalize="normalize", min_abs_expr=0.0, maxmin=False)
    ds = build_stem_dataset(main, [], "different_periods", cfg)
    return STEM(n_permutations=0).fit(ds)


# 1 --- top-level keys and constants -----------------------------------------


def test_top_level_keys_and_constants():
    payload = _run_case("c14_log_missing").to_dict()
    assert set(payload) == TOP_LEVEL_KEYS
    assert payload["schema_version"] == 2
    assert payload["reference"] == {"software": "STEM", "version": "1.3.14"}
    assert payload["generator"]["package"] == "pystemtc"
    assert isinstance(payload["generator"]["version"], str)


# 2 --- gene_assignments row shape + c14 non-finite payload -------------------


def test_gene_assignments_shape_and_c14_negative_infinity():
    payload = _run_case("c14_log_missing").to_dict()
    rows = payload["gene_assignments"]
    assert rows
    for row in rows:
        assert set(row) == {
            "gene",
            "probe",
            "profile_ids",
            "values",
            "value_states",
            "present",
        }
        assert all(isinstance(p, int) and not isinstance(p, bool) for p in row["profile_ids"])
        assert len(row["values"]) == len(row["value_states"]) == len(row["present"])
        for state, value in zip(row["value_states"], row["values"]):
            assert (value is None) == (state in ("nan", "positive_infinity", "negative_infinity"))
    s3 = _by_gene(payload)["S_0003"]
    assert s3["values"][-1] is None
    assert s3["value_states"][-1] == "negative_infinity"
    assert s3["present"][-1] is False


# 3 --- _encode_value truth table ---------------------------------------------


@pytest.mark.parametrize(
    ("value", "present", "expected_state", "expected_value"),
    [
        # 8 semantic combinations (4 value categories x 2 present) + 2 extra
        # finite representative values for finite+True (the table contains
        # two finite+True rows because finite+True is a single semantic
        # combination, not two).  See spec 03 §1.10 round-7.1 contract:
        # non-finite classification independent of present; finite payload
        # then split by present.  Never collapse value_states into a
        # missness-only field.
        (math.nan, True, "nan", None),
        (math.nan, False, "nan", None),
        (math.inf, True, "positive_infinity", None),
        (math.inf, False, "positive_infinity", None),
        (-math.inf, True, "negative_infinity", None),
        (-math.inf, False, "negative_infinity", None),
        (0.0, True, "finite", 0.0),
        (-0.5, True, "finite", -0.5),  # extra finite+True representative
        (0.948, False, "missing", 0.948),  # c13 phantom-fill payload
        (-math.inf, False, "negative_infinity", None),  # c14 present=False, -Inf
    ],
)
def test_encode_value_truth_table_8_semantic_combinations(
    value, present, expected_state, expected_value
):
    """Round-7.1 contract: 8 semantic (value, present) combinations.

    The 10 parametrized cases are 8 distinct semantic combinations
    (4 payload categories NaN/+Inf/-Inf/finite × 2 present bits) plus
    2 extra representative finite values (0.0 and -0.5) — those two are
    the same semantic case (finite+True), just different sample doubles.
    Critically: `(-inf, False)` reports `"negative_infinity"` (NOT
    `"missing"`), and `(+inf, True)` reports `"positive_infinity"`
    (NOT `"finite"`) — both cases would be wrong under the pre-round-7
    direction-invariance formulation `present=True ⇒ state=="finite"`.
    """
    state, out = _encode_value(value, present)
    assert state == expected_state
    assert out == expected_value


def test_encode_value_truth_table_and_length_invariant():
    # non-finite states win over present, whatever the pma mask says
    assert _encode_value(math.nan, True) == ("nan", None)
    assert _encode_value(math.nan, False) == ("nan", None)
    assert _encode_value(math.inf, True) == ("positive_infinity", None)
    assert _encode_value(math.inf, False) == ("positive_infinity", None)
    assert _encode_value(-math.inf, True) == ("negative_infinity", None)
    assert _encode_value(-math.inf, False) == ("negative_infinity", None)
    # finite branch splits on present; the fill payload is retained
    assert _encode_value(0.948, False) == ("missing", 0.948)
    assert _encode_value(-0.5, True) == ("finite", -0.5)
    assert _encode_value(0.0, True) == ("finite", 0.0)
    # structural invariant: state/value lists come out per input cell
    values = [math.nan, math.inf, -math.inf, 1.5, -2.5]
    present = [False, True, True, False, True]
    states = []
    encoded = []
    for value, is_present in zip(values, present):
        state, out = _encode_value(value, is_present)
        states.append(state)
        encoded.append(out)
    assert len(states) == len(encoded) == len(values) == len(present)
    assert states == [
        "nan",
        "positive_infinity",
        "negative_infinity",
        "missing",
        "finite",
    ]
    assert encoded == [None, None, None, 1.5, -2.5]


# 4 --- strict JSON -----------------------------------------------------------


def test_to_dict_is_strict_json():
    for case in ("c14_log_missing", "c13_synth10_missing"):
        payload = _run_case(case).to_dict()
        text = json.dumps(payload, allow_nan=False)  # must not raise
        assert '"schema_version": 2' in text


# 5 --- determinism -----------------------------------------------------------


def test_to_dict_deterministic():
    result = _run_case("c14_log_missing")
    assert result.to_dict() == result.to_dict()


# 6 --- profile ids survive into the schema -----------------------------------


def test_c14_s0003_profile_ids():
    payload = _run_case("c14_log_missing").to_dict()
    assert _by_gene(payload)["S_0003"]["profile_ids"] == [7]


# 7 --- input.time_points ------------------------------------------------------


def test_c14_input_time_points():
    payload = _run_case("c14_log_missing").to_dict()
    assert payload["input"]["time_points"] == ["0h", "1h", "2h", "4h", "8h", "24h"]


# 8 --- config / input shapes --------------------------------------------------


def test_config_and_input_shapes():
    result = _run_case("c14_log_missing")
    payload = result.to_dict()
    stemconfig_keys = {f.name for f in dataclasses.fields(STEMConfig)}
    expected = stemconfig_keys - {"data_file", "repeat_files"}
    assert set(payload["config"]) == expected
    assert set(payload["config"]) == set(CONFIG_ALGORITHM_KEYS)
    assert set(payload["input"]) == {"form", "data_file", "repeat_files", "time_points"}
    assert payload["input"]["form"] == "path"
    assert payload["input"]["data_file"].endswith("synth6d.txt")
    assert result.metadata["sample_labels"] == payload["input"]["time_points"]


# 9 --- clusters / filtered_genes shapes ---------------------------------------


def test_clusters_and_filtered_genes_shapes():
    payload = _run_case("c01_guillemin_core").to_dict()
    clusters = payload["clusters"]
    assert clusters, "c01 must produce at least one cluster"
    assert any(c["profile_ids"] for c in clusters)
    for i, cluster in enumerate(clusters):
        assert cluster["id"] == i
        assert cluster["profile_ids"]
    # profiles carrying a cluster id must be members of that cluster
    members_by_id = {c["id"]: set(c["profile_ids"]) for c in clusters}
    for profile in payload["profiles"]:
        cid = profile["cluster"]
        if cid != -1:
            assert profile["id"] in members_by_id[cid]
    for row in payload["filtered_genes"]:
        assert set(row) == {"gene", "probe", "reason"}
        assert row["reason"] in {"repeat_correlation", "missing", "threshold"}


# 10 --- metadata keys ----------------------------------------------------------


def test_metadata_keys():
    payload = _run_case("c14_log_missing").to_dict()
    meta = payload["metadata"]
    for key in (
        "num_genes",
        "num_time_points",
        "num_profiles",
        "input_form",
        "timestamp",
        "sample_labels",
    ):
        assert key in meta, f"metadata missing {key!r}"
    assert "software" not in meta
    assert "reference" not in meta
    assert meta["input_form"] == "path"
    # UTC ISO-8601, second precision (datetime.isoformat(timespec="seconds"))
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", meta["timestamp"]
    )


# 11 --- toy engine run: stem_dataset form + timing ------------------------------


def test_toy_run_input_form_and_timing():
    result = _toy_result()
    assert isinstance(result, STEMResult)
    payload = result.to_dict()
    assert payload["input"]["form"] == "stem_dataset"
    assert payload["input"]["data_file"] is None
    assert payload["input"]["repeat_files"] == []
    assert payload["input"]["time_points"] == ["0h", "1h", "2h", "4h"]
    assert set(payload["timing"]) == TIMING_KEYS
    assert all(v >= 0.0 for v in payload["timing"].values())
    # stem_dataset path skips reading/normalizing; both pre-stages report 0.0
    assert payload["timing"]["input_read"] == 0.0
    assert payload["timing"]["normalize_filter"] == 0.0
    assert payload["timing"]["wall"] >= payload["timing"]["permutation"]
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", payload["metadata"]["timestamp"]
    )
