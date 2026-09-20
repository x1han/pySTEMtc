"""Real-data benchmark harness for pySTEMTC (round-7.5, 2026-09-20).

This harness is the **ecological-validity counterpart** to ``benchmark_core.py``
(synthetic scaling grid). It runs **Java STEM v1.3.14 + PySTEMTC side-by-side
on user-provided real time-course data** and reports:

1. **Result consistency first** (``assignment_exact`` while writer is pending;
   ``C1 exact = NOT YET ASSESSED`` until writer implementation round) --
   the first-column judgment per expert ruling 2026-09-20, NOT Py/Java ratio.
2. **Performance** (end-to-end wall + peak RSS for both languages, plus
   PySTEMTC core_wall + stage timing).
3. **Dataset profile** (input / dedup / repeat / missing / threshold /
   retained-gene counts; sha256 provenance) so two datasets with the same
   raw row count are not interpreted as equivalent.

Round-7.5 P1 fixes from expert review 2026-09-20:

- **P1-1 (fair measurement)**: Python side now runs in **fresh subprocess
  per run** (not in-process). The parent times ``end_to_end_wall`` around
  ``subprocess.run`` (cross-language-comparable); the worker writes a
  ``core_wall`` (Py-internal optimization analysis). The Py worker protocol
  is reused from ``benchmark_core.py:225`` (``--worker`` JSON stdout).
  Java already used fresh JVM per run; child peak RSS via Psapi.
- **P1-2 (assignment_exact, NOT set-comparison)**: profile_ids compared as
  **ordered list** to preserve tie-assignment order; C1 column reported
  as ``NOT YET ASSESSED`` until writer implementation round.
- **P1-3 (no hardcoded Java config)**: every Java defaults field is now
  driven by ``manifest.config``; replicates + repeat_mode are wired through
  to both Python (``engine.fit(data, replicates=...)``) and Java
  (``Repeat_Data_Files`` / ``Repeat_Data_is_from``).
- **P1-4 (R1 developmental order)**: R1 v2 main.txt regenerated with
  ``8W_Brain`` (adult, 8 weeks) at the END of the developmental trajectory,
  sha256 ``ef8e6ae3915c50bcef518d737b915e9e36d83bb2bb02c59cf643b27a105a45ac``.

Round-7.5 解冻区:
- dataset profile adds ``input_rows``, ``unique_gene_names``,
  ``duplicate_gene_rows``, ``raw_missing_rate``, ``zero_rate``,
  ``nonpositive_rate``, ``input_sha256``, ``derivation_sha256``,
  ``derivation_description``.
- Java binary / stem.jar via CLI ``--java-bin`` / ``--stem-jar`` with
  env-var fallback then auto-discovery (NOT in manifest -- manifest is
  portable across machines).
- PyYAML is a required dependency; the round-7.4 hand-rolled fallback is
  removed (it could not fully parse the locked schema).

Highest-rule (round-7.5 expert ruling):
- never modify the real dataset to make it easier to benchmark;
- never change algorithm parameters between Java and Python;
- never pre-pick n_permutations / candidate_cap to make the run "prettier";
- **Java stage timing is intentionally blank** -- we don't fake one.

Usage:
    python benchmarks/benchmark_real.py --manifest D:/stem/benchmark_data/R1/manifest.yaml
    python benchmarks/benchmark_real.py --manifest <yaml> --formal 3 --warmup 1
    python benchmarks/benchmark_real.py --manifest <yaml> --formal 1   # smoke

Outputs:
    <outdir>/<ts>_real/dataset_profile.csv   # one row per dataset
    <outdir>/<ts>_real/runs.csv              # one row per run (Py + Java)
    <outdir>/<ts>_real/summary.md            # main table: Py/Java side-by-side
    <outdir>/<ts>_real/<id>_genetable_java.txt  # copy of Java genetable
    <outdir>/<ts>_real/<id>_profiletable_java.txt  # copy of Java profiletable
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform as _platform
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# STAGE_KEYS mirrors benchmark_core.py -- the 7 stages PySTEMTC exposes via
# ``result.timing``. Java rows leave these blank (Java has no stage timer;
# we do not fake one).
STAGE_KEYS = (
    "input_read",
    "normalize_filter",
    "profile_generation",
    "assignment",
    "permutation",
    "significance",
    "clustering",
)

RESULTS = Path(__file__).parent / "results" / "real"


# --------------------------------------------------------------------------
# YAML manifest (PyYAML is a required dependency, no fallback)
# --------------------------------------------------------------------------

def _load_manifest(path: Path) -> dict:
    """Read the locked manifest schema (§1.12). PyYAML is required.

    Raises:
        ImportError if PyYAML is not installed (round-7.5 ruling: the
            hand-rolled fallback in round-7.4 was broken -- it could not
            fully parse the schema; we no longer pretend otherwise).
    """
    import yaml
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# --------------------------------------------------------------------------
# dataset profile (input / dedup / repeat / missing / threshold / retained)
# --------------------------------------------------------------------------

def _profile_dataset(manifest: dict, dataset_id: str) -> dict:
    """Read the main file once and compute the dataset profile.

    Round-7.5 expanded schema (per expert ruling 2026-09-20):
        input_rows, unique_gene_names, duplicate_gene_rows,
        T, reps,
        raw_missing_rate, zero_rate, nonpositive_rate,   # nonpositive = effective missing under log mode
        value_min, value_max, value_median,
        input_sha256, derivation_sha256, derivation_description,
        + engine-side post-filter counts (filled after first run)
    """
    import hashlib
    main_path = Path(manifest["main"])
    if not main_path.exists():
        raise FileNotFoundError(f"manifest.main not found: {main_path}")
    n_cols = None
    rows: list[list[str]] = []
    with open(main_path, encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter="\t")
        for row in reader:
            rows.append(row)
    header = rows[0]
    body = rows[1:]
    n_cols = len(header) - 1
    if manifest["config"].get("spot_included", True):
        time_cols = n_cols - 1
    else:
        time_cols = n_cols
    # Use the FIRST data column as the gene identifier (independent of
    # spot_included: when spot_included=True, the first column IS the gene
    # name; when False, the only ID column is the gene name). The spec is
    # captured by spot_included; the ID column is always body[i][0].
    gene_names = [r[0] for r in body]
    input_rows = len(body)
    unique_gene_names = len(set(gene_names))
    duplicate_gene_rows = input_rows - unique_gene_names

    raw_missing = 0
    zeros = 0
    nonpositive = 0
    values: list[float] = []
    for r in body:
        for cell in r[-time_cols:]:
            if cell == "" or cell.lower() in ("na", "nan", "null"):
                raw_missing += 1
                continue
            try:
                v = float(cell)
            except ValueError:
                raw_missing += 1
                continue
            values.append(v)
            if v == 0.0:
                zeros += 1
            if v <= 0.0:
                nonpositive += 1
    total_cells = input_rows * time_cols
    main_sha = hashlib.sha256(main_path.read_bytes()).hexdigest()
    desc = manifest.get("description") or {}
    return {
        "dataset_id": dataset_id,
        "input_rows": input_rows,
        "unique_gene_names": unique_gene_names,
        "duplicate_gene_rows": duplicate_gene_rows,
        "T": time_cols,
        "reps": len(manifest.get("replicates") or []),
        "raw_missing_rate": round(raw_missing / total_cells, 6) if total_cells else 0.0,
        "zero_rate": round(zeros / total_cells, 6) if total_cells else 0.0,
        "nonpositive_rate": round(nonpositive / total_cells, 6) if total_cells else 0.0,
        "value_min": round(min(values), 4) if values else 0.0,
        "value_max": round(max(values), 4) if values else 0.0,
        "value_median": round(statistics.median(values), 4) if values else 0.0,
        "input_sha256": desc.get("input_sha256", ""),
        "derivation_sha256": main_sha,
        "derivation_description": desc.get("preprocessing", ""),
        # Engine-side post-filter counts (filled in after first run):
        "genes_after_dedup": "",
        "genes_after_repeat_filter": "",
        "genes_after_missing_filter": "",
        "genes_after_threshold_filter": "",
        "final_retained_genes": "",
    }


# --------------------------------------------------------------------------
# subprocess: PySTEMTC worker (reuses benchmark_core.py's --worker protocol)
# --------------------------------------------------------------------------
# Protocol shape (mirrors benchmark_core.py:225-267):
#   --worker mode:
#     - parses --manifest and --language=python from argv
#     - imports pystemtc.engine (fresh subprocess per run)
#     - engine.fit(data, replicates=...)
#     - emits single-line JSON to stdout: {dataset_id, language, exit_code,
#       core_wall_s, peak_rss_bytes, stages{}, summary{}, gene_assignments{}}
#   parent mode:
#     - subprocess.run([..., "--worker", ...])
#     - times end_to_end_wall_s around the call (cross-language-comparable)
#     - reads JSON payload from worker stdout (core_wall + stage timing + assignments)

def _python_worker_main(manifest: dict, dataset_id: str) -> dict:
    """In-worker payload builder. Called inside the fresh subprocess."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.pystemtc.engine import STEM

    cfg = manifest["config"]
    replicates = manifest.get("replicates") or []
    t0 = time.perf_counter()
    engine = STEM(
        normalize=cfg["normalize"],
        max_unit_change=cfg["max_unit_change"],
        max_model_profiles=cfg["max_model_profiles"],
        max_correlation=cfg["max_correlation"],
        candidate_cap=cfg["candidate_cap"],
        n_permutations=cfg["n_permutations"],
        permute_t0=cfg["permute_t0"],
        alpha=cfg.get("alpha", 0.05),
        correction=cfg["correction"],
        clustering_method=cfg.get("clustering_method", "stem"),
        spot_included=cfg.get("spot_included", True),
        max_missing=cfg["max_missing"],
        min_abs_expr=cfg["min_abs_expr"],
        repeat_mode=cfg.get("repeat_mode", "different_periods"),
        repeat_min_correlation=cfg.get("repeat_min_correlation", 0.0),
        cluster_min_correlation=cfg.get("cluster_min_correlation", 0.7),
        cluster_corr_percentile=cfg.get("cluster_corr_percentile", 0.0),
        change_rule=cfg.get("change_rule", "max_minus_min"),
    )
    res = engine.fit(manifest["main"], replicates=replicates if replicates else None)
    core_wall = time.perf_counter() - t0
    payload = {
        "dataset_id": dataset_id,
        "language": "python",
        "exit_code": 0,
        "core_wall_s": core_wall,
        "peak_rss_bytes": _peak_rss_bytes(),
        "stages": {key: res.timing.get(key, 0.0) for key in STAGE_KEYS},
        "summary": {
            "genes_input": res.metadata.get("genes_input", 0),
            "genes_retained": len(res.gene_assignments),
            "profiles": len(res.profiles),
            "permutation_mode": res.metadata.get("permutation_mode", ""),
        },
        # Round-7.5 P1-2: ordered list (NOT set) so tie-assignment order is
        # preserved when comparing against Java.
        "gene_assignments": {ga.gene: list(ga.profile_ids) for ga in res.gene_assignments},
    }
    return payload


