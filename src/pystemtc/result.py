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
    """Classify one stored double for schema v2 (spec 03 §1.10 truth table).

    Priority is pinned: the stored double is classified FIRST, ``present``
    (the pma mask) only splits the finite branch.

    ==========  ===================  ================================
    stored      state                values entry
    ==========  ===================  ================================
    NaN         "nan"                None
    +Inf        "positive_infinity"  None
    -Inf        "negative_infinity"  None
    finite      present == False     "missing" — fill payload retained
    finite      present == True      "finite" — original value
    ==========  ===================  ================================

    Invariants: ``values[i] is None`` iff ``value_states[i]`` is one of
    nan/positive_infinity/negative_infinity; ``state == "missing"`` implies
    ``present is False``; ``present is True`` implies ``state == "finite"``.
    Note the asymmetry: a non-finite payload stored in an all-missing cell
    (present=False — e.g. the log-mode ``log(0) = -Inf`` route, c14) reports
    the non-finite state, not "missing", because the state classifies the
    stored double while ``present`` mirrors the pma mask.

    This is the writer-lossless snapshot semantics of the Java matrix (the
    Java gene-matrix content = merged medians + the primary row's fill
    payload in all-missing cells, DataSetCore.java:707-712): from
    (value, state, present) every Java genetable cell — including the
    ``""``-vs-formatted distinction, ``-0.00`` and the ∞/U+FFFD renders — can
    be reconstructed exactly by the M4 writer.
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
