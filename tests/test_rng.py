"""JavaRandom vectors against tests/golden/java_rng/vectors.txt (DoD M1-1).

The vector file was exported from the real ``java.util.Random`` (JRE 8) via
``tools/gen_java_rng.js``.  The DOUBLE/INTB/INT groups are drawn sequentially
from one instance per seed, so replaying the same call order also pins the
stream interleaving.  The INTB bound (1000) is not recorded in the file.
"""

from pathlib import Path

import pytest

from pystemtc.rng import JavaRandom

VECTORS = Path(__file__).parent / "golden" / "java_rng" / "vectors.txt"
INTB_BOUND = 1000  # bound used by tools/gen_java_rng.js; not stored in vectors.txt


def _parse_vectors():
    seeds = []
    current = None
    for line in VECTORS.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        kind = parts[0]
        if kind == "SEED":
            current = {"seed": int(parts[1]), "double": [], "intb": [], "int": []}
            seeds.append(current)
        elif kind == "DOUBLE":
            current["double"].append(parts[2])
        elif kind == "INTB":
            current["intb"].append(int(parts[2]))
        elif kind == "INT":
            current["int"].append(int(parts[2]))
    return seeds


def _load_seed_vectors():
    return {
        entry["seed"]: {
            "double": [float(v) for v in entry["double"]],
            "intb": entry["intb"],
            "int": entry["int"],
        }
        for entry in _parse_vectors()
    }


@pytest.mark.parametrize("seed", [9873287, 3733246, 2211, 42])
def test_java_random_matches_golden_vectors(seed):
    vectors = _load_seed_vectors()[seed]
    rng = JavaRandom(seed)

    for i, expected in enumerate(vectors["double"]):
        got = rng.next_double()
        assert got == expected, f"seed {seed} DOUBLE {i}: {got!r} != {expected!r}"

    for i, expected in enumerate(vectors["intb"]):
        got = rng.next_int(INTB_BOUND)
        assert got == expected, f"seed {seed} INTB {i}: {got} != {expected}"

    for i, expected in enumerate(vectors["int"]):
        got = rng.next_int()
        assert got == expected, f"seed {seed} INT {i}: {got} != {expected}"
