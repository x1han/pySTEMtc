"""The STEM engine: orchestrates the M1 chain and the M2 core algorithm in
the exact ``buildsetwithOrig`` STEM-branch order (ST.java:2695-2810):

    read -> logratio2 -> averageAndFilterDuplicates -> repeat merge ->
    errorcheck -> filterdistprofiles -> filterMissing -> filtergenesthreshold2
    (all inside :func:`pystemtc.dataset.build_stem_dataset`)
    -> model profiles (enumerate/sample + compactprofiles2)
    -> findbestgroupassignments -> tallyassignments -> computeaveragetally
    -> computePvaluesAssignments -> clusterprofiles

GO / two-condition comparison steps are intentionally not implemented (V1
frozen scope); ``Clustering_Method = K-means`` raises
:class:`NotImplementedError`.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from . import __version__
from .assign import best_assignments
from .clustering import cluster_profiles
from .config import STEMConfig
from .dataio import dataframe_to_spotset, read_stem_file
from .dataset import STEMDataset, SpotSet, build_stem_dataset, gene_names
from .errors import STEMTCValueError
from .permutation import expected_counts
from .profiles import compact_profiles2, enumerate_candidates, sample_candidates
from .result import GeneAssignment, ProfileRecord, STEMResult
from .significance import correct, count_pvalue


class STEM:
    """Headless port of the STEM clustering method (defaults mirror
    ``defaults.txt``, ST.java:61-115)."""

    def __init__(
        self,
        normalize: str = "normalize",
        max_unit_change: int = 2,
        max_model_profiles: int = 50,
        max_correlation: float = 1.0,
        candidate_cap: int = 1_000_000,
        n_permutations: int = 50,
        permute_t0: bool = True,
        alpha: float = 0.05,
        correction: str = "bonferroni",
        cluster_min_correlation: float = 0.7,
        cluster_corr_percentile: float = 0.0,
        max_missing: int = 0,
        min_abs_expr: float = 1.0,
        change_rule: str = "max_minus_min",
        repeat_min_correlation: float = 0.0,
        repeat_mode: str = "different_periods",
        spot_included: bool = True,
        clustering_method: str = "stem",
    ):
        if change_rule not in ("max_minus_min", "diff_from_zero"):
            raise STEMTCValueError(f"unknown change_rule: {change_rule!r}")
        if correction not in ("bonferroni", "fdr", "none"):
            raise STEMTCValueError(f"unknown correction: {correction!r}")
        if normalize not in ("log", "normalize", "none_add0"):
            raise STEMTCValueError(f"unknown normalize mode: {normalize!r}")

        self.config = STEMConfig(
            normalize=normalize,
            max_missing=max_missing,
            min_abs_expr=min_abs_expr,
            maxmin=change_rule == "max_minus_min",
            repeat_min_correlation=repeat_min_correlation,
            spot_included=spot_included,
            repeat_mode=repeat_mode,
            max_model_profiles=max_model_profiles,
            max_unit_change=max_unit_change,
            max_correlation=max_correlation,
            candidate_cap=candidate_cap,
            n_permutations=n_permutations,
            permute_t0=permute_t0,
            alpha=alpha,
            correction=correction,
            cluster_min_correlation=cluster_min_correlation,
            cluster_corr_percentile=cluster_corr_percentile,
            clustering_method=clustering_method,
        )

    # ------------------------------------------------------------------
    def fit(
        self,
        data,
        replicates: list | None = None,
        repeat_mode: str | None = None,
    ) -> STEMResult:
        """Run the full analysis.  ``data`` may be a native STEM tsv/tsv.gz
        path, a wide DataFrame (required column ``gene``, optional ``spot``,
        remaining columns = time points), or a ready :class:`STEMDataset`."""
        config = self.config
        if repeat_mode is not None:
            config = replace(config, repeat_mode=repeat_mode)

        if isinstance(data, STEMDataset):
            ds = data
            input_form = "stem_dataset"
            return self._analyze(ds, config, input_form)

        if isinstance(data, pd.DataFrame):
            main = dataframe_to_spotset(
                data,
                takelog=config.normalize == "log",
                add0=config.normalize == "none_add0",
            )
            input_form = "dataframe"
        elif isinstance(data, (str, Path)):
            main = read_stem_file(
                data,
                takelog=config.normalize == "log",
                add0=config.normalize == "none_add0",
                spot_included=config.spot_included,
            )
            input_form = "path"
        else:
            raise STEMTCValueError(
                "fit() accepts a file path, a DataFrame or a STEMDataset"
            )

        repeats: list[SpotSet] = []
        if replicates is None:
            rep_sources = list(config.repeat_files or [])
        else:
            rep_sources = list(replicates)
        for rep_source in rep_sources:
            if isinstance(data, pd.DataFrame):
                if not isinstance(rep_source, pd.DataFrame):
                    raise STEMTCValueError(
                        "replicates must be DataFrames when the main input is a DataFrame"
                    )
                repeats.append(
                    dataframe_to_spotset(
                        rep_source,
                        takelog=config.normalize == "log",
                        add0=config.normalize == "none_add0",
                    )
                )
            else:
                repeats.append(
                    read_stem_file(
                        rep_source,
                        takelog=config.normalize == "log",
                        add0=config.normalize == "none_add0",
                        spot_included=config.spot_included,
                        repeat_set=True,
                    )
                )
        ds = build_stem_dataset(main, repeats, config.repeat_mode, config)

        return self._analyze(ds, config, input_form)

    # ------------------------------------------------------------------
    def _analyze(self, ds: STEMDataset, config: STEMConfig, input_form: str) -> STEMResult:
        if config.clustering_method != "stem":
            raise NotImplementedError(
                "K-means clustering is not implemented in PySTEMTC V1 "
                "(frozen scope; planned for V1.1 with the Random(2211) + "
                "reservoir-sampling restart replica)"
            )

        numcols = int(ds.gene_data.shape[1])
        numrows = int(ds.gene_data.shape[0])

        self._validate_profile_params(config)

        # generatemodelprofiles (STEM_DataSet.java:766-806)
        nchoices = 2 * config.max_unit_change + 1
        if float(nchoices) ** (numcols - 1) < config.candidate_cap:  # :776
            candidates = enumerate_candidates(config.max_unit_change, numcols)
        else:
            candidates = sample_candidates(
                config.max_unit_change, numcols, config.candidate_cap
            )
        models, _candidate_ids = compact_profiles2(
            candidates,
            config.max_model_profiles,
            config.max_correlation,
            config.max_unit_change,
        )

        # findbestgroupassignments (STEM_DataSet.java:1718-1758)
        assignments = best_assignments(ds.gene_data, ds.gene_pma, models)

        # tallyassignments (STEM_DataSet.java:191-209)
        counts = [0.0] * len(models)
        for row_assignments in assignments:
            numassigned = len(row_assignments)
            dweight = 1.0 / numassigned
            for pid in row_assignments:
                counts[pid] += dweight

        # computeaveragetally (STEM_DataSet.java:1038-1375)
        expected, perm_meta = expected_counts(
            ds, models, config.n_permutations, config.permute_t0
        )
        expected_list = [float(v) for v in expected]

        # computePvaluesAssignments (STEM_DataSet.java:287-335)
        pvalues = [
            count_pvalue(counts[i], numrows, expected_list[i] / numrows)
            for i in range(len(models))
        ]
        significant, _ = correct(
            pvalues,
            config.alpha,
            config.correction,
            counts=counts,
        )

        # clusterprofiles (STEM_DataSet.java:870-997)
        sig_ids = [i for i, sig in enumerate(significant) if sig]
        clusters = cluster_profiles(
            sig_ids,
            counts,
            models,
            config.cluster_min_correlation,
            config.cluster_corr_percentile,
            repeat_corr_sorted=ds.repeat_corr_sorted,
        )
        cluster_of: dict[int, int] = {}
        for cid, members in enumerate(clusters):
            for pid in members:
                cluster_of[pid] = cid

        profiles = [
            ProfileRecord(
                id=i,  # Profile ID = position after candidate-index sorting
                model=list(models[i]),
                cluster=cluster_of.get(i, -1),
                n_assigned=counts[i],
                n_expected=expected_list[i],
                p_value=pvalues[i],
                significant=significant[i],
            )
            for i in range(len(models))
        ]

        genes = gene_names(ds)
        gene_assignments = [
            GeneAssignment(
                gene=genes[nrow],
                probe=ds.gene_probes[nrow],
                profile=";".join(str(pid) for pid in assignments[nrow]),
                values=[float(v) for v in ds.gene_data[nrow]],
                present=[bool(p != 0) for p in ds.gene_pma[nrow]],
            )
            for nrow in range(numrows)
        ]

        metadata = {
            "software": f"PySTEMTC {__version__}",
            "reference": "STEM v1.3.14 (Ernst, Patek, Bar-Joseph)",
            "input_form": input_form,
            "num_genes": numrows,
            "num_time_points": numcols,
            "num_profiles": len(models),
            "num_candidate_profiles": len(candidates),
            "permutation_mode": perm_meta["permutation_mode"],
            "n_permutations_requested": perm_meta["n_permutations_requested"],
            "legacy_with_replacement": perm_meta["legacy_with_replacement"],
        }

        return STEMResult(
            profiles=profiles,
            gene_assignments=gene_assignments,
            filtered_genes=list(ds.filtered_genes),
            clusters=[list(c) for c in clusters],
            config=asdict(config),
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _validate_profile_params(config: STEMConfig) -> None:
        """ST.java clusterscript validation (ST.java:3208-3299)."""
        if config.max_unit_change < 1:
            raise STEMTCValueError("Maximum unit change must be >= 1")
        if config.max_model_profiles < 0:
            raise STEMTCValueError("Maximum number of profiles must be >= 0")
        if not (-1 <= config.max_correlation <= 1):
            raise STEMTCValueError(
                "Maximum correlation between model profiles must be in [-1,1]"
            )
        if config.n_permutations < 0:
            raise STEMTCValueError("Number of permutations per gene must be >=0")
        if config.candidate_cap < 1:
            raise STEMTCValueError("Maximum number of candidate model profiles must be positive")
        if config.candidate_cap < config.max_model_profiles:
            raise STEMTCValueError(
                "Maximum number of candidate model profiles must be >= maximum number of profiles"
            )
        if config.alpha < 0:
            raise STEMTCValueError("Alpha value must non-negative")
        if not (-1 <= config.cluster_min_correlation <= 1):
            raise STEMTCValueError("Minimum Correlation for Clustering must be in [-1,1]")
        if not (0 <= config.cluster_corr_percentile <= 1):
            raise STEMTCValueError(
                "Minimum Correlation Percentile for Clustering must be in [0,1]"
            )
