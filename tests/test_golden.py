"""M2 golden verification against the Java batch reference tables.

For EACH of the 14 configs in ``tests/golden/java_configs`` (c01-c12 plus
the round-5 branch fixtures c13/c14) the engine is run
through :meth:`pystemtc.engine.STEM.fit` on the config's Data_File (+ repeats)
and compared against ``java_reference/<case>_profiletable.txt``:

- Level A (exact, string-level): Profile ID (int), Profile Model (via the
  ``Double.toString`` replica), Cluster (int), ``# Genes Assigned`` (a DOUBLE
  — fractional values from 1/k ties are expected; compared via the
  ``Double.toString`` replica), and the genetable gene/probe/Profile columns
  (ties joined with ";" in ascending model-index order) plus row order for
  ALL rows.
- Level B (exact-first, must NOT be loosened): ``# Gene Expected``
  (``Double.toString`` replica) and p-value (``Util.doubleToSz`` replica);
  any string mismatch fails the test.

Config Data_File / Repeat_Data_Files paths are relative to D:/stem (e.g.
``g27_1.txt``); the frozen c09/c10/c11 configs carry the historical pre-rename
``STEMpy/tests/golden/data/...`` prefix. Values are resolved against D:/stem
first, the project checkout second, then by basename under the bundled
``tests/golden/data`` copies.
"""

from pathlib import Path

import pytest

from pystemtc.config import STEMConfig
from pystemtc.engine import STEM
from pystemtc.javaformat import double_to_sz, java_double_to_string

GOLDEN = Path(__file__).parent / "golden"
CONFIGS = GOLDEN / "java_configs"
REFERENCE = GOLDEN / "java_reference"

# D:/stem (repo root, where stem.jar batch ran) then D:/stem/pySTEMtc.
_ROOTS = [GOLDEN.parents[1].parent, GOLDEN.parents[1]]

ALL_CASES = sorted(p.stem for p in CONFIGS.glob("*.txt"))

_RESULTS: dict[str, object] = {}


def _resolve(value: str) -> Path:
    for root in _ROOTS:
        candidate = root / value
        if candidate.exists():
            return candidate
    # c09/c10/c11 keep the pre-rename "STEMpy/..." prefix on disk; the bundled
    # copies under golden/data are content-identical to what stem.jar consumed.
    fallback = GOLDEN / "data" / Path(value).name
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"config data file {value!r} not found under {_ROOTS}")


def _run_case(case: str):
    """Run the full engine pipeline once per case (results are cached across
    the profiletable/genetable parametrizations)."""
    if case in _RESULTS:
        return _RESULTS[case]

    cfg = STEMConfig.from_defaults_file(CONFIGS / f"{case}.txt")
    engine = STEM(
        normalize=cfg.normalize,
        max_unit_change=cfg.max_unit_change,
        max_model_profiles=cfg.max_model_profiles,
        max_correlation=cfg.max_correlation,
        candidate_cap=cfg.candidate_cap,
        n_permutations=cfg.n_permutations,
        permute_t0=cfg.permute_t0,
        alpha=cfg.alpha,
        correction=cfg.correction,
        cluster_min_correlation=cfg.cluster_min_correlation,
        cluster_corr_percentile=cfg.cluster_corr_percentile,
        max_missing=cfg.max_missing,
        min_abs_expr=cfg.min_abs_expr,
        change_rule="max_minus_min" if cfg.maxmin else "diff_from_zero",
        repeat_min_correlation=cfg.repeat_min_correlation,
        repeat_mode=cfg.repeat_mode,
        spot_included=cfg.spot_included,
    )
    result = engine.fit(
        _resolve(cfg.data_file),
        replicates=[_resolve(f) for f in cfg.repeat_files] or None,
    )
    _RESULTS[case] = result
    return result


def _read_golden_text(path: Path) -> str:
    # Java's batch writer uses the platform default charset of the oracle
    # box (GBK here); c14's -Inf cells are GBK 0xA1DE ("∞"). ASCII tables
    # decode identically under either, so GBK is the deterministic choice.
    return path.read_bytes().decode("gbk")


