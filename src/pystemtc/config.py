"""Configuration mirroring the Java ``defaults.txt`` keys.

Defaults follow ST.java's ``*DEF`` statics (ST.java:61-115).  The M2 surface
adds the model-profile, permutation, significance and clustering parameters;
the comparison/GO/interface keys remain intentionally unmodeled (frozen V1
scope).  Validation messages mirror the Java warnings where the values are
hard-rejected here; other out-of-range values are kept (Java only warns).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .errors import STEMTCValueError

_NORMALIZE_MAP = {
    "log normalize data": "log",
    "normalize data": "normalize",
    "no normalization/add 0": "none_add0",
}
_CHANGE_MAP = {"maximum-minimum": True, "difference from 0": False}
_REPEAT_MODE_MAP = {
    "different time periods": "different_periods",
    "the same time period": "same_period",
}
_CORRECTION_MAP = {"bonferroni": "bonferroni", "false discovery rate": "fdr", "none": "none"}
_CLUSTERING_METHOD_MAP = {"stem clustering method": "stem", "stem": "stem", "k-means": "kmeans", "kmeans": "kmeans"}


@dataclass
class STEMConfig:
    """Algorithm configuration; defaults mirror Java's defaults.txt (ST.java:61-115)."""

    # --- M1 chain ---
    normalize: str = "normalize"  # "log" | "normalize" | "none_add0"
    max_missing: int = 0
    min_abs_expr: float = 1.0
    maxmin: bool = True  # True: max-min rule; False: difference from 0
    repeat_min_correlation: float = 0.0
    spot_included: bool = True
    repeat_mode: str = "different_periods"  # "different_periods" | "same_period"

    # --- M2: model profiles (ST.java:61, 80, 91, 93) ---
    max_model_profiles: int = 50  # Maximum_Number_of_Model_Profiles (nMaxProfiles)
    max_unit_change: int = 2  # Maximum_Unit_Change_..._between_Time_Points (nMaxUnit)
    max_correlation: float = 1.0  # Maximum_Correlation (dMaxCorrelationModel)
    candidate_cap: int = 1_000_000  # Maximum_Number_of_Candidate_Model_Profiles

    # --- M2: permutation / significance (ST.java:92, 94-95, 115) ---
    n_permutations: int = 50  # Number_of_Permutations_per_Gene; 0 = all permutations
    permute_t0: bool = True  # Permutation_Test_Should_Permute_Time_Point_0
    alpha: float = 0.05  # Significance_Level
    correction: str = "bonferroni"  # "bonferroni" | "fdr" | "none"

    # --- M2: profile clustering (ST.java:96-97) ---
    cluster_min_correlation: float = 0.7  # Clustering_Minimum_Correlation
    cluster_corr_percentile: float = 0.0  # Clustering_Minimum_Correlation_Percentile
    clustering_method: str = "stem"  # Clustering_Method; "kmeans" -> NotImplementedError

    data_file: str = ""
    repeat_files: list[str] = field(default_factory=list)

    @property
    def takelog(self) -> bool:
        return self.normalize == "log"

    @property
    def add0(self) -> bool:
        return self.normalize == "none_add0"

    @classmethod
    def from_defaults_file(cls, path: str | Path) -> "STEMConfig":
        """Parse a STEM defaults file (key<Tab>Value lines; unknown keys ignored)."""
        cfg = cls()
        for raw in Path(path).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("\t")
            key = key.strip()
            value = value.strip()
            bracket = key.find("[")
            if bracket != -1:
                key = key[:bracket]
            lkey = key.lower()
            lvalue = value.lower()
            if lkey == "normalize_data":
                if lvalue not in _NORMALIZE_MAP:
                    raise STEMTCValueError(f"{value} is an invalid argument for Normalize_Data")
                cfg.normalize = _NORMALIZE_MAP[lvalue]
            elif lkey == "maximum_number_of_missing_values":
                cfg.max_missing = int(value)
            elif lkey == "minimum_absolute_log_ratio_expression":
                cfg.min_abs_expr = float(value)
            elif lkey == "change_should_be_based_on":
                if lvalue not in _CHANGE_MAP:
                    raise STEMTCValueError(
                        f"{value} is an invalid argument for Change_should_be_based_on"
                    )
                cfg.maxmin = _CHANGE_MAP[lvalue]
            elif lkey == "minimum_correlation_between_repeats":
                cfg.repeat_min_correlation = float(value)
            elif lkey == "spot_ids_included_in_the_data_file":
                cfg.spot_included = lvalue == "true"
            elif lkey == "repeat_data_is_from":
                if lvalue not in _REPEAT_MODE_MAP:
                    raise STEMTCValueError(f"{value} is an invalid argument for Repeat_Data_is_from")
                cfg.repeat_mode = _REPEAT_MODE_MAP[lvalue]
            elif lkey == "repeat_data_files" or lkey == "repeat_data_files(comma delimited list)":
                cfg.repeat_files = [tok.strip() for tok in value.split(",") if tok.strip()]
            elif lkey == "data_file":
                cfg.data_file = value
            elif lkey == "maximum_number_of_model_profiles":
                cfg.max_model_profiles = int(value)
            elif lkey == "maximum_unit_change_in_model_profiles_between_time_points":
                cfg.max_unit_change = int(value)
            elif lkey == "maximum_correlation":
                cfg.max_correlation = float(value)
            elif lkey == "maximum_number_of_candidate_model_profiles":
                cfg.candidate_cap = int(value)
            elif lkey == "number_of_permutations_per_gene":
                cfg.n_permutations = int(value)
            elif lkey == "permutation_test_should_permute_time_point_0":
                cfg.permute_t0 = lvalue == "true"
            elif lkey == "significance_level":
                cfg.alpha = float(value)
            elif lkey == "correction_method":
                if lvalue not in _CORRECTION_MAP:
                    raise STEMTCValueError(
                        f"{value} is an invalid argument for Correction_Method"
                    )
                cfg.correction = _CORRECTION_MAP[lvalue]
            elif lkey == "clustering_minimum_correlation":
                cfg.cluster_min_correlation = float(value)
            elif lkey == "clustering_minimum_correlation_percentile":
                cfg.cluster_corr_percentile = float(value)
            elif lkey == "clustering_method":
                if lvalue not in _CLUSTERING_METHOD_MAP:
                    raise STEMTCValueError(f"{value} is an invalid argument for Clustering_Method")
                cfg.clustering_method = _CLUSTERING_METHOD_MAP[lvalue]
        return cfg
