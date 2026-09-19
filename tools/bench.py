"""M3 performance benchmarks (round-5 ruling N3: measure only, do not optimize).

Runs the full engine pipeline on three synthetic scales and records wall
time and peak process RSS. Deterministic seeds; no missing cells (clean
path upper bound); 50 permutations; default 50-model-profile grid.

Peak RSS comes from the OS (Psapi GetProcessMemoryInfo -> PeakWorkingSetSize
via ctypes), so no sampling loop and no third-party dependency; it is the
whole Python process peak, including numpy/pandas import overhead.

Usage: python tools/bench.py [--sizes 300x6,3000x10,10000x10] [--seed 20260919]
Results print incrementally as CSV to stdout after each scale completes.
"""
from __future__ import annotations

import argparse
import ctypes
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
import sys

sys.path.insert(0, str(_HERE.parent / "src"))

from pystemtc.engine import STEM  # noqa: E402


def _peak_rss_bytes() -> int:
    """Peak working set of the current process, in bytes (Windows Psapi)."""

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_uint32),
            ("PageFaultCount", ctypes.c_uint32),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    psapi = ctypes.WinDLL("Psapi.dll")
    kernel32 = ctypes.WinDLL("kernel32.dll")
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
        ctypes.c_uint32,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    handle = kernel32.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        raise OSError("GetProcessMemoryInfo failed")
    return int(counters.PeakWorkingSetSize)


def write_synth(path: Path, n_spots: int, n_cols: int, seed: int) -> None:
    """Same layout as gen_fixtures.synth (dup_every=10, no missing cells)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    vals = rng.normal(0.0, 1.0, size=(n_spots, n_cols)).round(3)
    genes = []
    for i in range(n_spots):
        if i % 10 == 1 and genes:
            genes.append(genes[-1])
        else:
            genes.append(f"GENE_{i:06d}")
    cols = [f"t{j}" for j in range(n_cols)]
    with open(path, "w", newline="\n") as f:
        f.write("SPOT\tGene Symbol\t" + "\t".join(cols) + "\n")
        for i in range(n_spots):
            cells = [str(i + 1), genes[i]] + [f"{vals[i, j]:.3f}" for j in range(n_cols)]
            f.write("\t".join(cells) + "\n")


def run_scale(n_spots: int, n_cols: int, seed: int, tmp: Path) -> dict:
    data = tmp / f"bench_{n_spots}x{n_cols}.txt"
    write_synth(data, n_spots, n_cols, seed)
    engine = STEM(
        normalize="normalize",
        max_unit_change=2,
        max_model_profiles=50,
        max_correlation=1.0,
        candidate_cap=1000000,
        n_permutations=50,
        permute_t0=True,
        alpha=0.05,
        correction="bonferroni",
        cluster_min_correlation=0.7,
        cluster_corr_percentile=0.0,
        max_missing=0,
        min_abs_expr=0.5,
        change_rule="max_minus_min",
        spot_included=True,
    )
    t0 = time.perf_counter()
    result = engine.fit(data)
    wall = time.perf_counter() - t0
    rss = _peak_rss_bytes()
    data.unlink()
    n_genes = len(result.gene_assignments)
    n_profiles = len(result.profiles)
    return {
        "spots": n_spots,
        "T": n_cols,
        "genes": n_genes,
        "profiles": n_profiles,
        "wall_s": round(wall, 1),
        "peak_rss_mib": round(rss / 2**20, 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sizes", default="300x6,3000x10,10000x10",
                    help="comma list of SPOTSxT (default three N3 scales)")
    ap.add_argument("--seed", type=int, default=20260919)
    args = ap.parse_args()

    tmp = Path(_HERE.parent / "build")
    tmp.mkdir(exist_ok=True)

    print("spots,T,genes,profiles,wall_s,peak_rss_mib", flush=True)
    for spec in args.sizes.split(","):
        n_spots, n_cols = (int(x) for x in spec.lower().split("x"))
        row = run_scale(n_spots, n_cols, args.seed, tmp)
        print(f"{row['spots']},{row['T']},{row['genes']},{row['profiles']},"
              f"{row['wall_s']},{row['peak_rss_mib']}", flush=True)


if __name__ == "__main__":
    main()