def _spawn_python_worker(manifest_path: Path, dataset_id: str) -> tuple[dict, float]:
    """Spawn a fresh Python subprocess; time ``end_to_end_wall`` around the
    call; return (worker_payload, end_to_end_wall_s).

    Mirrors benchmark_core.py's _spawn_worker pattern (line 275).
    """
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--manifest", str(manifest_path),
        "--language", "python",
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    end_to_end_wall = time.perf_counter() - t0
    if proc.returncode != 0:
        raise RuntimeError(
            f"python worker failed rc={proc.returncode}\n"
            f"stdout: {proc.stdout[-1000:]}\nstderr: {proc.stderr[-1000:]}"
        )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("python worker produced no JSON line")
    payload = json.loads(lines[-1])
    payload["end_to_end_wall_s"] = end_to_end_wall
    return payload, end_to_end_wall


# --------------------------------------------------------------------------
# subprocess: Java STEM v1.3.14 (batch mode, GBK oracle)
# --------------------------------------------------------------------------

def _resolve_java_paths(args: argparse.Namespace) -> tuple[str, str, str, str]:
    """Resolve Java binary and stem.jar path. Round-7.5 ruling:
    CLI > environment variable > auto-discovery > hardcoded fallback.
    Returns (java_bin, java_version_str, stem_jar_path, stem_jar_sha256).
    """
    import hashlib
    java = (
        args.java_bin
        or os.environ.get("JAVA_BIN")
        or shutil.which("java")
        or r"C:\Program Files (x86)\Common Files\Oracle\Java\java8path\java.exe"
    )
    stem_jar = (
        args.stem_jar
        or os.environ.get("STEM_JAR")
        or r"D:\stem\stem.jar"
    )
    java_version_str = _java_version(java)
    try:
        jar_sha = hashlib.sha256(Path(stem_jar).read_bytes()).hexdigest()
    except Exception:
        jar_sha = "unreadable"
    return java, java_version_str, stem_jar, jar_sha


