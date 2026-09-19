"""Readers producing :class:`pystemtc.dataset.SpotSet` (spec §1.1).

File semantics replicate ``DataSetCore.dataSetReader`` (DataSetCore.java:285-548):
tab-delimited, gzip tried first, header row, ``[SPOT] GENE t1..tT`` columns,
empty cell = missing (data 0.0, pma 0), present cells pma 2, gene/spot names
trimmed and uppercased, a missing or literally-"0" gene name is synthesized as
``0 (SPOT_<spotname>)``, blank lines are skipped (spot-column mode only), and
raw values are kept as parsed.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd

from .dataset import SpotSet
from .errors import STEMTCValueError


def _tokenize(line: str, delim: str = "\t") -> list[str]:
    """``StringTokenizer(line, delim, true)``: each delimiter is its own token."""
    tokens: list[str] = []
    start = 0
    for i, ch in enumerate(line):
        if ch == delim:
            if i > start:
                tokens.append(line[start:i])
            tokens.append(delim)
            start = i + 1
    if start < len(line):
        tokens.append(line[start:])
    return tokens


def _open_text(path: str | Path):
    # Java tries GZIPInputStream first and falls back on IOException
    # (DataSetCore.java:297-302); the gzip magic check is equivalent.
    with open(path, "rb") as raw:
        magic = raw.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rt", encoding="utf-8", newline=None)
    return open(path, "rt", encoding="utf-8", newline=None)


def _parse_double(sztoken: str, message: str) -> float:
    # Java Double.parseDouble ignores surrounding whitespace and accepts a
    # trailing d/d/D/f/F suffix (Javadoc; verified via jjs); "_" is rejected.
    sztoken = sztoken.strip()
    if sztoken and sztoken[-1] in "dDfF":
        sztoken = sztoken[:-1]
    if "_" in sztoken:
        raise STEMTCValueError(message)
    try:
        return float(sztoken)
    except ValueError:
        raise STEMTCValueError(message) from None


def _upper_trim(name: str) -> str:
    # Java: sztoken.trim().toUpperCase(Locale.ENGLISH)
    return name.strip().upper()


def read_stem_file(
    path: str | Path,
    takelog: bool = False,
    add0: bool = False,
    spot_included: bool = True,
    repeat_set: bool = False,
):
    """Read a native STEM tsv/tsv.gz file into a SpotSet.

    ``takelog`` marks raw values <= 0 as missing at read time
    (DataSetCore.java:530-534); ``add0`` prepends the synthetic zero column
    (DataSetCore.java:495-497); ``repeat_set`` only selects the repeat-variant
    error messages.
    """
    path = Path(path)
    with _open_text(path) as handle:
        lines = handle.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    if not lines:
        raise STEMTCValueError(f"Input File {path} is empty!")

    szheader = lines[0]
    if szheader == "":
        idx = 1
        while szheader == "":
            if idx >= len(lines):
                raise STEMTCValueError(f"Input File {path} is empty!")
            szheader = lines[idx]
            idx += 1
        lines = lines[idx - 1 :]

    numcols = szheader.count("\t")
    if szheader.endswith("\t"):
        numcols -= 1
    if spot_included:
        numcols -= 1
    if add0:
        numcols += 1

    tokens = _tokenize(szheader)
    pos = 0

    def _next_header_token(err: str) -> str:
        nonlocal pos
        if pos >= len(tokens):
            raise STEMTCValueError(err)
        tok = tokens[pos]
        pos += 1
        return tok

    if spot_included:
        tok = _next_header_token("Missing gene header.")
        if tok != "\t":
            if pos >= len(tokens):
                msg = "Missing gene header."
                if numcols == -1:
                    msg += "\nConsider unchecking 'Spot IDs included in the data file'"
                raise STEMTCValueError(msg)
            _next_header_token("Missing gene header.")  # flush tab
            probe_header = tok
        else:
            probe_header = ""
    else:
        probe_header = "SPOT"

    tok = _next_header_token("Missing gene header.")
    if tok != "\t":
        if pos < len(tokens):
            pos += 1  # flush tab
        gene_header = tok
    else:
        gene_header = ""

    dsamplemins: list[str] = []
    if add0:
        dsamplemins.append("0")
    for _ in range(max(numcols - (1 if add0 else 0), 0)):
        tok = _next_header_token("Missing a column header")
        if tok != "\t":
            if pos < len(tokens):
                pos += 1  # flush tab
        else:
            tok = ""
        dsamplemins.append(tok)

    if spot_included:
        kept = [ln for ln in lines[1:] if ln.strip(" \t") != ""]
    else:
        kept = lines[1:]
    numrows = len(kept)
    if numrows == 0:
        raise STEMTCValueError(f"{path} is empty!")

    data = np.zeros((numrows, numcols), dtype=np.float64)
    pma = np.zeros((numrows, numcols), dtype=np.int8)
    probenames: list[str] = []
    genenames: list[str] = []
    seen_spots: set[str] = set()

    for nrow, szline in enumerate(kept):
        toks = _tokenize(szline)
        pos = 0

        if spot_included:
            if pos >= len(toks):
                raise STEMTCValueError(
                    "Missing a Spot Name in the repeat/comparison set"
                    if repeat_set
                    else "Missing a Spot Name"
                )
            sztoken = toks[pos]
            pos += 1
            if sztoken == "\t":
                if repeat_set:
                    msg = "Missing a Spot Name in the repeat/comparison set"
                else:
                    msg = "Missing a Spot Name"
                    msg += "\nConsider unchecking 'Spot IDs included in the data file'"
                raise STEMTCValueError(msg)
            if sztoken in seen_spots:
                if repeat_set:
                    msg = f"Spot name {sztoken} in repeat/comparison is not unique"
                else:
                    msg = (
                        f"Spot name {sztoken} is not unique"
                        "\nConsider unchecking 'Spot IDs included in the data file'"
                    )
                raise STEMTCValueError(msg)
            seen_spots.add(sztoken)
            probename = _upper_trim(sztoken)
            if pos < len(toks):
                pos += 1  # flush tab
        else:
            probename = "ID_" + str(nrow)
        probenames.append(probename)

        if pos >= len(toks):
            genename = "0 (SPOT_" + probename + ")"
            # data/pma columns already initialized to missing
        else:
            sztoken = toks[pos]
            pos += 1
            if sztoken == "\t" or sztoken == "0":
                # gene name missing; "0" counts as a missing name field
                if sztoken == "0" and pos < len(toks):
                    pos += 1  # flush tab
                genename = "0 (SPOT_" + probename + ")"
            else:
                if len(sztoken) >= 2 and sztoken[0] == '"' and sztoken[-1] == '"':
                    sztoken = sztoken[1:-1]
                if pos < len(toks):
                    pos += 1  # flush tab
                genename = _upper_trim(sztoken)
        genenames.append(genename)

        ncol = 1 if add0 else 0
        if add0:
            data[nrow, 0] = 0.0
            pma[nrow, 0] = 2

        beol = False
        sztoken = ""
        while ncol < numcols:
            if pos >= len(toks):
                beol = True
            else:
                sztoken = toks[pos]
                pos += 1

            if beol or sztoken == "\t":
                data[nrow, ncol] = 0.0
                pma[nrow, ncol] = 0
            else:
                msg = f"{sztoken} is not a valid real number"
                if repeat_set:
                    msg = f"In the repeat/comparison set {msg}"
                elif (ncol == 0 or (ncol == 1 and add0)) and not spot_included:
                    msg += "\nConsider checking 'Spot IDs included in the data file'"
                value = _parse_double(sztoken, msg)
                data[nrow, ncol] = value
                if takelog and value <= 0:
                    # values <= 0 count as missing when not already in log space
                    pma[nrow, ncol] = 0
                else:
                    pma[nrow, ncol] = 2
                if pos < len(toks):
                    sztoken = toks[pos]
                    pos += 1
                    if sztoken == "\n":
                        beol = True
            ncol += 1

    return SpotSet(
        raw_data=data,
        raw_pma=pma,
        spot_ids=probenames,
        gene_ids=genenames,
        probe_ids=list(probenames),
        sample_labels=dsamplemins,
    )


def _cell_str(value) -> str:
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        return str(int(value))
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return str(value)


def _is_missing_scalar(value) -> bool:
    if value is None:
        return True
    return bool(pd.isna(value))


def dataframe_to_spotset(df, takelog: bool = False, add0: bool = False):
    """Build a SpotSet from a wide DataFrame (spec §1.1 contract).

    Requires a ``gene`` column; optional ``spot`` column (synthesized as
    ``SPOT_<row>`` in row order when absent); the remaining columns, in
    column order, are the time points (column names become the time labels).
    NaN cells are missing; rows are neither reordered nor deduplicated and
    duplicate gene rows are kept (the median merge happens downstream).
    """
    columns = [str(c) for c in df.columns]
    if "gene" not in columns:
        raise STEMTCValueError("DataFrame must have a 'gene' column")
    has_spot = "spot" in columns
    time_cols = [c for c in df.columns if str(c) not in ("gene", "spot")]
    numcols = len(time_cols) + (1 if add0 else 0)

    nrows = len(df)
    data = np.zeros((nrows, numcols), dtype=np.float64)
    pma = np.zeros((nrows, numcols), dtype=np.int8)
    probenames: list[str] = []
    genenames: list[str] = []
    seen_spots: set[str] = set()

    for nrow in range(nrows):
        if has_spot:
            # NaN/blank/duplicate spot names all raise, mirroring the file
            # rules (DataSetCore.java:429-452)
            raw = df["spot"].iloc[nrow]
            sztoken = None if _is_missing_scalar(raw) else _cell_str(raw)
            if sztoken is None or sztoken.strip() == "":
                raise STEMTCValueError("Missing a Spot Name")
            if sztoken in seen_spots:
                raise STEMTCValueError(f"Spot name {sztoken} is not unique")
            seen_spots.add(sztoken)
            probename = _upper_trim(sztoken)
        else:
            probename = f"SPOT_{nrow}"
        probenames.append(probename)

        raw = df["gene"].iloc[nrow]
        if _is_missing_scalar(raw):
            sztoken = None
        else:
            sztoken = _cell_str(raw)
            if sztoken.strip() == "0" or sztoken == "":
                sztoken = None
        if sztoken is None:
            genename = "0 (SPOT_" + probename + ")"
        else:
            if sztoken.strip() in ("", "0"):
                genename = "0 (SPOT_" + probename + ")"
            else:
                if len(sztoken) >= 2 and sztoken[0] == '"' and sztoken[-1] == '"':
                    sztoken = sztoken[1:-1]
                genename = _upper_trim(sztoken)
        genenames.append(genename)

        ncol = 1 if add0 else 0
        if add0:
            pma[nrow, 0] = 2
        for col in time_cols:
            raw = df[col].iloc[nrow]
            if not _is_missing_scalar(raw):
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    raise STEMTCValueError(f"{raw} is not a valid real number") from None
                data[nrow, ncol] = value
                if takelog and value <= 0:
                    pma[nrow, ncol] = 0
                else:
                    pma[nrow, ncol] = 2
            ncol += 1

    labels = ["0"] + [str(c) for c in time_cols] if add0 else [str(c) for c in time_cols]

    return SpotSet(
        raw_data=data,
        raw_pma=pma,
        spot_ids=probenames,
        gene_ids=genenames,
        probe_ids=list(probenames),
        sample_labels=labels,
    )
