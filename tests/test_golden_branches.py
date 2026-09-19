"""Branch-arrival assertions for the c13/c14 golden extensions (spec 03 §1.9).

The golden string comparisons prove engine agreement; these tests prove the
target branches are actually REACHED. A fixture whose missing rows get
filtered before permutation would otherwise pass vacuously — round-5 review
N2 requires branch-targeted fixtures plus test-side arrival proof.

Also pins the round-5 ``legacy_with_replacement`` semantics (spec 03 §1.7).
"""

from pathlib import Path

from test_golden import _run_case

DATA = Path(__file__).parent / "golden" / "data"


def _read_rows(path: Path) -> list[list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("SPOT\tGene Symbol\t")
    return [line.split("\t") for line in lines[1:] if line != ""]


# --- c13: on-the-fly x missing x masked correlation (spec 03 §1.9) ---


def test_synth10m_deterministic_pattern():
    rows = _read_rows(DATA / "synth10m.txt")
    assert len(rows) == 300
    n_missing = 0
    for i, cells in enumerate(rows):
        vals = cells[2:]
        assert vals[0] != "", f"row {i}: t0 must never be missing"
        blanks = [j for j, v in enumerate(vals) if v == ""]
        if i % 3 == 2:
            assert blanks == [(i % 9) + 1], f"row {i}: expected one blank at (i%9)+1"
            n_missing += 1
        else:
            assert blanks == [], f"row {i}: unexpected blanks {blanks}"
    assert n_missing == 100


def test_c13_missing_reaches_on_the_fly():
    result = _run_case("c13_synth10_missing")
    assert result.metadata["permutation_mode"] == "on_the_fly"
    assert result.metadata["legacy_with_replacement"] is True
    # Surviving genes still carrying a non-t0 missing cell at gene level
    # (merged pma=0): these are the rows that hit the legality check
    # (STEM_DataSet.java:1223) and masked correlation inside the on-the-fly
    # permutation loop. Dup-rescued rows correctly do not count.
    missing_survivors = [g for g in result.gene_assignments if not all(g.present[1:])]
    assert len(missing_survivors) >= 10, (
        f"only {len(missing_survivors)} surviving genes with non-t0 missing — "
        "the on-the-fly masked path would be untested"
    )


# --- c14: log re-reference quirk x universe path x missing (spec 03 §1.9) ---


def test_synth6d_deterministic_pattern():
    rows = _read_rows(DATA / "synth6d.txt")
    assert len(rows) == 240
    for i, cells in enumerate(rows):
        gene, vals = cells[1], cells[2:]
        assert vals[0] != "" and float(vals[0]) > 0, f"row {i}: t0 must be present and positive"
        if i < 200:  # dup pairs: row 2i primary, row 2i+1 secondary
            if i % 2 == 0:
                # primary: complete and strictly positive (log-safe)
                assert all(v != "" and float(v) > 0 for v in vals), f"row {i} ({gene})"
            else:
                pair = i // 2
                if pair < 50:  # G1: blank -> log(0) = -Inf route
                    assert gene.startswith("G1_") and vals[2] == ""
                else:  # G2: negative -> loader pma=0 -> log(neg) = NaN route
                    assert gene.startswith("G2_") and float(vals[2]) < 0
                others = [v for j, v in enumerate(vals) if j != 2]
                assert all(v != "" and float(v) > 0 for v in others)
        else:  # singles: every 3rd has one blank at a non-t0 index
            blanks = [j for j, v in enumerate(vals) if v == ""]
            present = [float(v) for v in vals if v != ""]
            assert all(v > 0 for v in present)
            if (i - 200) % 3 == 0:
                assert len(blanks) == 1 and blanks[0] >= 2
            else:
                assert blanks == []


def test_c14_log_missing_reaches_universe_path():
    result = _run_case("c14_log_missing")
    # permute_t0=true with T=6 gives universe 6! = 720 (generatepermutations,
    # STEM_DataSet.java:1093/:1468); 50 < 720 -> deterministic subsampling.
    assert result.metadata["permutation_mode"] == "subsample_universe"
    assert result.metadata["legacy_with_replacement"] is True
    survivors = {g.gene for g in result.gene_assignments}
    g1 = [g for g in survivors if g.startswith("G1_")]
    g2 = [g for g in survivors if g.startswith("G2_")]
    # Both defect groups must survive filtering, or the -Inf route (G1) and
    # the literal-NaN route (G2) through the log-mode re-reference median
    # (:1221-1275) would be untested.
    assert len(g1) >= 10, f"only {len(g1)} G1 survivors"
    assert len(g2) >= 10, f"only {len(g2)} G2 survivors"
