"""Structured result object for a completed STEM run (spec 02 §B3).

``to_csv`` (Java-shaped output tables) is deferred to M4; :meth:`to_dict`
provides the minimal JSON-compatible snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass


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
    profile: str  # assigned profile ids, ";"-joined when tied
    values: list[float]  # normalized (post-merge) values, NaN = missing
    present: list[bool]  # pma != 0 per column


@dataclass
class STEMResult:
    """Minimal structured result of :meth:`pystemtc.engine.STEM.fit`."""

    profiles: list[ProfileRecord]
    gene_assignments: list[GeneAssignment]
    filtered_genes: list[tuple[str, str, str]]  # (gene, probe, reason)
    clusters: list[list[int]]  # cluster id -> member profile ids
    config: dict
    metadata: dict

    def to_dict(self) -> dict:
        """JSON-compatible snapshot (M4 will add ``to_csv``)."""
        return {
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
            "gene_assignments": [
                {
                    "gene": g.gene,
                    "probe": g.probe,
                    "profile": g.profile,
                    "values": list(g.values),
                    "present": list(g.present),
                }
                for g in self.gene_assignments
            ],
            "filtered_genes": [list(t) for t in self.filtered_genes],
            "clusters": [list(c) for c in self.clusters],
            "config": dict(self.config),
            "metadata": dict(self.metadata),
        }