def _java_run(manifest: dict, dataset_id: str, out_dir: Path,
              java_bin: str, stem_jar: str) -> dict:
    """Invoke Java in batch mode (3 args). Writes the genetable/profiletable
    into out_dir; returns dict with end_to_end_wall + peak RSS + assignments
    parsed from the GBK-encoded genetable.

    The harness *never* spawns Java in single-file mode without ``-o`` to
    avoid the GUI launch (ST.java dispatch on args.length==2).
    """
    cfg_dir = out_dir / "_cfg"
    java_out_dir = out_dir / "_java_out"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    java_out_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / f"{dataset_id}.txt"
    cfg_path.write_text(_render_stem_config(manifest, dataset_id), encoding="utf-8")

    cmd = [
        java_bin,
        "-cp", stem_jar,
        "edu.cmu.cs.sb.stem.ST",
        "-b", str(cfg_dir), str(java_out_dir),
    ]
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    peak = _poll_peak_rss(proc)
    stdout_b, stderr_b = proc.communicate()
    end_to_end_wall = time.perf_counter() - t0
    exit_code = proc.returncode
    if exit_code != 0:
        raise RuntimeError(
            f"Java batch failed rc={exit_code}\n"
            f"stdout: {stdout_b.decode('gbk','replace')[:400]}\n"
            f"stderr: {stderr_b.decode('gbk','replace')[:400]}"
        )

    java_genetable = java_out_dir / f"{dataset_id}_genetable.txt"
    java_profiletable = java_out_dir / f"{dataset_id}_profiletable.txt"
    if not java_genetable.exists():
        raise RuntimeError(f"Java did not produce {java_genetable}")
    # Copy to canonical location under out_dir
    shutil.copy2(java_genetable, out_dir / f"{dataset_id}_genetable_java.txt")
    if java_profiletable.exists():
        shutil.copy2(java_profiletable, out_dir / f"{dataset_id}_profiletable_java.txt")

    assignments = _parse_java_genetable(java_genetable)
    n_sig = _count_java_significant(java_profiletable) if java_profiletable.exists() else 0
    return {
        "dataset_id": dataset_id,
        "language": "java",
        "exit_code": exit_code,
        "core_wall_s": "",  # Java has no internal stage timer; do not fake.
        "end_to_end_wall_s": end_to_end_wall,
        "peak_rss_bytes": peak,
        "stages": {key: "" for key in STAGE_KEYS},
        "summary": {
            "genes_retained": len(assignments),
            "significant_profiles": n_sig,
        },
        "gene_assignments": assignments,
    }


