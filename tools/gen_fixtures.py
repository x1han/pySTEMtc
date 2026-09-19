"""Generate golden fixtures for PySTEMTC (M1+).

Produces, under the project's tests/golden/:
  java_configs/   - batch defaults files (parameter grid), based on D:/stem/defaults.txt
  data/           - synthetic time-course inputs (6 and 10 time points)
  java_reference/ - stem.jar -b outputs (profiletable/genetable per config) + stdout log
  java_rng/       - real java.util.Random vectors via JRE8 jjs (Nashorn)

Requires: JRE 8 at the path below (java + jjs). Re-run any time to regenerate.
"""
from pathlib import Path
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


def main():
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
    }
    for name, extra in variants.items():
        if name in ("c09_synth6", "c10_synth6_allperms"):
            base = dict(synth6)
        elif name == "c11_synth10":
            base = dict(synth10)
        else:
            base = dict(guillemin)
        base.update(extra)
        (CFG / f"{name}.txt").write_text(make_config(base), encoding="utf-8")

    synth(DATA / "synth6.txt", 300, ["0h", "1h", "2h", "4h", "8h", "24h"], seed=20260919)
    synth(DATA / "synth10.txt", 250, ["0h", "1h", "2h", "4h", "8h", "12h", "18h", "24h", "36h", "48h"], seed=20260920)

    # Real java.util.Random vectors via Nashorn (no javac needed on a JRE-only box).
    js = HERE / "gen_java_rng.js"
    proc = subprocess.run([str(JJS), str(js)], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        sys.exit(f"jjs failed: {proc.stderr}")
    (RNGDIR / "vectors.txt").write_text(proc.stdout, encoding="utf-8")

    # Golden batch run: one invocation processes every config in java_configs/.
    proc = subprocess.run(
        ["java", "-mx1024M", "-jar", "stem.jar", "-b",
         str(CFG.relative_to(ROOT)), str(REF.relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, timeout=600,
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
    main()
