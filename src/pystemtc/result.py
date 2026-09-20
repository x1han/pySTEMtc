"""Structured result object for a completed STEM run (spec 02 §B3; to_dict
schema v2 per spec 03 §1.10).

Java-shaped output tables (``write_java_tables``) are deferred to the M4
writer round; :meth:`STEMResult.to_dict` provides the schema-v2
JSON-compatible snapshot.  ``gene_assignments`` ``values`` there is a
lossless snapshot of the Java gene-matrix content (merged medians + the
all-missing cells' fill payloads); the future writer consumes the internal
floats of :class:`STEMResult` directly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import __version__

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
