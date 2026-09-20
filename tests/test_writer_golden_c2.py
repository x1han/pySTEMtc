"""W3: C2 (byte-exact) genetable + profiletable comparison sweeps.

For C2 byte-exact comparison, the writer is invoked with
``encoding="gbk", newline="\\r\\n"`` to reproduce Java's Windows-default
byte stream (Java's ``file.encoding`` on this host is GBK; Java
``PrintWriter`` writes CRLF line terminators).  With those settings the
byte output should match the golden reference file byte-for-byte.

Cases: 14 c01..c14 + 1 headers_custom = 15 cases; each case covers
both genetable and profiletable = 30 C2 comparisons (per spec
round-7.3).

Note: c14 must round-trip the GBK ``-∞`` encoding -- Java's
``NumberFormat.format(-Inf)`` with GBK output writes the bytes
``\\xA1\\xDE`` (two-byte GBK encoding of U+221E).  The writer's
``format_java_double`` produces a Python ``str`` containing ``"-\\u221e"``,
which Python's text I/O with ``encoding="gbk"`` encodes back to
``\\xA1\\xDE``.  This round-trip must hold for c14 to pass C2.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pystemtc.config import STEMConfig
from pystemtc.engine import STEM

GOLDEN = Path(__file__).parent / "golden"
DATA = GOLDEN / "data"
JAVA_REF = GOLDEN / "java_reference"

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
    if name == "headers_custom":
        return STEMConfig.from_defaults_file(
            GOLDEN / "writer_configs" / "headers_custom.txt"
        )
    return STEMConfig.from_defaults_file(
        GOLDEN / "java_configs" / f"{name}.txt"
    )


def _resolve_data_path(config: STEMConfig) -> Path:
    declared = Path(config.data_file)
    candidate_in_data = DATA / declared.name
    if candidate_in_data.exists():
        return candidate_in_data
    candidate_in_headers = GOLDEN / "headers" / declared.name
    if candidate_in_headers.exists():
        return candidate_in_headers
    return (Path(__file__).resolve().parents[1] / declared).resolve()


def _resolve_java_ref(case: str, kind: str) -> Path | None:
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


def _run_case(name: str, tmp_path: Path) -> tuple[bytes, bytes]:
    """Run one config end-to-end and write tables in GBK + CRLF."""
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
    paths = result.write_java_tables(
        tmp_path, encoding="gbk", newline="\r\n",
    )
    py_gene = Path(paths[0]).read_bytes()
    py_prof = Path(paths[1]).read_bytes()
    return py_gene, py_prof


def _format_byte_diff(case, kind, py_bytes, java_bytes):
    diff_at = None
    for i in range(min(len(py_bytes), len(java_bytes))):
        if py_bytes[i] != java_bytes[i]:
            diff_at = i
            break
    msg = [
        f"\n{case} {kind} C2 byte-exact FAIL:",
        f"  py   length={len(py_bytes)}, java length={len(java_bytes)}",
    ]
    if diff_at is not None:
        ctx_lo = max(0, diff_at - 20)
        ctx_hi = min(len(py_bytes), diff_at + 20)
        msg.append(f"  first diff at offset {diff_at}")
        msg.append(f"    py[{ctx_lo}:{ctx_hi}]   = {py_bytes[ctx_lo:ctx_hi]!r}")
        ctx_hi_j = min(len(java_bytes), diff_at + 20)
        msg.append(f"    java[{ctx_lo}:{ctx_hi_j}] = {java_bytes[ctx_lo:ctx_hi_j]!r}")
    else:
        msg.append("  bytes equal up to shorter length (length mismatch)")
    return "\n".join(msg)


@pytest.mark.parametrize("case", CASES)
def test_genetable_c2_byte_exact(case, tmp_path):
    py_bytes, _ = _run_case(case, tmp_path)
    java_path = _resolve_java_ref(case, "genetable")
    if java_path is None:
        pytest.skip(f"Java reference not present for {case}")
    java_bytes = java_path.read_bytes()
    if py_bytes != java_bytes:
        pytest.fail(_format_byte_diff(case, "genetable",
                                       py_bytes, java_bytes))
    assert py_bytes == java_bytes


@pytest.mark.parametrize("case", CASES)
def test_profiletable_c2_byte_exact(case, tmp_path):
    _, py_bytes = _run_case(case, tmp_path)
    java_path = _resolve_java_ref(case, "profiletable")
    if java_path is None:
        pytest.skip(f"Java reference not present for {case}")
    java_bytes = java_path.read_bytes()
    if py_bytes != java_bytes:
        pytest.fail(_format_byte_diff(case, "profiletable",
                                       py_bytes, java_bytes))
    assert py_bytes == java_bytes