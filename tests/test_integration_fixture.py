"""M1 DoD end-to-end check against the golden genetable fixtures.

Compares the surviving gene rows (gene symbol + SPOT/probe string, same
order) and every value column at STRING level against the Java batch output.
Values are formatted like Java's ``NumberFormat.getInstance(Locale.ENGLISH)``
with min = max fraction digits 2 (HALF_EVEN rounding on the exact binary
value, thousands grouping, "-0.00" for tiny negatives).  The Profile column
is validated in M2.
"""

from pathlib import Path

import pytest

from pystemtc.config import STEMConfig
from pystemtc.dataio import read_stem_file
from pystemtc.dataset import build_stem_dataset, gene_names
# Round-8 final patch: this module previously kept a local copy of
# ``format_java_double`` (the round-7.1 simpler version with
# ``Decimal(float(value))``).  The canonical two-path-dispatch
# implementation now lives in :mod:`pystemtc.javaformat`.  Single
# source of truth -- never keep two Java formatters in the repo.
from pystemtc.javaformat import format_java_double

GOLDEN = Path(__file__).parent / "golden"


def _find_input(name: str) -> Path:
    """Locate raw sample data; bundled copies under tests/golden/data win."""
    bundled = GOLDEN / "data" / name
    if bundled.exists():
        return bundled
    here = Path(__file__).resolve()
    for base in (here.parents[2], here.parents[1], Path.cwd()):
        candidate = base / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"could not locate input file {name!r}")


def _repeat_spotsets(cfg_path: Path, config):
    """Load the repeat files listed in the config's Repeat_Data_Files line."""
    for line in cfg_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Repeat_Data_Files"):
            value = line.split("\t", 1)[1].strip() if "\t" in line else ""
            return [
                read_stem_file(
                    _find_input(name.strip()),
                    takelog=config.takelog,
                    add0=config.add0,
                    spot_included=config.spot_included,
                    repeat_set=True,
                )
                for name in value.split(",")
                if name.strip()
            ]
    return []


CASES = [
    "c01_guillemin_core",
    "c03_lognorm",
    "c04_add0",
    "c07_sameperiod",
    "c08_norepeat",
]


@pytest.mark.parametrize("case", CASES)
def test_genetable_matches_java(case):
    cfg_path = GOLDEN / "java_configs" / f"{case}.txt"
    config = STEMConfig.from_defaults_file(cfg_path)

    main = read_stem_file(
        _find_input("g27_1.txt"),
        takelog=config.takelog,
        add0=config.add0,
        spot_included=config.spot_included,
    )
    repeats = _repeat_spotsets(cfg_path, config)
    ds = build_stem_dataset(main, repeats, mode=config.repeat_mode, config=config)

    # repeat correlation values cover ALL dup-merged genes and are ascending;
    # Java computes them only for different_periods repeats (sortedcorrvals is
    # null in same-period mode, DataSetCore.java:787-792)
    if repeats and config.repeat_mode == "different_periods":
        assert ds.repeat_corr_sorted is not None
        assert ds.repeat_corr_sorted == sorted(ds.repeat_corr_sorted)
    else:
        assert ds.repeat_corr_sorted is None

    lines = (GOLDEN / "java_reference" / f"{case}_genetable.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    header = lines[0].split("\t")
    assert header[:2] == ["Gene Symbol", "SPOT"]
    assert header[2] == "Profile"  # skipped here, validated in M2
    assert header[3:] == ds.sample_labels

    rows = lines[1:]
    names = gene_names(ds)
    ncols = ds.gene_data.shape[1]
    assert len(rows) == ds.gene_data.shape[0] == len(names)

    for i, line in enumerate(rows):
        cols = line.split("\t")
        assert cols[0] == names[i], f"row {i}: gene symbol {cols[0]!r} != {names[i]!r}"
        assert cols[1] == ds.gene_probes[i], (
            f"row {i} ({names[i]}): probe {cols[1]!r} != {ds.gene_probes[i]!r}"
        )
        for j in range(ncols):
            # Java prints the last column unconditionally (ST.java:3033);
            # other columns print an empty string for missing cells
            if j < ncols - 1 and ds.gene_pma[i, j] == 0:
                expected = ""
            else:
                expected = format_java_double(ds.gene_data[i, j])
            assert cols[3 + j] == expected, (
                f"row {i} ({names[i]}) column {ds.sample_labels[j]}: "
                f"{cols[3 + j]!r} != {expected!r}"
            )


@pytest.mark.parametrize(
    "value,expected",
    [
        (2.675, "2.67"),  # exact expansion 2.67499... (HALF_EVEN, not repr-based)
        (0.125, "0.12"),  # exact tie -> HALF_EVEN down
        (0.135, "0.14"),
        (0.015, "0.01"),
        (999.995, "1,000.00"),  # rounding crosses the grouping boundary
        (1234.567, "1,234.57"),
        (-0.001, "-0.00"),
        (-0.0004, "-0.00"),
        (-0.0, "-0.00"),
        (0.0, "0.00"),
        (-2.675, "-2.67"),
        (float("nan"), "\ufffd"),
    ],
)
def test_java_double_formatter_semantics(value, expected):
    assert format_java_double(value) == expected
