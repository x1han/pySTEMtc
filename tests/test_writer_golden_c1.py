"""W2: C1 (decoded-exact) genetable + profiletable comparison sweeps.

For each Java config in ``tests/golden/java_configs/c*.txt`` plus the
``headers_custom`` configuration, this module:

1. Runs pystemtc end-to-end via :class:`pystemtc.engine.STEM`.
2. Writes the genetable and profiletable via :meth:`STEMResult.write_java_tables`.
3. Decodes the Java golden reference file at TEXT level
   (Java writes CRLF on Windows and uses GBK on this host's default
   ``file.encoding``, so we normalize CRLF -> LF and decode GBK for c14).
4. Compares line-by-line at the DECODED level (C1).

Acceptance: every line of pySTEMTC output equals the corresponding line
of the Java golden reference at decoded-text level.  C2 byte-exact is
explicitly out of scope (see :mod:`test_writer_golden_c2` for byte-exact
sweeps that don't depend on file-encoding round-trips).

Total cases: 14 golden configs (c01..c14) + 1 ``headers_custom``
configuration = **15 cases**.  Each case covers BOTH the genetable
and profiletable comparisons, so **30 line-equal assertions total**.
Round-8 final patch: the previous docstring claimed 16/32 because it
incorrectly described the ``headers_custom`` config as two sweeps
(c01-base + c04-base); in reality there is exactly one
``headers_custom`` reference file (under
``tests/golden/java_reference/headers_custom/``), so the matrix is
15 cases x 2 tables = 30.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pystemtc.config import STEMConfig
from pystemtc.engine import STEM

GOLDEN = Path(__file__).parent / "golden"
DATA = GOLDEN / "data"
JAVA_REF = GOLDEN / "java_reference"

# Golden Java configs c01..c14 + the headers_custom sweep.
# c01..c14 are the M3 writer-reference sweep; the headers_custom
# variant uses the in-repo writer_configs/headers_custom.txt config
# (data = tests/golden/headers/custom_header.txt) to verify the
# writer honors ``result.input['gene_header'] / ['probe_header']``
# (Gate B, round-7.2 contract).
CASES: list[str] = [
    "c01_guillemin_core",
    "c02_t0fixed",
    "c03_lognorm",
    "c04_add0",
    "c05_fdr",
    "c06_nocorr",
    "c07_sameperiod",
    "c08_norepeat",
    "c09_synth6",
    "c10_synth6_allperms",
    "c11_synth10",
    "c12_percentile",
    "c13_synth10_missing",
    "c14_log_missing",
    "headers_custom",
]


def _load_config(name: str) -> STEMConfig:
    """Load a config by name.  For ``headers_custom`` the config lives
    under ``tests/golden/writer_configs/``."""
    if name == "headers_custom":
        return STEMConfig.from_defaults_file(
            GOLDEN / "writer_configs" / "headers_custom.txt"
        )
    return STEMConfig.from_defaults_file(
        GOLDEN / "java_configs" / f"{name}.txt"
    )


def _resolve_data_path(config: STEMConfig) -> Path:
    """Resolve a config's data_file against the right test-tree location.

    For c01..c14 configs the data files live under tests/golden/data/.
    For the headers_custom config, the data file lives under
    tests/golden/headers/ (the config's Data_File path is relative to
    the project root, so we honor the relative path when it falls
    inside the workspace).
    """
    declared = Path(config.data_file)
    candidate_in_data = DATA / declared.name
    if candidate_in_data.exists():
        return candidate_in_data
    # headers/custom_header.txt -- the config Data_File uses a relative
    # path under pySTEMtc/tests/golden/headers/
    candidate_in_headers = GOLDEN / "headers" / declared.name
    if candidate_in_headers.exists():
        return candidate_in_headers
    # fall through: resolve relative to the workspace
    return (Path(__file__).resolve().parents[1] / declared).resolve()


def _run_case(name: str, tmp_path: Path) -> tuple[list[str], list[str]]:
    """Run one config end-to-end and write tables to ``tmp_path``."""
    config = _load_config(name)
    data_path = _resolve_data_path(config)
    rep_paths = [DATA / Path(rf).name for rf in (config.repeat_files or [])]
    engine = STEM(
        normalize=config.normalize,
        max_unit_change=config.max_unit_change,
        max_model_profiles=config.max_model_profiles,
        max_correlation=config.max_correlation,
        candidate_cap=config.candidate_cap,
        n_permutations=config.n_permutations,
        permute_t0=config.permute_t0,
        alpha=config.alpha,
        correction=config.correction,
        cluster_min_correlation=config.cluster_min_correlation,
        cluster_corr_percentile=config.cluster_corr_percentile,
        max_missing=config.max_missing,
        min_abs_expr=config.min_abs_expr,
        change_rule="max_minus_min" if config.maxmin else "diff_from_zero",
        repeat_min_correlation=config.repeat_min_correlation,
        repeat_mode=config.repeat_mode,
        spot_included=config.spot_included,
        clustering_method=config.clustering_method,
    )
    result = engine.fit(data_path, replicates=rep_paths)
    paths = result.write_java_tables(tmp_path, encoding="utf-8")
    py_gene = Path(paths[0]).read_text(encoding="utf-8").splitlines()
    py_prof = Path(paths[1]).read_text(encoding="utf-8").splitlines()
    return py_gene, py_prof


def _read_java_ref_decoded(path: Path) -> list[str]:
    """Read a Java-written reference at the DECODED level.

    Java ``PrintWriter`` on this Windows host writes CRLF line terminators
    and encodes Unicode via ``file.encoding`` (GBK here).  For c14
    specifically, ``-Inf`` is rendered as ``-∞`` in GBK (bytes ``A1 DE``)
    rather than as a 3-byte UTF-8 sequence.  Decoding the bytes as GBK
    then re-encoding as UTF-8 yields the same logical text the writer
    produces.  All other reference files happen to be 7-bit ASCII and
    decode identically under UTF-8 or GBK.
    """
    raw = path.read_bytes()
    # Try UTF-8 first (works for all cases except c14); fall back to GBK
    # if a decoding error is raised -- this is the c14 row path.
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk")
    return [line.rstrip("\r") for line in text.splitlines()]


@pytest.mark.parametrize("case", CASES)
def test_genetable_c1_decoded_exact(case, tmp_path):
    py_lines, _ = _run_case(case, tmp_path)
    java_path = _resolve_java_ref(case, "genetable")
    if java_path is None:
        pytest.skip(f"Java reference not present for {case}")
    java_lines = _read_java_ref_decoded(java_path)
    assert py_lines == java_lines, _format_diff(case, "genetable",
                                                 py_lines, java_lines)


@pytest.mark.parametrize("case", CASES)
def test_profiletable_c1_decoded_exact(case, tmp_path):
    _, py_lines = _run_case(case, tmp_path)
    java_path = _resolve_java_ref(case, "profiletable")
    if java_path is None:
        pytest.skip(f"Java reference not present for {case}")
    java_lines = _read_java_ref_decoded(java_path)
    assert py_lines == java_lines, _format_diff(case, "profiletable",
                                                 py_lines, java_lines)


def _resolve_java_ref(case: str, kind: str) -> Path | None:
    """Locate the Java reference file.  For ``headers_custom`` the
    reference lives under ``java_reference/headers_custom/`` (single
    pair of files, not per-config)."""
    direct = JAVA_REF / f"{case}_{kind}.txt"
    if direct.exists():
        return direct
    nested = JAVA_REF / case / f"{case}_{kind}.txt"
    if nested.exists():
        return nested
    nested_alt = JAVA_REF / case / f"{kind}.txt"
    if nested_alt.exists():
        return nested_alt
    return None


def _format_diff(case, kind, py, java):
    """Build a human-readable diff for assertion failure messages."""
    out = [f"\n{case} {kind}: {len(py)} py lines vs {len(java)} java lines"]
    n = min(len(py), len(java))
    shown = 0
    for i in range(n):
        if py[i] != java[i]:
            shown += 1
            if shown <= 5:
                out.append(f"  row {i} DIFF")
                out.append(f"    py:   {py[i]!r}")
                out.append(f"    java: {java[i]!r}")
            else:
                break
    if len(py) != len(java):
        out.append(f"  length differs (py={len(py)}, java={len(java)})")
    return "\n".join(out)