def _render_stem_config(manifest: dict, dataset_id: str) -> str:
    """Render a Java STEM defaults file (the format ST.java:parseDefaults reads).

    Round-7.5 P1-3: ALL algorithm parameters are driven by manifest.config;
    no field is hardcoded except K-means-only values (Number_of_Clusters_K,
    Number_of_Random_Starts) which only apply when clustering_method=kmeans.
    """
    cfg = manifest["config"]
    main = manifest["main"].replace("/", "\\")
    normalize_map = {"log": "Log normalize data", "normalize": "Normalize data",
                     "none_add0": "No normalization/add 0"}
    spot_inc = "true" if cfg.get("spot_included", True) else "false"
    correction_map = {"bonferroni": "Bonferroni", "fdr": "False Discovery Rate",
                      "none": "None"}
    repeat_mode_str = cfg.get("repeat_mode", "different_periods")
    repeat_mode_java = "Different time periods" if repeat_mode_str == "different_periods" else "The same time period"
    replicates = manifest.get("replicates") or []
    replicate_files_str = ",".join(r.replace("/", "\\") for r in replicates) if replicates else ""

    change_rule = cfg.get("change_rule", "max_minus_min")
    change_rule_java = "Maximum-Minimum" if change_rule == "max_minus_min" else "Difference From 0"

    clustering_method = cfg.get("clustering_method", "stem")
    clustering_method_java = "STEM Clustering Method" if clustering_method == "stem" else "K-means"

    lines = [
        "#Main Input:",
        f"Data_File\t{main}",
        "Gene_Annotation_Source\tUser provided",
        "Gene_Annotation_File\t",
        "Cross_Reference_Source\tUser provided",
        "Cross_Reference_File\t",
        "Gene_Location_Source\tUser provided",
        "Gene_Location_File\t",
        f"Clustering_Method[STEM Clustering Method,K-means]\t{clustering_method_java}",
        f"Maximum_Number_of_Model_Profiles\t{cfg['max_model_profiles']}",
        f"Maximum_Unit_Change_in_Model_Profiles_between_Time_Points\t{cfg['max_unit_change']}",
        # K-means-only defaults; ignored by STEM clustering method but Java
        # still parses them. Defaults are surfaced in the manifest schema.
        f"Number_of_Clusters_K\t{cfg.get('n_clusters', 10)}",
        f"Number_of_Random_Starts\t{cfg.get('random_starts', 20)}",
        f"Normalize_Data[Log normalize data,Normalize data,No normalization/add 0]\t{normalize_map[cfg['normalize']]}",
        f"Spot_IDs_included_in_the_data_file\t{spot_inc}",
        "",
        "#Repeat data",
        f"Repeat_Data_Files(comma delimited list)\t{replicate_files_str}",
        f"Repeat_Data_is_from[Different time periods,The same time period]\t{repeat_mode_java}",
        "",
        "#Comparison Data:",
        "Comparison_Data_File\t",
        "Comparison_Repeat_Data_Files(comma delimited list)\t",
        "Comparison_Repeat_Data_is_from[Different time periods,The same time period]\tDifferent time periods",
        "Comparison_Minimum_Number_of_genes_in_intersection\t5",
        "Comparison_Maximum_Uncorrected_Intersection_pvalue\t0.0050",
        "",
        "#Filtering:",
        f"Maximum_Number_of_Missing_Values\t{cfg['max_missing']}",
        f"Minimum_Correlation_between_Repeats\t{cfg.get('repeat_min_correlation', 0.0)}",
        f"Minimum_Absolute_Log_Ratio_Expression\t{cfg['min_abs_expr']}",
        f"Change_should_be_based_on[Maximum-Minimum,Difference From 0]\t{change_rule_java}",
        "Pre-filtered_Gene_File\t",
        "",
        "#Model Profiles",
        f"Maximum_Correlation\t{cfg['max_correlation']}",
        f"Number_of_Permutations_per_Gene\t{cfg['n_permutations']}",
        f"Maximum_Number_of_Candidate_Model_Profiles\t{cfg['candidate_cap']}",
        f"Significance_Level\t{cfg.get('alpha', 0.05)}",
        f"Correction_Method[Bonferroni,False Discovery Rate,None]\t{correction_map[cfg['correction']]}",
        f"Permutation_Test_Should_Permute_Time_Point_0\t{'true' if cfg['permute_t0'] else 'false'}",
        "",
        "#Clustering Profiles:",
        f"Clustering_Minimum_Correlation\t{cfg.get('cluster_min_correlation', 0.7)}",
        f"Clustering_Minimum_Correlation_Percentile\t{cfg.get('cluster_corr_percentile', 0.0)}",
        "",
        "#Gene Annotations:",
        "Category_ID_File\t",
        "Include_Biological_Process\ttrue",
        "Include_Molecular_Function\ttrue",
        "Include_Cellular_Process\ttrue",
        "Only_include_annotations_with_these_evidence_codes\t",
        "Only_include_annotations_with_these_taxon_IDs\t",
        "",
        "#GO Analysis:",
        "Multiple_hypothesis_correction_method_enrichment[Bonferroni,Randomization]\tRandomization",
        "Minimum_GO_level\t3",
        "Minimum_GO_Minimum_number_of_genes\t5",
        "Number_of_samples_for_randomized_multiple_hypothesis_correction\t500",
        "",
        "#Interface Options",
        "Gene_display_policy_on_main_interface[Do not display,Display only selected,Display all]\tDo not display",
        "Gene_Color(R,G,B)\t204,51,0",
        "Display_Model_Profile\ttrue",
        "Display_Profile_ID\ttrue",
        "Display_details_when_ordering\ttrue",
        "Show_Main_Y-axis_gene_tick_marks\tfalse",
        "Main_Y-axis_gene_tick_interval\t1.0",
        "Y-axis_scale_for_genes_on_main_interface_should_be[Gene specific,Profile specific,Global]\tProfile specific",
        "Scale_should_be_based_on_only_selected_genes\ttrue",
        "Y-axis_scale_on_details_windows_should_be[Determined automatically,Fixed]\tDetermined automatically",
        "Y_Scale_Min\t-3.0",
        "Y_Scale_Max\t3.0",
        "Tick_interval\t1.0",
        "X-axis_scale_should_be[Uniform,Based on real time]\tUniform",
    ]
    return "\n".join(lines) + "\n"


