"""Generate golden fixtures for PySTEMTC (M1+).

Produces, under the project's tests/golden/:
  java_configs/   - batch defaults files (parameter grid), based on D:/stem/defaults.txt
  data/           - synthetic time-course inputs (6 and 10 time points)
  java_reference/ - stem.jar -b outputs (profiletable/genetable per config) + stdout log
  java_rng/       - real java.util.Random vectors via JRE8 jjs (Nashorn)

Requires: JRE 8 at the path below (java + jjs). Re-run any time to regenerate.

``--fixtures c13_synth10_missing,c14_log_missing`` generates ONLY the named
configs (plus their data files) and batch-runs them from a scratch directory
(bare filenames -> correct output naming, ST.java:1268-1282). This leaves
every frozen artifact (c01-c12 configs, synth6/synth10, reference tables,
vectors) untouched. Whole-dir regeneration is reserved for an explicit full
run: frozen c09/c10/c11 configs carry the historical "STEMpy/..." Data_File
prefix that no longer resolves, so a whole-dir batch would skip them with a
caught FileNotFoundException (ST.java:1300-1311). Do NOT pass single config
FILES to -b: the output name is derived from the input path
(szcurrentDefaultFile, ST.java:2947/:2989) and the write silently fails.
"""
from pathlib import Path
import argparse
import subprocess
import sys

import numpy as np

HERE = Path(__file__).resolve().parent          # <project>/tools
STEMPY = HERE.parent                            # project root (D:/stem/pySTEMtc)
ROOT = STEMPY.parent                            # D:/stem (stem.jar, g27_1.txt, defaults.txt)
GOLD = STEMPY / "tests" / "golden"
CFG = GOLD / "java_configs"
REF = GOLD / "java_reference"
DATA = GOLD / "data"
RNGDIR = GOLD / "java_rng"
JJS = Path(r"C:\Program Files\Java\jre1.8.0_451\bin\jjs.exe")

S6_COLS = ["0h", "1h", "2h", "4h", "8h", "24h"]
S10_COLS = ["0h", "1h", "2h", "4h", "8h", "12h", "18h", "24h", "36h", "48h"]


def make_config(overrides: dict) -> str:
    lines = (ROOT / "defaults.txt").read_text(encoding="utf-8").splitlines()
    out, seen = [], set()
    for line in lines:
        if not line.strip() or line.startswith("#"):
            out.append(line)
            continue
        head, _, value = line.partition("\t")
        key = head.split("[", 1)[0].strip()
        if key in overrides:
            out.append(f"{head}\t{overrides[key]}")
            seen.add(key)
        else:
            out.append(line)
    missing = set(overrides) - seen
    if missing:
        raise KeyError(f"keys not found in defaults template: {missing}")
    return "\n".join(out) + "\n"


def synth(path: Path, n_spots: int, time_cols, seed: int, dup_every=10, miss_rate=0.08):
    rng = np.random.default_rng(seed)
    vals = rng.normal(0.0, 1.0, size=(n_spots, len(time_cols))).round(3)
    mask = rng.random(size=vals.shape) < miss_rate
    genes = []
    for i in range(n_spots):
        if i % dup_every == 1 and genes:
            genes.append(genes[-1])
        else:
            genes.append(f"GENE_{i:04d}")
    with open(path, "w", newline="\n") as f:
        f.write("SPOT\tGene Symbol\t" + "\t".join(time_cols) + "\n")
        for i in range(n_spots):
            cells = [str(i + 1), genes[i]]
            for j in range(len(time_cols)):
                cells.append("" if mask[i, j] else f"{vals[i, j]:.3f}")
            f.write("\t".join(cells) + "\n")


