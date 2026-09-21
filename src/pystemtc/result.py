"""Structured result object for a completed STEM run (spec 02 §B3; to_dict
schema v2 per spec 03 §1.10).

Java-shaped output tables are written by :meth:`STEMResult.write_java_tables`
(M4 writer round; round-7.3 contract).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

from . import __version__
from .javaformat import format_java_double, java_double_to_string, double_to_sz

# Writer discipline (current frozen contract):
# - rows are emitted with logical "\n"; open(..., newline=...) controls
#   platform / explicit newline translation.
# - encoding=None and newline=None use platform defaults.
# - errors="replace" is fixed internally.
# - canonical C2 comparison explicitly uses encoding="gbk",
#   newline="\r\n" against the JRE8 Windows oracle.
LINE_TERMINATOR = "\n"

# Algorithm-parameter keys of STEMConfig (config.py) — every field except the
# two I/O keys ``data_file``/``repeat_files``, which belong to the ``input``
# section of schema v2.  Enumerated explicitly (spec 03 §1.10) instead of
# filtering an ``asdict`` copy, so adding a STEMConfig field forces a
# deliberate schema decision rather than a silent payload change.
CONFIG_ALGORITHM_KEYS: tuple[str, ...] = (
    "normalize",
    "max_missing",
    "min_abs_expr",
    "maxmin",
    "repeat_min_correlation",
    "spot_included",
    "repeat_mode",
    "max_model_profiles",
    "max_unit_change",
    "max_correlation",
    "candidate_cap",
    "n_permutations",
    "permute_t0",
    "alpha",
    "correction",
    "cluster_min_correlation",
    "cluster_corr_percentile",
    "clustering_method",
)


def _encode_value(value: float, present: bool) -> tuple[str, float | None]:
    """Classify one stored double for schema v2 (spec 03 §1.10, round-7.1).

    The two information dimensions are kept together and MUST NOT replace
    one another; their priority/dependency is pinned by the table below:

    - ``present`` is the Java pma mask and answers "did Java mark this cell
      as present?".  It is the unique authority for present-ness and is
      reported unchanged in the schema (``GeneAssignment.present``).
    - ``value_states`` answers "what is the CATEGORY of the stored double?":
      ``"nan" | "positive_infinity" | "negative_infinity" | "missing"
      | "finite"``.

    Classification priority (round-7.1 expert ruling, 2026-09-20):
      non-finite classification is independent of ``present``;
      finite payload's state is then split by ``present``.

    =====  ============  ================================
    value  present       state               values
    =====  ============  ================================
    NaN    True/False    "nan"               None
    +Inf   True/False    "positive_infinity" None
    -Inf   True/False    "negative_infinity" None
    finite True          "finite"            original value
    finite False         "missing"           fill payload retained
    =====  ============  ================================

    This is the 8 distinct semantic combinations (4 value categories
    × 2 present), NOT a "10-cell orthogonal truth table" — the latter
    phrase is wrong because ``(-inf, False)`` is the same semantic case
    as the other ``-inf`` rows and the test parametrize list uses 2
    finite+True values purely as additional representative samples.  See
    :func:`tests.test_result_schema.test_encode_value_truth_table_8_semantic_combinations`
    for the 8-combination sweep plus 2 finite representative cases.

    Consequences: ``state == "finite"`` IFF ``value`` finite AND
    ``present == True``; ``state == "missing"`` IFF ``value`` finite AND
    ``present == False``.  NaN/+Inf/-Inf states DO NOT imply ``present``:
    c14 row ``present=False, value=-Inf`` reports ``"negative_infinity"``;
    a present-mask cell that happens to store ``-Inf`` would also report
    ``"negative_infinity"``.  Do not collapse ``value_states`` to a
    missness-only field — that would lose the Java-stored payload (the M4
    writer needs both axes to reproduce the genetable byte-exact).

    Lossless snapshot of the Java matrix (DataSetCore.java:707-712: the
    merged medians + primary row's fill payload in all-missing cells; the
    M4 writer reconstructs every genetable cell — ``""`` vs formatted,
    ``-0.00`` and the ∞/U+FFFD renders — from
    ``(value, value_state, present)``).
    """
    if math.isnan(value):
        return "nan", None
    if math.isinf(value):
        if value > 0:
            return "positive_infinity", None
        return "negative_infinity", None
    if not present:
        return "missing", value
    return "finite", value


@dataclass
class ProfileRecord:
    """One model profile row (a ``ProfileRec`` plus clustering output)."""

    id: int
    model: list[float]
    cluster: int  # -1 = non-significant or unclustered (ST.java:2950-2954)
    n_assigned: float  # double: fractional values from 1/k ties are expected
    n_expected: float
    p_value: float
    significant: bool


@dataclass
class GeneAssignment:
    """One surviving gene row (a genetable row without the value formatting)."""

    gene: str
    probe: str
    profile_ids: list[int]  # assigned profile ids; several when tied (ascending model-index order)
    values: list[float]  # normalized (post-merge) stored doubles; may be NaN/±Inf
    present: list[bool]  # pma != 0 per column


@dataclass
class STEMResult:
    """Structured result of :meth:`pystemtc.engine.STEM.fit`."""

    profiles: list[ProfileRecord]
    gene_assignments: list[GeneAssignment]
    filtered_genes: list[tuple[str, str, str]]  # (gene, probe, reason)
    clusters: list[list[int]]  # cluster id -> member profile ids
    config: dict
    metadata: dict
    input: dict = field(default_factory=dict)  # schema-v2 "input" section
    timing: dict = field(default_factory=dict)  # stage wall times, seconds

    def to_dict(self) -> dict:
        """Schema-v2 JSON-compatible snapshot (spec 03 §1.10).

        Top-level keys are exactly: ``schema_version``, ``reference``,
        ``generator``, ``config``, ``input``, ``metadata``, ``profiles``,
        ``gene_assignments``, ``filtered_genes``, ``clusters``, ``timing``.
        Non-finite stored doubles are encoded via :func:`_encode_value`
        (never NaN/Infinity literals), so
        ``json.dumps(result.to_dict(), allow_nan=False)`` succeeds.
        """
        gene_rows: list[dict] = []
        for g in self.gene_assignments:
            values: list[float | None] = []
            states: list[str] = []
            for value, present in zip(g.values, g.present):
                state, encoded = _encode_value(value, present)
                states.append(state)
                values.append(encoded)
            gene_rows.append(
                {
                    "gene": g.gene,
                    "probe": g.probe,
                    "profile_ids": list(g.profile_ids),
                    "values": values,
                    "value_states": states,
                    "present": list(g.present),
                }
            )

        return {
            "schema_version": 2,
            "reference": {"software": "STEM", "version": "1.3.14"},
            "generator": {"package": "pystemtc", "version": __version__},
            "config": {
                key: self.config[key]
                for key in CONFIG_ALGORITHM_KEYS
                if key in self.config
            },
            "input": dict(self.input),
            "metadata": dict(self.metadata),
            "profiles": [
                {
                    "id": p.id,
                    "model": list(p.model),
                    "cluster": p.cluster,
                    "n_assigned": p.n_assigned,
                    "n_expected": p.n_expected,
                    "p_value": p.p_value,
                    "significant": p.significant,
                }
                for p in self.profiles
            ],
            "gene_assignments": gene_rows,
            "filtered_genes": [
                {"gene": gene, "probe": probe, "reason": reason}
                for gene, probe, reason in self.filtered_genes
            ],
            "clusters": [
                {"id": i, "profile_ids": list(members)}
                for i, members in enumerate(self.clusters)
            ],
            "timing": dict(self.timing),
        }

    # ------------------------------------------------------------------
    # Java-shaped output (round-7.3 writer contract, round-8 implementation)
    # ------------------------------------------------------------------

    def _open_writer(
        self,
        path: Path,
        encoding: str | None,
        newline: str | None,
    ) -> IO[str]:
        """Open a writer for one table.

        ``encoding`` and ``newline`` flow through to :func:`open`; pass
        ``None`` to use the platform default (Java's behavior on this
        host).  ``errors="replace"`` is pinned internally -- the writer
        API does not expose this parameter.

        Line discipline: this method writes :data:`LINE_TERMINATOR`
        (``"\\n"``) at the end of every row; the ``newline`` parameter
        passed to :func:`open` is what performs any LF-to-CRLF
        translation.  We deliberately NEVER concatenate
        ``line + newline`` in user code: doing both would produce
        ``\\r\\r\\n`` (round-7.7 P1-3 fix).
        """
        return path.open("w", encoding=encoding, errors="replace", newline=newline)

    def _write_genetable(
        self, path: Path, encoding: str | None, newline: str | None,
    ) -> None:
        """Write the Java-shaped genetable (ST.java:2985-3036).

        Header columns: ``<gene_header>\\t<probe_header>\\tProfile`` then the
        time-point labels from ``result.input['time_points']`` verbatim --
        NO self-injected ``"0"`` column (the user's t0 reference value is
        already in the matrix at index 0; the gene-header+profile+time
        columns are exactly ``numcols + 3`` total fields).

        Per-cell rule (Java loop):
          - ``j < T-1`` AND ``not present[j]`` -> emit the empty string
            between tabs (cell rendered blank)
          - otherwise emit ``format_java_double(value[j])``

        The LAST column (``j == T-1``) is always rendered (Java's
        ``pw.println(... +nf2.format(...))`` after the conditional loop),
        even when ``present[T-1] == False``.
        """
        gene_header: str = self.input.get("gene_header", "Gene Symbol")
        probe_header: str = self.input.get("probe_header", "SPOT")
        time_points: list[str] = list(self.input.get("time_points", []))
        T: int = len(time_points)

        with self._open_writer(path, encoding, newline) as fh:
            # Header line
            fh.write(gene_header)
            fh.write("\t")
            fh.write(probe_header)
            fh.write("\tProfile")
            for label in time_points:
                fh.write("\t")
                fh.write(label)
            fh.write(LINE_TERMINATOR)
            # Data rows
            for g in self.gene_assignments:
                fh.write(g.gene)
                fh.write("\t")
                fh.write(g.probe)
                fh.write("\t")
                profile_ids = g.profile_ids
                if profile_ids:
                    fh.write(str(profile_ids[0]))
                    for pid in profile_ids[1:]:
                        fh.write(";")
                        fh.write(str(pid))
                for j in range(T):
                    fh.write("\t")
                    if j < T - 1 and not g.present[j]:
                        # missing cell -- Java prints empty between tabs
                        continue
                    fh.write(format_java_double(g.values[j]))
                fh.write(LINE_TERMINATOR)

    def _write_profiletable(
        self, path: Path, encoding: str | None, newline: str | None,
    ) -> None:
        """Write the Java-shaped profile table (ST.java:2944-2977, non-kmeans).

        Hardcoded 6-column header (the writer does not auto-detect k-means
        mode -- Java's kmeans branch writes a different file with the
        ``_kmeansclustertable.txt`` suffix; pystemtc does not currently
        expose a kmeans pathway through the public API):

          ``Profile ID\\tProfile Model\\tCluster (-1 non-significant)\\t
          # Genes Assigned\\t# Gene Expected\\tp-value``

        Per-row:
          - Profile ID: integer ``p.id``
          - Profile Model: ``java_double_to_string(model[0]),`` plus
            ``,java_double_to_string(model[j])`` for j in 1..len-1 (the
            Java default ``double -> String`` is used for model coords;
            the genetable's NumberFormat-2 path is NOT used here).
          - Cluster: ``p.cluster`` as int (Java prints ``-1`` for
            non-significant).
          - # Genes Assigned, # Gene Expected: ``java_double_to_string``
            (raw Double.toString, not NumberFormat).
          - p-value: ``double_to_sz`` (Util.doubleToSz path; see
            :func:`pystemtc.javaformat.double_to_sz`).
        """
        with self._open_writer(path, encoding, newline) as fh:
            fh.write("Profile ID\tProfile Model"
                     "\tCluster (-1 non-significant)"
                     "\t# Genes Assigned\t# Gene Expected\tp-value")
            fh.write(LINE_TERMINATOR)
            for p in self.profiles:
                fh.write(str(p.id))
                fh.write("\t")
                model = p.model
                if model:
                    fh.write(java_double_to_string(model[0]))
                    for m in model[1:]:
                        fh.write(",")
                        fh.write(java_double_to_string(m))
                fh.write("\t")
                fh.write(str(p.cluster))
                fh.write("\t")
                fh.write(java_double_to_string(p.n_assigned))
                fh.write("\t")
                fh.write(java_double_to_string(p.n_expected))
                fh.write("\t")
                fh.write(double_to_sz(p.p_value))
                fh.write(LINE_TERMINATOR)

    def write_java_tables(
        self,
        out_dir: str | Path,
        prefix: str | None = None,
        *,
        encoding: str | None = None,
        newline: str | None = None,
    ) -> list[str]:
        """Write the Java-shaped genetable and profiletable to ``out_dir``.

        File-naming convention (round-7.3 frozen, restored in round-8
        final patch):

          - ``prefix="abc"`` -> ``abc_genetable.txt``, ``abc_profiletable.txt``
          - ``prefix=None`` + path-derived input -> the stem of
            ``result.input['data_file']`` (e.g. ``g27_1``)
          - ``prefix=None`` + dataframe input (``data_file`` is
            ``None``) -> ``ValueError``; the caller MUST supply an
            explicit ``prefix`` because there is no stem to derive.

        ``encoding`` and ``newline`` are forwarded to :func:`open`
        with ``None`` meaning "platform default" (Java's behavior on
        the user's host).  For C2 byte-exact comparison against the
        Java golden oracles (which were produced by JRE 1.8.0_451 on
        Windows), pass ``encoding="gbk", newline="\\r\\n"`` explicitly.

        ``errors="replace"`` is pinned internally -- the API does not
        expose this parameter (round-7.7 P2-3 ruling).

        Returns the absolute string paths of the two written tables in
        the order ``[genetable, profiletable]``.
        """
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # Prefix resolution: explicit > path-stem > error.
        if prefix is None:
            data_file = self.input.get("data_file")
            if data_file is None:
                raise ValueError(
                    "write_java_tables: prefix is required when the "
                    "input was a DataFrame (no data_file path to "
                    "derive a stem from). Pass prefix= explicitly."
                )
            prefix = Path(str(data_file)).stem

        genetable_path = out_path / f"{prefix}_genetable.txt"
        profiletable_path = out_path / f"{prefix}_profiletable.txt"
        self._write_genetable(genetable_path, encoding, newline)
        self._write_profiletable(profiletable_path, encoding, newline)
        return [str(genetable_path), str(profiletable_path)]
