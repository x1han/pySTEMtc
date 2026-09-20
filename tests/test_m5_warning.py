"""M5 warning (FINAL-A A5): once-per-analysis warning when
``normalize='none_add0'`` and ``permute_t0=True`` are both set.

The warning text is FROZEN -- changing it is a contract break for
downstream tooling that may grep on it.  See round-7.7 / FINAL-A A5.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from pystemtc import STEM


_FROZEN_TEXT_FRAGMENT = "normalize='none_add0'"
_FROZEN_TEXT_FRAGMENT_2 = "Interpret permutation-based significance with caution"


# Reuse a 30-row slice of the bundled g27_1.txt data: known to survive
# M1 under all three normalize modes with default filters, T=5 (T=4 +
# t0 reference column present in the file).
_G27_SRC = Path(__file__).resolve().parent / "golden" / "data" / "g27_1.txt"


@pytest.fixture()
def tiny_data_file(tmp_path: Path) -> Path:
    """Copy a 30-row T=5 slice of g27_1.txt into tmp_path.

    The slice covers columns ``SPOT, Gene Symbol, 0h, 0.5h, 3h, 6h``
    (T=4 observed time points; the column 0h is t0).  The synthetic
    zero baseline that ``none_add0`` appends brings T to 5 in that
    branch.
    """
    src_lines = _G27_SRC.read_text(encoding="utf-8").splitlines()
    header = src_lines[0].split("\t")
    keep_cols = header[:6]
    out_lines = ["\t".join(keep_cols)]
    for line in src_lines[1:31]:
        out_lines.append("\t".join(line.split("\t")[:6]))
    dst = tmp_path / "tiny.tsv"
    dst.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return dst


def test_m5_warning_fires_when_add0_and_permute_t0(tiny_data_file: Path) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        STEM(
            normalize="none_add0",
            permute_t0=True,
            n_permutations=4,
        ).fit(str(tiny_data_file))

    msgs = [str(w.message) for w in caught]
    assert any(_FROZEN_TEXT_FRAGMENT in m for m in msgs)
    assert any(_FROZEN_TEXT_FRAGMENT_2 in m for m in msgs)


def test_m5_warning_silent_when_permute_t0_false(tiny_data_file: Path) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        STEM(
            normalize="none_add0",
            permute_t0=False,
            n_permutations=4,
        ).fit(str(tiny_data_file))

    msgs = [str(w.message) for w in caught]
    assert not any(_FROZEN_TEXT_FRAGMENT in m for m in msgs)


def test_m5_warning_silent_when_normalize_log(tiny_data_file: Path) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        STEM(
            normalize="log",
            permute_t0=True,
            n_permutations=4,
        ).fit(str(tiny_data_file))

    msgs = [str(w.message) for w in caught]
    assert not any(_FROZEN_TEXT_FRAGMENT in m for m in msgs)


def test_m5_warning_silent_when_normalize_normalize(tiny_data_file: Path) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        STEM(
            normalize="normalize",
            permute_t0=True,
            n_permutations=4,
        ).fit(str(tiny_data_file))

    msgs = [str(w.message) for w in caught]
    assert not any(_FROZEN_TEXT_FRAGMENT in m for m in msgs)


def test_m5_warning_fires_exactly_once_per_analysis(tiny_data_file: Path) -> None:
    """One fit() call with the trigger combo -> exactly one warning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        STEM(
            normalize="none_add0",
            permute_t0=True,
            n_permutations=4,
        ).fit(str(tiny_data_file))

    matching = [
        w for w in caught
        if _FROZEN_TEXT_FRAGMENT in str(w.message)
    ]
    assert len(matching) == 1


def test_m5_warning_is_user_warning_category(tiny_data_file: Path) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        STEM(
            normalize="none_add0",
            permute_t0=True,
            n_permutations=4,
        ).fit(str(tiny_data_file))

    matching = [
        w for w in caught
        if _FROZEN_TEXT_FRAGMENT in str(w.message)
    ]
    assert len(matching) == 1
    assert issubclass(matching[0].category, UserWarning)