def synth_missing(path: Path, n_spots: int, time_cols, seed: int, dup_every=10):
    """synth10m (c13): N(0,1) values; deterministic non-t0 missing pattern.

    Row i%3==2 blanks 0-based time index (i%9)+1 (columns 1..9 rotating);
    t0 is never blank. filterMissing (DataSetCore.java:574-603) with
    Maximum_Number_of_Missing_Values=1 keeps every row; rows i≡11 (mod 30)
    are dup secondaries whose missing cell is median-merged away (Math.max,
    :716-723), the rest stay gene-level missing so the on-the-fly legality
    check (:1223) and masked correlation are exercised (spec 03 §1.9).
    """
    rng = np.random.default_rng(seed)
    vals = rng.normal(0.0, 1.0, size=(n_spots, len(time_cols))).round(3)
    genes = []
    for i in range(n_spots):
        if i % dup_every == 1 and genes:
            genes.append(genes[-1])
        else:
            genes.append(f"GENE_{i:04d}")
    with open(path, "w", newline="\n") as f:
        f.write("SPOT\tGene Symbol\t" + "\t".join(time_cols) + "\n")
        for i in range(n_spots):
            cells = [str(i + 1), genes[i]]
            blank_col = (i % 9) + 1 if i % 3 == 2 else None
            for j in range(len(time_cols)):
                cells.append("" if j == blank_col else f"{vals[i, j]:.3f}")
            f.write("\t".join(cells) + "\n")


def synth_pairs(path: Path, time_cols, seed=20260921, n_pairs=100, n_singles=40):
    """synth6d (c14): all-positive values; defective SECONDARY dup spots.

    Row layout: 2*100 pair rows (row 2i = primary, row 2i+1 = secondary)
    then n_singles single-spot genes. The defective cell sits at 0-based
    time index 2 on the SECONDARY spot only: genespottimedata stores the
    primary by reference so the merge median overwrites it
    (DataSetCore.java:675-679 vs :717-723, spec 03 §1.2 aliasing), while the
    secondary keeps pre-merge log-ratios — only a defective secondary (or a
    single-spot gene) can push -Inf/NaN into the log-mode re-reference
    median (STEM_DataSet.java:1221-1275, spec 03 §1.7 quirk 3).

    Groups: G1_ pairs 0-49 blank at index 2 -> log(0) = -Inf -> vals get
    +Inf -> median +Inf -> sqrt(NaN) -> dcorr NaN skipped (:1349); G2_ pairs
    50-99 hold -0.7 -> loader marks pma=0 and keeps the negative data
    (:513-521) -> log(negative) = NaN enters the median directly; S_ singles
    (every 3rd) blank at a non-t0 index -> the -Inf route with no merge.
    """
    rng = np.random.default_rng(seed)
    ncols = len(time_cols)
    rows: list[tuple[str, list]] = []
    for i in range(n_pairs):
        gene = f"G1_{i:04d}" if i < 50 else f"G2_{i:04d}"
        primary = [round(float(rng.uniform(0.5, 4.0)), 3) for _ in range(ncols)]
        secondary = [round(float(rng.uniform(0.5, 4.0)), 3) for _ in range(ncols)]
        if i < 50:
            secondary[2] = None
        else:
            secondary[2] = -0.7
        rows.append((gene, primary))
        rows.append((gene, secondary))
    for j in range(n_singles):
        vals = [round(float(rng.uniform(0.5, 4.0)), 3) for _ in range(ncols)]
        if j % 3 == 0:
            vals[(j % 4) + 2] = None
        rows.append((f"S_{j:04d}", vals))
    with open(path, "w", newline="\n") as f:
        f.write("SPOT\tGene Symbol\t" + "\t".join(time_cols) + "\n")
        for k, (gene, vals) in enumerate(rows):
            cells = [str(k + 1), gene]
            for v in vals:
                cells.append("" if v is None else f"{v:.3f}")
            f.write("\t".join(cells) + "\n")