def _parse_java_genetable(path: Path) -> dict[str, list[int]]:
    """Java genetable is GBK + CRLF. Profile column is index 2, ';'-joined ints."""
    out: dict[str, list[int]] = {}
    with open(path, encoding="gbk") as fh:
        reader = csv.reader(fh, delimiter="\t")
        next(reader)  # header
        for row in reader:
            if len(row) < 3:
                continue
            gene = row[0]
            try:
                out[gene] = [int(p) for p in row[2].split(";")]
            except ValueError:
                continue
    return out


def _count_java_significant(path: Path) -> int:
    """Profiletable Cluster column: -1 = non-significant, anything else = sig."""
    if not path.exists():
        return 0
    n = 0
    with open(path, encoding="gbk") as fh:
        reader = csv.reader(fh, delimiter="\t")
        next(reader)
        for row in reader:
            if len(row) >= 3 and row[2].strip() != "-1":
                n += 1
    return n


# --------------------------------------------------------------------------
# peak RSS: own process (Python) + child process (Java) -- both required
# --------------------------------------------------------------------------

def _peak_rss_bytes() -> int:
    """Peak RSS of the current Python process."""
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes as wt

        psapi = ctypes.WinDLL("psapi.dll")
        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = PMC()
        counters.cb = ctypes.sizeof(counters)
        psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
        psapi.GetProcessMemoryInfo.restype = wt.BOOL
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return int(counters.PeakWorkingSetSize)
        return 0
    if sys.platform.startswith("linux"):
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    if sys.platform == "darwin":
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return 0


def _poll_peak_rss(proc: subprocess.Popen) -> int:
    """Sample the child process's PeakWorkingSetSize every 50 ms while running.
    On Linux, use wait4 + getrusage(RUSAGE_CHILDREN) once at end (a single
    sample is sufficient -- child's peak is reported as final usage)."""
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes as wt

        psapi = ctypes.WinDLL("psapi.dll")
        kernel32 = ctypes.WinDLL("kernel32.dll")

        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = PMC()
        counters.cb = ctypes.sizeof(counters)
        psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
        psapi.GetProcessMemoryInfo.restype = wt.BOOL
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        peak = 0
        while proc.poll() is None:
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, proc.pid
            )
            if handle:
                if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                    peak = max(peak, int(counters.PeakWorkingSetSize))
                kernel32.CloseHandle(handle)
            time.sleep(0.05)
        return peak
    if sys.platform.startswith("linux"):
        try:
            _, _, rusage = os.wait4(proc.pid, 0)
            return rusage.ru_maxrss * 1024
        except ChildProcessError:
            return 0
    return 0


# --------------------------------------------------------------------------
# Compatibility comparison: assignment_exact (ordered list, NOT set)
# --------------------------------------------------------------------------

def _compare_consistency(py: dict, java: dict) -> dict:
    """Round-7.5 P1-2: compare ``profile_ids`` as **ordered list** (NOT
    set) so tie-assignment order is preserved.

    Returns a dict with:
        n_common / n_java_only / n_py_only
        n_mismatches
        assignment_exact -- True iff every retained gene has the same
            ordered list of profile_ids in both languages.
        first_mismatches -- up to 5 (gene, java_profile_ids, py_profile_ids)
            for inspection.
    """
    py_a = py.get("gene_assignments", {})
    java_a = java.get("gene_assignments", {})
    common = set(py_a) & set(java_a)
    java_only = set(java_a) - set(py_a)
    py_only = set(py_a) - set(java_a)
    mismatches = []
    for g in common:
        # Ordered list comparison -- preserves tie order.
        if list(py_a[g]) != list(java_a[g]):
            mismatches.append((g, list(java_a[g]), list(py_a[g])))
    return {
        "n_common": len(common),
        "n_java_only": len(java_only),
        "n_py_only": len(py_only),
        "n_mismatches": len(mismatches),
        "assignment_exact": (
            len(java_only) == 0 and len(py_only) == 0 and len(mismatches) == 0
        ),
        "first_mismatches": mismatches[:5],
    }


# --------------------------------------------------------------------------
# CSV / MD writers
# --------------------------------------------------------------------------

