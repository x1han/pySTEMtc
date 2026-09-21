"""W1: writer unit tests for STEMResult.write_java_tables (round-8).

These exercise the writer's contract directly, without crossing into the
golden C1/C2 byte-comparison sweeps (those are W2 and W3):

- format_java_double / double_to_sz / java_double_to_string fidelity at
  the cell level (cross-checked against JRE 1.8.0_451)
- genetable per-cell rule (empty when pma=0 EXCEPT last column)
- profile table 6-column shape and model-coordinate comma join
- writer discipline (LF line endings, UTF-8 encoding, errors=replace
  fixed at the writer boundary)
- public API surface: returns list[str] with two absolute paths

The 30 C1 sweeps live in ``test_writer_golden_c1.py`` and the 30 C2
sweeps in ``test_writer_golden_c2.py``.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

from pystemtc.javaformat import (
    double_to_sz,
    format_java_double,
    java_double_to_string,
)
from pystemtc.result import (
    LINE_TERMINATOR,
    STEMResult,
    GeneAssignment,
    ProfileRecord,
)


# =====================================================================
# format_java_double -- cell-level fidelity (verified against JRE 1.8.0_451)
# =====================================================================


@pytest.mark.parametrize(
    "value, expected",
    [
        # --- small-range binary HALF_EVEN (ST.java:3017-3019) ---
        (2.675, "2.67"),
        (-0.0, "-0.00"),
        (0.0, "0.00"),
        (999.995, "1,000.00"),
        (-999.995, "-1,000.00"),
        (-2.675, "-2.67"),
        (0.005, "0.01"),  # round-up at boundary
        (0.004, "0.00"),  # round-down at boundary
        # --- large-finite E-notation path (Gate A JRE8 probe) ---
        (1e30, "1,000,000,000,000,000,000,000,000,000,000.00"),
        (-1e30, "-1,000,000,000,000,000,000,000,000,000,000.00"),
        # 1e100: int part = "1" + 100 zeros = 101 digits = 34 groups
        # (first group "10", then 33 groups of "000")
        (1e100, ",".join(["10"] + ["000"] * 33) + ".00"),
        # 1e308: int part = "1" + 308 zeros = 309 digits = 103 groups
        # (first group "100", then 102 groups of "000")
        (1e308, ",".join(["100"] + ["000"] * 102) + ".00"),
        # --- non-finite ---
        (float("nan"), "\ufffd"),
        (float("inf"), "\u221e"),
        (-float("inf"), "-\u221e"),
    ],
)
def test_format_java_double_cell_fidelity(value, expected):
    assert format_java_double(value) == expected


# =====================================================================
# double_to_sz -- profile-table p-value (Util.doubleToSz)
# =====================================================================


@pytest.mark.parametrize(
    "value, expected",
    [
        (1.3e-11, "1.3E-11"),  # small-magnitude E-notation
        (3.5e-36, "3.5E-36"),
        (0.5, "0.50"),
        (1.0, "1.00"),
        (0.0, "0.00"),  # <=0 -> "0.00"
        (-1.0, "0.00"),  # negative -> "0.00" (Util line 156-157)
        (float("nan"), "\ufffd"),  # NumberFormat(NaN) = U+FFFD
    ],
)
def test_double_to_sz_pvalue(value, expected):
    assert double_to_sz(value) == expected


# =====================================================================
# java_double_to_string -- profile-model coords + counts (Double.toString)
# =====================================================================


@pytest.mark.parametrize(
    "value, expected",
    [
        (0.0, "0.0"),
        (-1.0, "-1.0"),
        (1.0, "1.0"),
        (-2.0, "-2.0"),
        (3.0, "3.0"),
        (45.0, "45.0"),  # Java prints 45.0 not 45
        (42.7, "42.7"),
        (8.5, "8.5"),
    ],
)
def test_java_double_to_string_default(value, expected):
    assert java_double_to_string(value) == expected


# =====================================================================
# Helper: build a minimal STEMResult for writer tests
# =====================================================================


def _make_result(genes, profiles, time_points, gene_header="Gene Symbol",
                 probe_header="SPOT", *, data_file="g27_1.txt"):
    """Build a minimal STEMResult for writer tests.

    ``data_file`` defaults to ``"g27_1.txt"`` (path-derived; stem
    ``"g27_1"`` is used by ``write_java_tables`` when ``prefix=None``).
    Pass ``data_file=None`` to simulate a DataFrame-derived result
    (where ``prefix=None`` MUST raise ``ValueError``).
    """
    input_dict = {
        "gene_header": gene_header,
        "probe_header": probe_header,
        "time_points": list(time_points),
    }
    if data_file is not None:
        input_dict["data_file"] = data_file
    return STEMResult(
        profiles=profiles,
        gene_assignments=genes,
        filtered_genes=[],
        clusters=[],
        config={},
        metadata={},
        input=input_dict,
    )


def _gene(name, probe, profile_ids, values, present):
    return GeneAssignment(
        gene=name,
        probe=probe,
        profile_ids=list(profile_ids),
        values=list(values),
        present=list(present),
    )


def _profile(pid, model, cluster=-1, n_assigned=0.0, n_expected=0.0,
             p_value=1.0, significant=False):
    return ProfileRecord(
        id=pid,
        model=list(model),
        cluster=cluster,
        n_assigned=n_assigned,
        n_expected=n_expected,
        p_value=p_value,
        significant=significant,
    )


# =====================================================================
# Genetable: per-cell rule (ST.java:3021-3033)
# =====================================================================


def test_genetable_header_no_self_injected_zero(tmp_path: Path):
    """The writer must NOT self-inject a '0' column; the time_points list
    from result.input is used verbatim.  The Java genetable header is
    ``gene_header\tprobe_header\tProfile\t<time_points[0]>\t...\t<time_points[T-1]>``
    -- exactly T+3 fields."""
    r = _make_result(
        genes=[],
        profiles=[_profile(0, [0.0, 0.0, 0.0])],
        time_points=["0h", "1h", "2h"],
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[0]).read_text(encoding="utf-8")
    lines = text.split(LINE_TERMINATOR)
    assert lines[0] == "Gene Symbol\tSPOT\tProfile\t0h\t1h\t2h", (
        f"unexpected header: {lines[0]!r}")


def test_genetable_header_custom_columns(tmp_path: Path):
    """Custom gene_header / probe_header / time_points must flow through."""
    r = _make_result(
        genes=[],
        profiles=[_profile(0, [0.0, 0.0, 0.0])],
        time_points=["t0", "t1"],
        gene_header="MyGene",
        probe_header="MyProbe",
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[0]).read_text(encoding="utf-8")
    assert text.split(LINE_TERMINATOR)[0] == \
        "MyGene\tMyProbe\tProfile\tt0\tt1"


def test_genetable_cell_empty_when_pma0_interior(tmp_path: Path):
    """Cells j in [0..T-2] with present[j]==False must render empty
    between tabs (NOT '0.00' and NOT the value payload)."""
    r = _make_result(
        genes=[_gene("A", "p1", [0],
                     [1.5, 2.5, 3.5],
                     [True, False, True])],
        profiles=[_profile(0, [0.0, 0.0, 0.0])],
        time_points=["t0", "t1", "t2"],
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[0]).read_text(encoding="utf-8")
    lines = text.split(LINE_TERMINATOR)
    # data row: gene\tprobe\tprofile\tt0_cell\tt1_cell_empty\tt2_cell
    assert lines[1] == "A\tp1\t0\t1.50\t\t3.50", (
        f"interior missing cell not rendered empty: {lines[1]!r}")


def test_genetable_cell_LAST_COLUMN_always_rendered_even_when_pma0(tmp_path: Path):
    """The LAST column (j == T-1) is ALWAYS rendered, even when
    present[T-1] == False.  This is Java's unconditional
    ``pw.println(\t+nf2.format(...))`` after the conditional loop --
    the user's spec pins this as a writer contract (NOT a bug to
    paper over)."""
    r = _make_result(
        genes=[_gene("A", "p1", [0],
                     [1.5, 2.5, 3.5],
                     [True, True, False])],
        profiles=[_profile(0, [0.0, 0.0, 0.0])],
        time_points=["t0", "t1", "t2"],
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[0]).read_text(encoding="utf-8")
    lines = text.split(LINE_TERMINATOR)
    # last column rendered even when present[T-1]==False
    assert lines[1] == "A\tp1\t0\t1.50\t2.50\t3.50", (
        f"last column not unconditionally rendered: {lines[1]!r}")


def test_genetable_signed_zero_renders_minus(tmp_path: Path):
    """-0.0 must render as '-0.00' (Java signed zero behavior)."""
    r = _make_result(
        genes=[_gene("A", "p1", [0],
                     [-0.0, 0.0, 0.0],
                     [True, True, True])],
        profiles=[_profile(0, [0.0, 0.0, 0.0])],
        time_points=["t0", "t1", "t2"],
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[0]).read_text(encoding="utf-8")
    lines = text.split(LINE_TERMINATOR)
    assert lines[1] == "A\tp1\t0\t-0.00\t0.00\t0.00"


def test_genetable_inf_renders_infinity_glyph(tmp_path: Path):
    """+Inf / -Inf render as U+221E with sign preserved."""
    r = _make_result(
        genes=[_gene("A", "p1", [0],
                     [float("inf"), -float("inf"), 0.0],
                     [True, True, True])],
        profiles=[_profile(0, [0.0, 0.0, 0.0])],
        time_points=["t0", "t1", "t2"],
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[0]).read_text(encoding="utf-8")
    lines = text.split(LINE_TERMINATOR)
    assert lines[1] == "A\tp1\t0\t\u221e\t-\u221e\t0.00"


def test_genetable_tied_profile_ids_semicolon_join(tmp_path: Path):
    """Tied best assignments render as ``pid_a;pid_b;pid_c`` (Java ST.java:3014)."""
    r = _make_result(
        genes=[_gene("A", "p1", [3, 7, 11],
                     [1.0, 2.0, 3.0],
                     [True, True, True])],
        profiles=[_profile(3, [0.0, 0.0, 0.0]),
                  _profile(7, [0.0, 0.0, 0.0]),
                  _profile(11, [0.0, 0.0, 0.0])],
        time_points=["t0", "t1", "t2"],
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[0]).read_text(encoding="utf-8")
    lines = text.split(LINE_TERMINATOR)
    assert lines[1] == "A\tp1\t3;7;11\t1.00\t2.00\t3.00"


# =====================================================================
# Profile table: 6-column shape + comma join
# =====================================================================


def test_profiletable_six_column_header(tmp_path: Path):
    """The 6-column header is HARDCODED (non-kmeans branch)."""
    r = _make_result(
        genes=[],
        profiles=[_profile(0, [0.0, -1.0, 1.0], cluster=-1,
                           n_assigned=10.0, n_expected=8.5, p_value=0.5)],
        time_points=["t0", "t1", "t2"],
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[1]).read_text(encoding="utf-8")
    lines = text.split(LINE_TERMINATOR)
    assert lines[0] == \
        "Profile ID\tProfile Model" \
        "\tCluster (-1 non-significant)" \
        "\t# Genes Assigned\t# Gene Expected\tp-value"


def test_profiletable_model_coords_comma_join(tmp_path: Path):
    """Profile model coords join with ',' (Java String concat default,
    no spaces).  java_double_to_string supplies the coord text."""
    r = _make_result(
        genes=[],
        profiles=[_profile(0, [0.0, -2.0, -3.0, -4.0, -2.0], cluster=-1,
                           n_assigned=45.0, n_expected=42.7, p_value=0.38)],
        time_points=["t0"] * 5,
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[1]).read_text(encoding="utf-8")
    lines = text.split(LINE_TERMINATOR)
    assert lines[1] == "0\t0.0,-2.0,-3.0,-4.0,-2.0\t-1\t45.0\t42.7\t0.38", (
        f"unexpected profile row: {lines[1]!r}")


def test_profiletable_cluster_minus_one_renders_minus_one(tmp_path: Path):
    """cluster=-1 (non-significant) prints as the int ``-1``, not the
    string ``-1.0`` (Java ST.java:2950-2954)."""
    r = _make_result(
        genes=[],
        profiles=[_profile(7, [0.0, 0.0], cluster=-1,
                           n_assigned=5.0, n_expected=4.0, p_value=1.0)],
        time_points=["t0", "t1"],
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[1]).read_text(encoding="utf-8")
    lines = text.split(LINE_TERMINATOR)
    assert lines[1] == "7\t0.0,0.0\t-1\t5.0\t4.0\t1.00"


def test_profiletable_pvalue_uses_double_to_sz(tmp_path: Path):
    """p-value uses double_to_sz (NOT format_java_double with 2 fraction
    digits).  Small p-values render in E-notation with 1 fraction digit."""
    r = _make_result(
        genes=[],
        profiles=[_profile(0, [0.0, 0.0], cluster=-1,
                           n_assigned=84.0, n_expected=36.9, p_value=1.3e-11)],
        time_points=["t0", "t1"],
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[1]).read_text(encoding="utf-8")
    lines = text.split(LINE_TERMINATOR)
    # p_value 1.3e-11 -> double_to_sz -> "1.3E-11"
    assert lines[1].endswith("\t84.0\t36.9\t1.3E-11"), (
        f"p-value not via double_to_sz: {lines[1]!r}")


# =====================================================================
# Writer discipline: line endings, encoding, API surface
# =====================================================================


def test_writer_uses_raw_lf(tmp_path: Path):
    """With ``newline='\\n'`` (raw LF, no translation), no CR (0x0d)
    bytes are introduced.  Java writes CRLF on Windows; this is the
    raw-LF discipline that pairs with the C1 test sweeps (which
    normalize CRLF -> LF before comparison)."""
    r = _make_result(
        genes=[_gene("A", "p1", [0],
                     [1.0, 2.0, 3.0],
                     [True, True, True])],
        profiles=[_profile(0, [0.0, 0.0, 0.0])],
        time_points=["t0", "t1", "t2"],
    )
    paths = r.write_java_tables(tmp_path, encoding="utf-8", newline="\n")
    for p in paths:
        raw = Path(p).read_bytes()
        assert b"\r" not in raw, f"{p} contains CR bytes"
        # LF present (rows are LF-terminated)
        assert raw.count(b"\n") >= 1


def test_writer_default_newline_matches_platform(tmp_path: Path):
    """With ``newline=None`` (default, platform default), the writer
    defers newline translation to Python's text I/O layer.  The
    resulting byte stream must therefore reflect the host platform's
    text newline: ``os.linesep`` is ``b"\\r\\n"`` on Windows and
    ``b"\\n"`` on POSIX.  This is the round-7.3 frozen discipline:
    ``None`` means "platform default", not "raw LF" and not
    "CRLF on every platform".  The canonical Java C2 byte-exact
    path (``encoding="gbk", newline="\\r\\n"``) is a separate
    contract tested by the W3 sweeps; this test only verifies the
    platform-default behavior.
    """
    r = _make_result(
        genes=[_gene("A", "p1", [0],
                     [1.0, 2.0, 3.0],
                     [True, True, True])],
        profiles=[_profile(0, [0.0, 0.0, 0.0])],
        time_points=["t0", "t1", "t2"],
    )
    paths = r.write_java_tables(tmp_path)  # encoding=None, newline=None
    expected_eol = os.linesep.encode()
    for p in paths:
        raw = Path(p).read_bytes()
        # File must end with the platform EOL.
        assert raw.endswith(expected_eol), (
            f"{p} does not end with the platform default EOL "
            f"({expected_eol!r}); got tail {raw[-16:]!r}"
        )
        if os.linesep == "\r\n":
            # Windows host: CRLF must appear somewhere in the stream.
            assert b"\r\n" in raw, (
                f"{p} missing CRLF row terminator on Windows host"
            )
        else:
            # POSIX host: no CRLF should be present; LF is the only
            # row terminator.
            assert b"\r\n" not in raw, (
                f"{p} unexpectedly contains CRLF on POSIX host"
            )
            assert b"\n" in raw, (
                f"{p} missing LF row terminator on POSIX host"
            )


def test_writer_explicit_crlf_translates_lf_only(tmp_path: Path):
    """When ``newline='\\r\\n'`` is passed to the writer, Python text
    I/O translates ``\\n`` -> ``\\r\\n`` -- but the writer only ever
    writes raw ``\\n`` (see :data:`LINE_TERMINATOR`), so the result
    is exactly one CR per row, never ``\\r\\r\\n``.  This is the
    round-7.7 P1-3 fix: if we had ALSO concatenated
    ``line + newline_str`` we would emit double CR."""
    r = _make_result(
        genes=[_gene("A", "p1", [0],
                     [1.0, 2.0, 3.0],
                     [True, True, True])],
        profiles=[_profile(0, [0.0, 0.0, 0.0])],
        time_points=["t0", "t1", "t2"],
    )
    paths = r.write_java_tables(tmp_path, encoding="gbk", newline="\r\n")
    for p in paths:
        raw = Path(p).read_bytes()
        assert b"\r\r\n" not in raw, (
            f"{p} contains double-CRLF (LF was added twice)"
        )
        # every row ends with exactly one CRLF
        assert raw.endswith(b"\r\n")
        # CR count equals LF count (1:1, never 2:1)
        assert raw.count(b"\r") == raw.count(b"\n")


def test_writer_encodes_utf8(tmp_path: Path):
    """U+FFFD and U+221E must round-trip as UTF-8 (not GBK / cp1252).
    The byte oracle assets under tests/golden/java_reference/** use
    GBK (Java's default Windows file.encoding) and so cannot be
    compared byte-exact against this output."""
    r = _make_result(
        genes=[_gene("A", "p1", [0],
                     [float("nan"), float("inf"), -float("inf")],
                     [True, True, True])],
        profiles=[_profile(0, [0.0, 0.0, 0.0])],
        time_points=["t0", "t1", "t2"],
    )
    paths = r.write_java_tables(tmp_path)
    raw = Path(paths[0]).read_bytes()
    assert b"\xef\xbf\xbd" in raw  # UTF-8 for U+FFFD
    assert b"\xe2\x88\x9e" in raw  # UTF-8 for U+221E
    # The two-byte GBK sequence for U+221E is A1 DE -- must NOT appear
    assert b"\xa1\xde" not in raw
    # GBK '?' for NaN (0x3F) -- must NOT appear in place of U+FFFD


def test_write_java_tables_returns_two_string_paths(tmp_path: Path):
    """The contract: ``write_java_tables(out_dir) -> [str, str]``
    with [0] = genetable, [1] = profiletable, both absolute."""
    r = _make_result(
        genes=[],
        profiles=[],
        time_points=["t0", "t1"],
    )
    paths = r.write_java_tables(tmp_path)
    assert isinstance(paths, list)
    assert len(paths) == 2
    assert all(isinstance(p, str) for p in paths)
    g, p = paths
    assert Path(g).is_absolute()
    assert Path(p).is_absolute()
    # default data_file='g27_1.txt' -> stem 'g27_1'
    assert Path(g).name == "g27_1_genetable.txt"
    assert Path(p).name == "g27_1_profiletable.txt"


def test_writer_prefix_explicit_overrides_default_stem(tmp_path: Path):
    """``prefix="abc"`` must be used verbatim, ignoring the
    data_file stem."""
    r = _make_result(genes=[], profiles=[],
                     time_points=["t0"])  # default data_file="g27_1.txt"
    paths = r.write_java_tables(tmp_path, prefix="abc")
    assert Path(paths[0]).name == "abc_genetable.txt"
    assert Path(paths[1]).name == "abc_profiletable.txt"
    assert Path(paths[0]).exists()
    assert Path(paths[1]).exists()


def test_writer_prefix_default_is_data_file_stem(tmp_path: Path):
    """``prefix=None`` (default) -> derive from ``result.input['data_file']``
    stem.  ``g27_1.txt`` -> ``g27_1``."""
    r = _make_result(genes=[], profiles=[], time_points=["t0"],
                     data_file="foo/bar/baz.tsv")
    paths = r.write_java_tables(tmp_path)
    assert Path(paths[0]).name == "baz_genetable.txt"
    assert Path(paths[1]).name == "baz_profiletable.txt"


def test_writer_prefix_dataframe_raises_value_error(tmp_path: Path):
    """DataFrame input has ``data_file=None`` -> ``prefix=None``
    MUST raise ``ValueError`` (round-7.3 frozen contract, restored
    round-8 final patch)."""
    r = _make_result(genes=[], profiles=[], time_points=["t0"],
                     data_file=None)
    with pytest.raises(ValueError, match="prefix is required"):
        r.write_java_tables(tmp_path)


def test_writer_nan_gbk_encoding_yields_question_mark_byte(tmp_path: Path):
    """When ``encoding='gbk'`` is passed, ``format_java_double(NaN)``
    must round-trip to Java's GBK oracle byte ``0x3F`` (``?``).
    U+FFFD encoded as GBK -> ``?``; Python's text I/O does this
    automatically, so the writer's only job is to surface ``U+FFFD``
    (verified by :func:`format_java_double` already)."""
    r = _make_result(
        genes=[_gene("A", "p1", [0],
                     [float("nan")],
                     [True])],
        profiles=[_profile(0, [0.0])],
        time_points=["t0"],
    )
    paths = r.write_java_tables(tmp_path, encoding="gbk", newline="\r\n")
    raw = Path(paths[0]).read_bytes()
    # Last column (T-1=0) is always rendered -> 0x3F appears once
    assert b"\x3f" in raw, (
        f"GBK output must contain 0x3F (Java's NaN oracle byte); got {raw!r}"
    )


def test_genetable_cell_missing_interior_overrides_nan_payload(tmp_path: Path):
    """FINAL-A round-1: an INTERIOR cell (j < T-1) with ``present=False``
    MUST render as the empty cell, regardless of the stored payload
    (NaN, Inf, any value).  The Java loop at ST.java:3021-3033 writes
    ``pw.print("\\t")`` (no value) whenever ``pma[i][j] == 0`` for the
    conditional range.  The LAST column (j == T-1) is unconditional.

    This protects against a class of bug where ``present[j]==False``
    is silently ignored because the stored double happens to be NaN
    (which ``format_java_double`` would render as U+FFFD)."""
    r = _make_result(
        genes=[_gene("A", "p1", [0],
                     # t0 = finite, t1 = NaN (would render U+FFFD if
                     # not skipped), t2 = finite LAST COLUMN
                     [1.5, float("nan"), 3.5],
                     # interior cell t1 is missing -> must be empty
                     [True, False, True])],
        profiles=[_profile(0, [0.0, 0.0, 0.0])],
        time_points=["t0", "t1", "t2"],
    )
    paths = r.write_java_tables(tmp_path, encoding="utf-8", newline="\n")
    text = Path(paths[0]).read_text(encoding="utf-8")
    # data row: gene \t probe \t profile \t 1.50 \t <EMPTY> \t 3.50
    data_row = text.split(LINE_TERMINATOR)[1]
    assert data_row == "A\tp1\t0\t1.50\t\t3.50", (
        f"interior missing+NaN must render empty, got: {data_row!r}"
    )
    # U+FFFD must NOT appear anywhere in the file (the missing cell
    # overrode the NaN payload)
    assert "\ufffd" not in text


def test_write_java_tables_creates_out_dir(tmp_path: Path):
    """Nested non-existent ``out_dir`` must be created (mkdir -p semantics)."""
    nested = tmp_path / "a" / "b" / "c"
    assert not nested.exists()
    r = _make_result(genes=[], profiles=[], time_points=["t0"])
    paths = r.write_java_tables(nested)
    assert nested.is_dir()
    for p in paths:
        assert Path(p).exists()


def test_line_terminator_constant_pinned():
    """LINE_TERMINATOR is pinned to ``\\n`` (raw LF) -- do NOT silently
    change to ``os.linesep`` or CRLF.  C2 byte-exact comparison against
    the byte oracle is explicitly OUT of scope for this writer; CRLF
    would only matter if we restored byte-exact."""
    assert LINE_TERMINATOR == "\n"


def test_format_java_double_handles_nan_signbit_independent():
    """Python float NaN has no signed-zero concept, but the format
    function must still emit U+FFFD (not split on +/-).  Java's
    NumberFormat.format(NaN) is always U+FFFD regardless of payload."""
    assert format_java_double(float("nan")) == "\ufffd"
    assert format_java_double(float("-nan")) == "\ufffd"


def test_format_java_double_one_zero_does_not_render_negative():
    """Positive 0.0 (no sign bit) renders as '0.00', not '-0.00'."""
    assert format_java_double(0.0) == "0.00"


def test_genetable_empty_gene_list_writes_only_header(tmp_path: Path):
    """An empty gene list yields header-only output (zero data rows).
    This is a degenerate case but the writer must not crash."""
    r = _make_result(
        genes=[],
        profiles=[_profile(0, [0.0, 0.0])],
        time_points=["t0", "t1"],
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[0]).read_text(encoding="utf-8")
    # Exactly one line (the header) + trailing LF
    assert text.count(LINE_TERMINATOR) == 1
    assert text.split(LINE_TERMINATOR)[0] == "Gene Symbol\tSPOT\tProfile\tt0\tt1"


def test_genetable_probe_header_names_not_subject_correct(tmp_path: Path):
    """Java's 'Profile' column header is HARD-CODED -- it is NOT taken
    from ``input`` (Java's ST.java:2992-2999 picks 'Cluster' or 'Profile'
    based on the bkmeans flag; the writer currently pins 'Profile')."""
    r = _make_result(
        genes=[],
        profiles=[_profile(0, [0.0, 0.0])],
        time_points=["t0", "t1"],
    )
    paths = r.write_java_tables(tmp_path)
    text = Path(paths[0]).read_text(encoding="utf-8")
    assert "\tProfile\t" in text.split(LINE_TERMINATOR)[0]