def _read_profile_table(case: str):
    lines = _read_golden_text(REFERENCE / f"{case}_profiletable.txt").splitlines()
    header = lines[0].split("\t")
    assert header == [
        "Profile ID",
        "Profile Model",
        "Cluster (-1 non-significant)",
        "# Genes Assigned",
        "# Gene Expected",
        "p-value",
    ]
    return [line.split("\t") for line in lines[1:] if line != ""]


def _read_gene_table(case: str):
    lines = _read_golden_text(REFERENCE / f"{case}_genetable.txt").splitlines()
    header = lines[0].split("\t")
    assert header[2] == "Profile"
    return header, [line.split("\t") for line in lines[1:] if line != ""]


def _rel_err(value: float, printed: str) -> float:
    if "E" in printed:
        mantissa, _, exponent = printed.partition("E")
        want = float(mantissa) * 10.0 ** int(exponent)
    else:
        want = float(printed)
    if want == 0.0:
        return abs(value - want)
    return abs(value - want) / abs(want)


@pytest.mark.parametrize("case", ALL_CASES)
def test_golden_profiletable(case):
    result = _run_case(case)
    rows = _read_profile_table(case)

    assert len(rows) == len(result.profiles), (
        f"{case}: profile count {len(result.profiles)} != golden {len(rows)}"
    )

    level_a_failures = []
    level_b_failures = []
    for i, (row, rec) in enumerate(zip(rows, result.profiles)):
        # --- Level A: exact ---
        got = [
            str(rec.id),
            ",".join(java_double_to_string(v) for v in rec.model),
            str(rec.cluster),
            java_double_to_string(rec.n_assigned),
        ]
        want = [row[0], row[1], row[2], row[3]]
        for label, g, w in zip(
            ("Profile ID", "Profile Model", "Cluster", "# Genes Assigned"), got, want
        ):
            if g != w:
                level_a_failures.append(f"row {i} {label}: got {g!r} want {w!r}")

        # --- Level B: exact-first (any mismatch fails; error shown) ---
        got_expected = java_double_to_string(rec.n_expected)
        if got_expected != row[4]:
            level_b_failures.append(
                f"row {i} # Gene Expected: got {got_expected!r} want {row[4]!r} "
                f"(rel={_rel_err(rec.n_expected, row[4]):.3g})"
            )
        got_p = double_to_sz(rec.p_value)
        if got_p != row[5]:
            level_b_failures.append(
                f"row {i} p-value: got {got_p!r} want {row[5]!r} "
                f"(rel={_rel_err(rec.p_value, row[5]):.3g})"
            )

    assert not level_a_failures, (
        f"{case}: Level A mismatches (exact required):\n"
        + "\n".join(level_a_failures[:20])
    )
    assert not level_b_failures, (
        f"{case}: Level B string mismatches (exact-first):\n"
        + "\n".join(level_b_failures[:20])
    )


@pytest.mark.parametrize("case", ALL_CASES)
def test_golden_genetable(case):
    result = _run_case(case)
    header, rows = _read_gene_table(case)
    numcols = len(header) - 3

    assert numcols == result.metadata["num_time_points"], (
        f"{case}: genetable column count {numcols} != "
        f"{result.metadata['num_time_points']}"
    )
    assert len(rows) == len(result.gene_assignments), (
        f"{case}: genetable rows {len(result.gene_assignments)} != golden {len(rows)}"
    )

    failures = []
    for i, (row, gene) in enumerate(zip(rows, result.gene_assignments)):
        # gene/probe/Profile columns + row order (Level A exact)
        if row[0] != gene.gene:
            failures.append(f"row {i} gene: got {gene.gene!r} want {row[0]!r}")
        if row[1] != gene.probe:
            failures.append(f"row {i} probe: got {gene.probe!r} want {row[1]!r}")
        if row[2] != gene.profile:
            failures.append(f"row {i} Profile: got {gene.profile!r} want {row[2]!r}")

    assert not failures, (
        f"{case}: genetable Level A mismatches:\n" + "\n".join(failures[:20])
    )