CSV_FIELDS = (
    ["dataset_id", "run", "kind", "language"]
    + ["input_rows", "T", "reps",
       "raw_missing_rate", "zero_rate", "nonpositive_rate",
       "unique_gene_names", "duplicate_gene_rows",
       "input_sha256", "derivation_sha256"]
    + ["final_retained_genes", "profiles", "n_perms", "permutation_mode"]
    + ["end_to_end_wall_s", "core_wall_s", "peak_rss_mib", "exit_code"]
    + [f"stage_{key}_s" for key in STAGE_KEYS]
    + ["pystemtc_version", "git_commit", "python", "numpy", "pandas", "platform",
       "cpu_model", "logical_cpu_count", "ram_gib", "os_release",
       "java_bin", "java_version", "stem_jar_path", "stem_jar_sha256"]
)


def _env_versions(git_commit: str, java_bin: str = "", java_version_str: str = "",
                  stem_jar: str = "", stem_jar_sha256: str = "") -> dict:
    import importlib.metadata as md
    out = {
        "pystemtc_version": md.version("pystemtc") if _pkg_installed("pystemtc") else "0.0.0+local",
        "git_commit": git_commit,
        "python": _platform.python_version(),
        "numpy": md.version("numpy"),
        "pandas": md.version("pandas"),
        "platform": _platform.platform(),
        "cpu_model": _platform.processor() or "unknown",
        "logical_cpu_count": str(os.cpu_count() or 0),
        "ram_gib": str(round(_ram_gib(), 1)),
        "os_release": _platform.release(),
        "java_bin": java_bin or "",
        "java_version": java_version_str or _java_version(),
        "stem_jar_path": stem_jar or "",
        "stem_jar_sha256": stem_jar_sha256 or "",
    }
    return out


def _pkg_installed(name: str) -> bool:
    try:
        import importlib.metadata as md
        md.version(name)
        return True
    except Exception:
        return False


def _ram_gib() -> float:
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes as wt
        class SM(ctypes.Structure):
            _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        s = SM(); s.dwLength = ctypes.sizeof(s)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)):
            return s.ullTotalPhys / 2 ** 30
    return 0.0


def _java_version(java: str | None = None) -> str:
    if java is None:
        java = os.environ.get("JAVA_BIN") or shutil.which("java") or "java"
    try:
        out = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=10)
        return (out.stderr or out.stdout).splitlines()[0].strip()
    except Exception:
        return "unknown"


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1],
            timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _csv_row(dataset_id: str, run_idx: int, kind: str, lang: str,
             profile: dict, payload: dict, env: dict) -> dict:
    summary = payload.get("summary", {})
    row = {
        "dataset_id": dataset_id,
        "run": run_idx,
        "kind": kind,
        "language": lang,
        "input_rows": profile["input_rows"],
        "T": profile["T"],
        "reps": profile["reps"],
        "raw_missing_rate": profile["raw_missing_rate"],
        "zero_rate": profile["zero_rate"],
        "nonpositive_rate": profile["nonpositive_rate"],
        "unique_gene_names": profile["unique_gene_names"],
        "duplicate_gene_rows": profile["duplicate_gene_rows"],
        "input_sha256": profile["input_sha256"],
        "derivation_sha256": profile["derivation_sha256"],
        "final_retained_genes": summary.get("genes_retained", ""),
        "profiles": summary.get("profiles", ""),
        "n_perms": "",  # manifest-driven, surfaced in summary.md
        "permutation_mode": summary.get("permutation_mode", ""),
        "end_to_end_wall_s": round(payload.get("end_to_end_wall_s", 0.0), 4),
        "core_wall_s": round(payload["core_wall_s"], 4)
                       if isinstance(payload.get("core_wall_s"), float)
                       else payload.get("core_wall_s", ""),
        "peak_rss_mib": round(payload["peak_rss_bytes"] / 2 ** 20, 1),
        "exit_code": payload["exit_code"],
        "pystemtc_version": env["pystemtc_version"],
        "git_commit": env["git_commit"],
        "python": env["python"],
        "numpy": env["numpy"],
        "pandas": env["pandas"],
        "platform": env["platform"],
        "cpu_model": env["cpu_model"],
        "logical_cpu_count": env["logical_cpu_count"],
        "ram_gib": env["ram_gib"],
        "os_release": env["os_release"],
        "java_bin": env["java_bin"],
        "java_version": env["java_version"],
        "stem_jar_path": env["stem_jar_path"],
        "stem_jar_sha256": env["stem_jar_sha256"],
    }
    for key in STAGE_KEYS:
        v = payload["stages"].get(key, "")
        row[f"stage_{key}_s"] = round(v, 4) if isinstance(v, float) else v
    return row