def main(fixtures: str | None = None):
    selected = None if fixtures is None else set(fixtures.split(","))

    # Frozen configs must never be regenerated by name: their Data_File
    # prefixes are generation-time evidence (HANDOFF D8). Full runs rewrite
    # them only via the explicit documented whole-dir path.
    FROZEN = {
        "c01_guillemin_core", "c02_t0fixed", "c03_lognorm", "c04_add0",
        "c05_fdr", "c06_nocorr", "c07_sameperiod", "c08_norepeat",
        "c09_synth6", "c10_synth6_allperms", "c11_synth10", "c12_percentile",
    }
    if selected is not None and selected & FROZEN:
        sys.exit(
            f"--fixtures refuses frozen configs (evidence, see HANDOFF D8): "
            f"{sorted(selected & FROZEN)}"
        )

    for d in (CFG, REF, DATA, RNGDIR):
        d.mkdir(parents=True, exist_ok=True)

    guillemin = dict(
        Data_File="g27_1.txt",
        Spot_IDs_included_in_the_data_file="true",
        **{"Repeat_Data_Files(comma delimited list)": "g27_2.txt"},
        Minimum_Absolute_Log_Ratio_Expression="0.8",
        **{"Change_should_be_based_on": "Difference From 0"},
    )
    # Regenerated configs must point at data/ through the CURRENT project dir
    # name (resolved from D:/stem); frozen c09/c10/c11 keep their historical
    # "STEMpy/..." prefix on disk and rely on the test resolver's fallback.
    synth6 = dict(
        Data_File=f"{STEMPY.name}/tests/golden/data/synth6.txt",
        Spot_IDs_included_in_the_data_file="true",
        **{"Repeat_Data_Files(comma delimited list)": ""},
        Minimum_Absolute_Log_Ratio_Expression="0.5",
    )
    synth10 = dict(
        Data_File=f"{STEMPY.name}/tests/golden/data/synth10.txt",
        Spot_IDs_included_in_the_data_file="true",
        **{"Repeat_Data_Files(comma delimited list)": ""},
        Minimum_Absolute_Log_Ratio_Expression="0.5",
    )
    # c13/c14: branch-targeted missing fixtures, spec 03 §1.9 (round-5 N2).
    synth10m = dict(
        Data_File=f"{STEMPY.name}/tests/golden/data/synth10m.txt",
        Spot_IDs_included_in_the_data_file="true",
        **{"Repeat_Data_Files(comma delimited list)": ""},
        Minimum_Absolute_Log_Ratio_Expression="0.5",
        Maximum_Number_of_Missing_Values="1",
    )
    log_missing = dict(
        Data_File=f"{STEMPY.name}/tests/golden/data/synth6d.txt",
        Spot_IDs_included_in_the_data_file="true",
        **{"Repeat_Data_Files(comma delimited list)": ""},
        Normalize_Data="Log normalize data",
        Maximum_Number_of_Missing_Values="1",
        Permutation_Test_Should_Permute_Time_Point_0="true",
        Minimum_Absolute_Log_Ratio_Expression="0.5",
        **{"Change_should_be_based_on": "Maximum-Minimum"},
    )
    variants = {
        "c01_guillemin_core": {},
        "c02_t0fixed": {"Permutation_Test_Should_Permute_Time_Point_0": "false"},
        "c03_lognorm": {"Normalize_Data": "Log normalize data"},
        "c04_add0": {"Normalize_Data": "No normalization/add 0"},
        "c05_fdr": {"Correction_Method": "False Discovery Rate"},
        "c06_nocorr": {"Correction_Method": "None"},
        "c07_sameperiod": {"Repeat_Data_is_from": "The same time period"},
        "c08_norepeat": {"Repeat_Data_Files(comma delimited list)": ""},
        "c09_synth6": synth6,
        "c10_synth6_allperms": {**synth6, "Number_of_Permutations_per_Gene": "0"},
        "c11_synth10": synth10,
        "c12_percentile": {"Clustering_Minimum_Correlation_Percentile": "0.5"},
        "c13_synth10_missing": synth10m,
        "c14_log_missing": log_missing,
    }

    for name, extra in variants.items():
        if selected is not None and name not in selected:
            continue
        if name in ("c09_synth6", "c10_synth6_allperms"):
            base = dict(synth6)
        elif name == "c11_synth10":
            base = dict(synth10)
        elif name == "c13_synth10_missing":
            base = dict(synth10m)
        elif name == "c14_log_missing":
            base = dict(log_missing)
        else:
            base = dict(guillemin)
        base.update(extra)
        (CFG / f"{name}.txt").write_text(make_config(base), encoding="utf-8")

    if selected is None:
        synth(DATA / "synth6.txt", 300, S6_COLS, seed=20260919)
        synth(DATA / "synth10.txt", 250, S10_COLS, seed=20260920)
    if selected is None or "c13_synth10_missing" in selected:
        synth_missing(DATA / "synth10m.txt", 300, S10_COLS, seed=20260921)
    if selected is None or "c14_log_missing" in selected:
        synth_pairs(DATA / "synth6d.txt", S6_COLS)

    if selected is not None:
        # Dir-mode batch over a scratch copy holding only the new configs
        # (ST.java:1268-1282): bare filenames keep the output naming correct.
        # A single-FILE input embeds the whole input path into the output
        # name (szcurrentDefaultFile, :1289/:1294 -> :2947/:2989) and the
        # write fails silently, so do NOT pass config files directly.
        # Frozen reference tables for c01-c12 are never touched.
        import shutil

        scratch = ROOT / ".batch_scratch"
        shutil.rmtree(scratch, ignore_errors=True)
        scratch.mkdir()
        try:
            for name in sorted(selected):
                (scratch / f"{name}.txt").write_text(
                    (CFG / f"{name}.txt").read_text(encoding="utf-8"), encoding="utf-8"
                )
            proc = subprocess.run(
                ["java", "-mx1024M", "-jar", "stem.jar", "-b",
                 scratch.name, str(REF.relative_to(ROOT))],
                cwd=ROOT, capture_output=True, text=True, timeout=600,
                encoding="utf-8", errors="replace",
            )
            if proc.returncode != 0:
                sys.exit(f"stem.jar batch failed:\n{proc.stderr[-2000:]}")
            for name in sorted(selected):
                for kind in ("profiletable", "genetable"):
                    out = REF / f"{name}_{kind}.txt"
                    if not out.exists():
                        sys.exit(f"stem.jar batch produced no {out.name}")
                    print(f"{name}_{kind}: ok")
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        return

    # Real java.util.Random vectors via Nashorn (no javac needed on a JRE-only box).
    js = HERE / "gen_java_rng.js"
    proc = subprocess.run([str(JJS), str(js)], capture_output=True, text=True,
                          timeout=120, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        sys.exit(f"jjs failed: {proc.stderr}")
    (RNGDIR / "vectors.txt").write_text(proc.stdout, encoding="utf-8")

    # Golden batch run: one invocation processes every config in java_configs/.
    proc = subprocess.run(
        ["java", "-mx1024M", "-jar", "stem.jar", "-b",
         str(CFG.relative_to(ROOT)), str(REF.relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace",
    )
    (REF / "_batch_stdout.log").write_text(proc.stdout + "\n--- stderr ---\n" + proc.stderr,
                                           encoding="utf-8")
    if proc.returncode != 0:
        sys.exit(f"stem.jar batch failed (see {REF / '_batch_stdout.log'}):\n{proc.stderr[-2000:]}")

    tables = sorted(p.name for p in REF.glob("*.txt"))
    print(f"configs: {len(list(CFG.glob('*.txt')))}")
    print(f"outputs: {len(tables)}")
    for name in tables:
        print(" ", name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixtures", default=None,
                    help="comma list of config names; generate only these "
                         "(single-config batch per fixture). Omit for a full run.")
    args = ap.parse_args()
    main(args.fixtures)