def _write_summary_md(out_dir: Path, dataset_id: str, profile: dict,
                      py_payloads: list[dict], java_payloads: list[dict],
                      consistency: dict, env: dict, args: argparse.Namespace) -> None:
    """Write the main table. Round-7.5:

    - **end_to_end_wall** is the cross-language-comparable metric
      (parent subprocess.run timer; same on both sides).
    - **core_wall** is reported for PySTEMTC only; Java has no internal
      stage timer (no faking).
    - Py/Java end-to-end ratio is descriptive only -- NOT a release gate.
    """
    py_e2e = [p["end_to_end_wall_s"] for p in py_payloads]
    java_e2e = [p["end_to_end_wall_s"] for p in java_payloads]
    py_core = [p["core_wall_s"] for p in py_payloads if isinstance(p.get("core_wall_s"), float)]
    py_rss = [p["peak_rss_bytes"] for p in py_payloads]
    java_rss = [p["peak_rss_bytes"] for p in java_payloads]

    md = out_dir / "summary.md"
    lines = [
        f"# Real-data benchmark summary -- {dataset_id}",
        "",
        f"- generated: pySTEMTC {env['pystemtc_version']} @ {env['git_commit']}",
        f"- Python: {env['python']}, NumPy {env['numpy']}, pandas {env['pandas']}",
        f"- Java: {env['java_version']} (binary: `{env['java_bin']}`)",
        f"- stem.jar: `{env['stem_jar_path']}` (sha256 `{env['stem_jar_sha256'][:16]}...`)",
        f"- platform: {env['platform']}",
        f"- CPU: {env['cpu_model']} ({env['logical_cpu_count']} logical), RAM {env['ram_gib']} GiB",
        "",
        "> **Performance vs Compatibility**: The first-column judgment is "
        "**assignment_exact** (Java vs PySTEMTC profile_id order on every "
        "retained gene). Performance numbers (end-to-end wall, peak RSS) "
        "are descriptive, NOT release-blocking. The Py/Java end-to-end ratio "
        "above 1 is *not* a release gate -- it would be *fair* to compare "
        "now because both languages use the same subprocess-isolated "
        "measurement protocol.",
        "",
        "## Dataset profile (round-7.5 expanded schema)",
        "",
        "| dataset_id | input_rows | unique_genes | dup_rows | T | reps |",
        "|---|---|---|---|---|---|",
        f"| {dataset_id} | {profile['input_rows']} | {profile['unique_gene_names']} |"
        f" {profile['duplicate_gene_rows']} | {profile['T']} | {profile['reps']} |",
        "",
        "| raw_missing | zero | nonpositive (= effective missing under log) | value range | value_median |",
        "|---|---|---|---|---|",
        f"| {profile['raw_missing_rate']:.4f} | {profile['zero_rate']:.4f} |"
        f" {profile['nonpositive_rate']:.4f} | [{profile['value_min']}, {profile['value_max']}] |"
        f" {profile['value_median']} |",
        "",
        "### Provenance (sha256)",
        "",
        f"- input_sha256 (from manifest.description): `{profile['input_sha256'] or '(not provided)'}`",
        f"- derivation_sha256 (main.txt on disk): `{profile['derivation_sha256']}`",
        f"- derivation_description: {profile['derivation_description'] or '(none)'}",
        "",
        "## assignment_exact (round-7.5; ordered list, NOT set)",
        "",
        f"- Java retained: {consistency['n_common'] + consistency['n_java_only']}",
        f"- Py retained:   {consistency['n_common'] + consistency['n_py_only']}",
        f"- Common:        {consistency['n_common']}",
        f"- Java-only:     {consistency['n_java_only']}",
        f"- Py-only:       {consistency['n_py_only']}",
        f"- Mismatches in common (ordered-list !=): {consistency['n_mismatches']}",
        f"- **assignment_exact: {'PASS' if consistency['assignment_exact'] else 'FAIL'}**",
    ]
    if consistency.get("first_mismatches"):
        lines += ["", "First mismatches:", ""]
        for g, java_l, py_l in consistency["first_mismatches"]:
            lines.append(f"  - `{g}`: java={java_l}  py={py_l}")
    lines += [
        "",
        "## Compatibility C1",
        "",
        "> **NOT YET ASSESSED** -- the writer (``STEMResult.write_java_tables``) "
        "is implemented in a future round; before then, this benchmark cannot "
        "produce a Python genetable / profiletable to byte-compare against the "
        "Java oracle. See docs/03 §1.10 (round-7.3 writer contract sweep).",
        "",
        "## Main table -- end-to-end wall (parent subprocess timer, cross-language-comparable)",
        "",
        "| Language | wall median | wall min | wall max | RSS MiB median | exit_code |",
        "|---|---|---|---|---|---|",
    ]
    for label, walls, rss, payloads in (
        ("Python", py_e2e, py_rss, py_payloads),
        ("Java",   java_e2e, java_rss, java_payloads),
    ):
        if not walls:
            continue
        exit_codes = sorted({p["exit_code"] for p in payloads})
        lines.append(
            f"| {label} | {statistics.median(walls):.3f} | {min(walls):.3f} |"
            f" {max(walls):.3f} | {statistics.median(rss)/2**20:.1f} | {exit_codes} |"
        )
    if py_e2e and java_e2e:
        ratio = statistics.median(py_e2e) / statistics.median(java_e2e)
        lines.append(f"\nPy/Java end-to-end ratio (median, descriptive): **{ratio:.2f}x**")
    if py_core:
        lines += [
            "",
            "## PySTEMTC core_wall (engine.fit() internal; for Py optimization analysis only)",
            "",
            "| core_wall median | core_wall min | core_wall max |",
            "|---|---|---|",
            f"| {statistics.median(py_core):.3f} | {min(py_core):.3f} | {max(py_core):.3f} |",
            "",
            "## PySTEMTC stage timings (median, seconds)",
            "",
            "| " + " | ".join(STAGE_KEYS) + " |",
            "|" + "---|" * len(STAGE_KEYS) + "|",
        ]
        medians = [statistics.median([p["stages"][k] for p in py_payloads]) for k in STAGE_KEYS]
        lines.append("| " + " | ".join(f"{m:.3f}" for m in medians) + " |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--manifest", required=True, type=Path,
                    help="path to YAML manifest for a real dataset")
    ap.add_argument("--warmup", type=int, default=1, help="discarded warm-up runs (default 1)")
    ap.add_argument("--formal", type=int, default=3, help="formal runs (default 3)")
    ap.add_argument("--outdir", default=None, help="default: benchmarks/results/real/<UTCts>")
    ap.add_argument("--no-java", action="store_true", help="skip Java side (Python only)")
    ap.add_argument("--java-bin", default=None,
                    help="path to java executable (overrides $JAVA_BIN and auto-discovery)")
    ap.add_argument("--stem-jar", default=None,
                    help="path to stem.jar (overrides $STEM_JAR and auto-discovery)")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--language", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.formal < 1:
        raise SystemExit("--formal must be >= 1")

    # Worker mode: invoked by parent as a fresh subprocess. Read the
    # manifest, run the analysis, emit a single JSON line to stdout.
    if args.worker:
        manifest = _load_manifest(args.manifest)
        dataset_id = manifest.get("id") or args.manifest.stem
        if args.language == "python":
            payload = _python_worker_main(manifest, dataset_id)
            print(json.dumps(payload), flush=True)
        return

    manifest = _load_manifest(args.manifest)
    dataset_id = manifest.get("id") or args.manifest.stem

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (Path(args.outdir) if args.outdir else RESULTS / f"{stamp}_real")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"pySTEMTC real benchmark {stamp}: dataset={dataset_id}", flush=True)
    profile = _profile_dataset(manifest, dataset_id)
    # Resolve Java paths early so the env record reflects what we used.
    java_bin, java_version_str, stem_jar, jar_sha = _resolve_java_paths(args)
    env = _env_versions(_git_commit(), java_bin=java_bin,
                        java_version_str=java_version_str,
                        stem_jar=stem_jar, stem_jar_sha256=jar_sha)
    print(f"env: {env}", flush=True)
    print(f"profile: {profile}", flush=True)

    py_payloads: list[dict] = []
    java_payloads: list[dict] = []
    rows: list[dict] = []
    total = args.warmup + args.formal
    for run_idx in range(total):
        kind = "warmup" if run_idx < args.warmup else "formal"
        # --- Python side (fresh subprocess per run; end_to_end_wall in
        # parent; core_wall + stage timings from worker JSON) ---
        py, py_e2e = _spawn_python_worker(args.manifest, dataset_id)
        py["end_to_end_wall_s"] = py_e2e
        if kind == "formal":
            py_payloads.append(py)
        rows.append(_csv_row(dataset_id, run_idx + 1, kind, "python", profile, py, env))
        print(f"[{dataset_id}] python {kind} run {run_idx + 1}/{total}:"
              f" e2e={py['end_to_end_wall_s']:.3f}s"
              f" core={py['core_wall_s']:.3f}s"
              f" rss={py['peak_rss_bytes']/2**20:.1f}MiB",
              flush=True)
        # --- Java side (fresh JVM per run; end_to_end_wall in parent) ---
        if not args.no_java:
            java = _java_run(manifest, dataset_id, out_dir, java_bin, stem_jar)
            if kind == "formal":
                java_payloads.append(java)
            rows.append(_csv_row(dataset_id, run_idx + 1, kind, "java", profile, java, env))
            print(f"[{dataset_id}] java   {kind} run {run_idx + 1}/{total}:"
                  f" e2e={java['end_to_end_wall_s']:.3f}s"
                  f" rss={java['peak_rss_bytes']/2**20:.1f}MiB"
                  f" exit={java['exit_code']}", flush=True)

    # dataset profile CSV
    profile_csv = out_dir / "dataset_profile.csv"
    with open(profile_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(profile.keys()))
        w.writeheader(); w.writerow(profile)

    # runs CSV
    runs_csv = out_dir / "runs.csv"
    with open(runs_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader(); w.writerows(rows)

    # summary -- assignment_exact (no C1 until writer)
    consistency: dict = {"assignment_exact": True, "n_common": 0,
                         "n_java_only": 0, "n_py_only": 0,
                         "n_mismatches": 0, "first_mismatches": []}
    if py_payloads and java_payloads:
        consistency = _compare_consistency(py_payloads[0], java_payloads[0])
    _write_summary_md(out_dir, dataset_id, profile, py_payloads, java_payloads,
                      consistency, env, args)

    print(f"profile: {profile_csv}")
    print(f"runs:    {runs_csv}")
    print(f"summary: {out_dir / 'summary.md'}")
    print(f"assignment_exact: {consistency['assignment_exact']}  "
          f"(common={consistency['n_common']},"
          f" mismatches={consistency['n_mismatches']})")
    print(f"C1 exact: NOT YET ASSESSED (writer not implemented)", flush=True)


if __name__ == "__main__":
    main()
