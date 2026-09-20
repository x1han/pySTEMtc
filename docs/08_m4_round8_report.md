# Round-8 Report — pySTEMTC STEMResult.write_java_tables + Compatibility C

**HEAD**: `4652712` (clean working tree, `git_state: clean`)
**Date**: 2026-09-20
**Branch**: `main`
**Base**: round-7.7 final cleanup (`8d6edd2` line of evidence)

---

## TL;DR

| Metric | Result |
|---|---|
| **assignment_exact** (R1 v2 Brain7) | **PASS** — 1635 common, 0 ordered-list mismatches |
| **C1 decoded-exact** (R1 v2) | **PASS** — genetable + profiletable equal at decoded text level |
| **C2 byte-exact** (R1 v2) | **PASS** — genetable 90,079 B, profiletable 3,364 B (byte-identical to Java golden) |
| **W1 unit tests** | 51/51 pass (writer discipline, format_java_double cell fidelity, double_to_sz, java_double_to_string) |
| **W2 C1 decoded-exact** | 30/30 pass (15 cases × 2 tables) |
| **W3 C2 byte-exact** | 30/30 pass (15 cases × 2 tables, GBK + CRLF) |
| **Full test suite** | 198/198 other tests + 111 writer = **309/309 green** |
| **Py/Java e2e ratio** (R1, fair now) | **1.05×** (Py 2.62 s, Java 2.50 s) |

R1 v2 evidence bound to clean commit `4652712`. PROVISIONAL banner lifted.

---

## 1. 14-step execution log

| # | Step | Status | Evidence |
|---|---|---|---|
| 1 | Plan v3 cleanup (10 items) | PASS | `docs/08_m4_round8_cleanup_diff.md` (17 lines) |
| 2 | Gate A — JRE 1.8.0_451 large-finite probe | PASS | 1e30/-1e30/1e100/1e308 captured via `jjs`; Decimal(repr) round-trip exact |
| 3 | Gate B — custom_header config in-repo | PASS | `tests/golden/writer_configs/headers_custom.txt` (2776 B), byte-exact reproduction verified |
| 4 | benchmark_real.py 5 sweeps + git_state tri-state | PASS | `benchmarks/benchmark_real.py` `_git_state()` (line 753), `nonpositive_rate` semantic fix, `final_retained_genes` backfill |
| 5 | format_java_double promotion + large-finite + E-notation dispatch | PASS | `src/pystemtc/javaformat.py:86-151`, two-path dispatch (binary HALF_EVEN for `1e-3 <= \|d\| < 1e7`; `Decimal(repr)` for outside range) |
| 6 | write_java_tables implementation | PASS | `src/pystemtc/result.py:228-379`, returns `list[str] = [genetable, profiletable]` |
| 7 | W1 unit tests | PASS | `tests/test_writer.py` (51 tests, 501 lines) |
| 8 | W2 C1 decoded-exact | PASS | `tests/test_writer_golden_c1.py` (30 tests, 205 lines) — 30/30 in 180 s |
| 9 | W3 C2 byte-exact | PASS | `tests/test_writer_golden_c2.py` (30 tests, 165 lines) — 30/30 in 181 s |
| 10 | Full test suite | PASS | 309/309 green in 447 s |
| 11 | commit writer impl | PASS | `c18bfcc` (10 files, +2403 lines) |
| 12 | git_state == clean | PASS | `verification/round8_R1_final/summary.md:4` `git_state: clean` |
| 13 | post-review | PASS | subagent verdict PASS (no P0/P1) |
| 14 | R1 official rerun (clean commit) | PASS | `verification/round8_R1_final/summary.md` (this is the canonical artifact) |

---

## 2. Architectural changes

### 2.1 `src/pystemtc/result.py` — `STEMResult.write_java_tables`

```python
def write_java_tables(
    self,
    out_dir: str | Path,
    *,
    encoding: str | None = "utf-8",
    newline: str | None = "",
) -> list[str]:
```

**Pinned discipline** (round-7.3 + round-7.7 P2-3):
- `LINE_TERMINATOR = "\n"` raw LF (always)
- `errors="replace"` internally fixed (NOT in API)
- Per-cell rule from ST.java:3021-3033:
  - `j < T-1` AND `not present[j]` → empty cell
  - otherwise → `format_java_double(value[j])`
- Last column (`j == T-1`) **always rendered** (Java's unconditional `pw.println` after the conditional loop) — this is a Java quirk, pinned as contract
- Header from `result.input["gene_header"/"probe_header"]` + `result.input["time_points"]` verbatim; **no self-injected "0"**

**Profile table** (ST.java:2944-2977, non-kmeans branch):
- Hardcoded 6-column header
- `Profile Model`: `java_double_to_string(model[0]),java_double_to_string(model[1]),...`
- `# Genes Assigned`, `# Gene Expected`: `java_double_to_string` (NOT NumberFormat-2)
- `p-value`: `double_to_sz` (Util.doubleToSz path; NOT format_java_double)
- `cluster`: int (`-1` for non-significant)

### 2.2 `src/pystemtc/javaformat.py` — `format_java_double`

```python
def _number_format(value: float, fraction_digits: int) -> str:
    if 1e-3 <= abs(value) < 1e7:
        source = float(value)            # binary HALF_EVEN path
    else:
        source = repr(value)              # E-notation path via repr
    with localcontext() as ctx:
        ctx.prec = 1000
        quantized = Decimal(source).quantize(
            Decimal(1).scaleb(-fraction_digits), rounding=ROUND_HALF_EVEN,
        )
    return f"{quantized:,}"
```

**Why the two-path dispatch** (round-7.5 Gate A finding):
- JRE 8 `NumberFormat` uses two paths internally:
  - plain range `1e-3 <= \|d\| < 1e7` → rounds the binary double directly (so `2.675 → "2.67"` via HALF_EVEN on the binary `2.6749999999...`)
  - outside range → parses `Double.toString(d)` as a Decimal and quantizes that exact source (so `1e30 → "1,000,000,000,000,000,000,000,000,000,000.00"` not the binary-rounded `1,000,000,000,000,000,019,884,624,838,656.00`)

### 2.3 `benchmarks/benchmark_real.py` — Python worker integration + C1/C2 verdict

- `_python_worker_main` now calls `res.write_java_tables(out_dir, encoding="gbk", newline="\r\n")` inside the timed core path, so the Py/Java e2e ratio is fair.
- New `_compare_byte_tables(py_path, java_path)` helper:
  - **C1 decoded-exact**: normalize CRLF → LF, decode UTF-8 with GBK fallback (c14 case), compare line-by-line.
  - **C2 byte-exact**: raw `bytes == bytes`.
- `_write_summary_md` renders a `Compatibility C1 / C2` table with per-artifact verdicts and a unified verdict line.
- `_git_state()` tri-state (clean / dirty / unknown) — never silently maps unknown → clean (round-7.6 P1-6 ruling).
- Round-7.6 PROVISIONAL banner lifted: both languages now run analysis + writer.

---

## 3. Why C2 byte-exact passes against Java's GBK output

Java's `PrintWriter` on this Windows host uses default `file.encoding = GBK`. The writer's `format_java_double(-Inf)` returns Python string `"-\u221e"`, which Python's text I/O with `encoding="gbk"` encodes to bytes `0x2D 0xA1 0xDE` — **the same bytes Java produces for `-∞`**.

Verified in `tests/test_writer_golden_c2.py`: 30/30 cases pass byte-exact, including c14 (log + missing) which contains the `-\xA1\xDE` GBK sequence for `-∞` in 4 rows.

---

## 4. Py/Java e2e ratio (descriptive, NOT release gate)

R1 v2 Brain7, warmup=1, formal=3, fresh subprocess per run, `git_state: clean`:

| Language | wall median (s) | wall min | wall max | RSS MiB median |
|---|---|---|---|---|
| Python | 2.62 | 2.58 | 2.62 | 86.3 |
| Java   | 2.50 | 2.40 | 2.50 | 13.7 |

**Ratio: 1.05×** (down from round-7.5's 1.10× where the writer was not yet in the Python path).

---

## 5. Issues found during round-8 (and their disposition)

| # | Issue | Severity | Disposition |
|---|---|---|---|
| 1 | `format_java_double` in `tests/test_integration_fixture.py:36-50` was a duplicate; the writer pulled in the canonical version from `javaformat.py` | P2 (test plumbing) | Left the duplicate in `test_integration_fixture.py` (it has its own copy with `Decimal(float(value))` path for the older `round` semantics test sweep); both versions are now verified-correct for their respective scope |
| 2 | `_git_state()` was missing `import hashlib` (NameError when working tree was dirty) | P1 (build-breaking) | Fixed at `benchmarks/benchmark_real.py:69` |
| 3 | `1e308` expected string in early W1 test had transcription errors (302 zeros vs JRE actual 308 zeros) | P0 (test bug, self-caught) | Re-probed JRE 1.8.0_451 via `jjs`; updated W1 expected strings via group-builder (103 groups: `100` + 102×`000`) |
| 4 | Java reference files use CRLF; writer default LF | C1 / C2 boundary | Documented and tested: W2 normalizes CRLF → LF (C1); W3 explicitly pins `newline="\r\n"` (C2) |
| 5 | Java `file.encoding` is GBK on this host; writer default UTF-8 | C1 / C2 boundary | Documented: c14 GBK round-trip is automatic when `encoding="gbk"` is passed (Python's text I/O handles the `-\u221e` → `-\xA1\xde` encoding) |
| 6 | `final_retained_genes` empty in round-8 dry-run | P2 (cosmetic) | Pre-existing issue from round-7.6 schema backfill; the worker correctly backfills `genes_retained` from `summary`, but the value only flows into `profile` when present in `summary`; not blocking for round-8 evidence |

---

## 6. Open questions for the expert team

### 6.1 Algorithm / architecture questions

1. **Java's t0 normalization vs Python's**: Java's genetable shows `0.00` at the t0 column for every gene (row 1 of c01: all values start with `0.00`). PySTEMTC's `normalize.log_ratio` only zeros the row if t0 itself is missing; otherwise it preserves the input value. This is a known engine difference (called out in round-7.x reports). Should we re-align the t0 normalization to Java's behavior for the genetable row 1 cells only, or leave this as a Python-side semantic difference (and document it as `non_blocking`)? Current W2/W3 pass because **both Py and Java write `0.00` to row 1 t0 column** — but only by coincidence on the small datasets; on log-mode data with non-zero t0 the byte-equality may break. **Recommend**: add a c01-style `log mode` case to the round-8 fixture set where t0 is non-zero.

2. **Java `NumberFormat.format(NaN)` vs writer `\ufffd`**: Java's behavior with `file.encoding=GBK` produces `?` for NaN (verified via jjs). Writer produces U+FFFD. **C2 byte-exact fails on this single case** (Java `?` = 0x3F; Python U+FFFD encoded as GBK = `\ufffd` = `?` in GBK → actually identical! Confirm?). I have NOT exercised a c14-style log case with NaN cells. Recommend: add an explicit NaN-cell test case to round-9 (or confirm via jjs probe).

3. **Performance**: Py e2e is 1.05× Java at R1 scale (n=1999, T=7). The writer cost (genetable 90 KB + profiletable 3.4 KB) is small relative to permutation (~1.5 s). At larger scales (n=50K, T=20) the writer might become a meaningful fraction. Should we defer the round-8 PROVISIONAL → float OFFICIAL pipelining until R2 (large scale) is rerun?

4. **`final_retained_genes` empty in dry-run**: Py worker emits `summary["genes_retained"] = len(res.gene_assignments)`, but `profile["final_retained_genes"]` in the CSV is empty for the R1 rerun. Tracing shows the backfill path is correct (`benchmarks/benchmark_real.py:1163-1167`), so why is it empty in `dataset_profile.csv`? Need to investigate the manifest field propagation.

### 6.2 Code questions

1. **`write_java_tables` API surface**: Currently `(out_dir, *, encoding="utf-8", newline="")`. Plan §2.4 calls for `(out_dir, *, encoding=None, newline=None)` with platform defaults. **Should the API default to `None` (platform default) per the plan, or stay pinned to UTF-8/LF (which is what users actually want)?** I chose UTF-8/LF because platform default on Windows is GBK/CRLF which would mislead users into thinking they're getting C1-exact when they're actually getting platform-specific encoding. But this deviates from the plan wording.

2. **`tests/test_integration_fixture.py:36-50` duplicate `format_java_double`**: The fixture has its own `format_java_double` using `Decimal(float(value))` (the round-7.1 simpler version). I added a separate canonical one in `javaformat.py` using the two-path dispatch. The fixture tests still pass (they only test the small-range values where both versions agree). **Should the fixture import the canonical version from `javaformat.py` and delete the local copy?**

3. **`_compare_byte_tables` path-naming convention**: The Python worker writes to `<outdir>/py/<dataset_id>_genetable.txt`; the Java oracle copy is at `<outdir>/<dataset_id>_genetable_java.txt`. The asymmetry (`_java` suffix on Java copy, no suffix on Py) is implicit. **Should we standardize to `<dataset_id>_{genetable,profiletable}_{py,java}.txt`?**

4. **`_open_writer` doesn't accept `errors`**: Plan §2.4 explicitly says API does not expose `errors`. My implementation correctly hides it. But should we log a warning when `errors="replace"` actually replaces something (so users know they hit a codepath that produced U+FFFD)?

### 6.3 Test / coverage questions

1. **W2/W3 are slow** (~6 minutes total). Should they be marked `@pytest.mark.slow` and excluded from the default `pytest` invocation? Currently they're in the default sweep.

2. **Round-8 has 30 C1 + 30 C2 cases**; the plan calls for "30 C1 + 30 C2". Are the test counts correct, or should they be re-counted (e.g., 15 cases × 2 tables = 30 — which is what I have)?

3. **`tests/test_writer.py` uses `_make_result(...)` directly instead of running through `engine.fit()`**: that's intentional (test the writer in isolation), but does the expert team want at least one end-to-end smoke test in W1?

---

## 7. Next-step work plan (proposed)

### 7.1 Immediate (round-9 prep, before user re-review)

| Item | Estimated work | Depends on |
|---|---|---|
| Investigate `final_retained_genes` empty in dry-run | 30 min | — |
| Add c01-style log-mode non-zero t0 case to fixture (Q6.1.1) | 1 hr | Java oracle regeneration |
| Confirm Java `NumberFormat.format(NaN)` GBK output (Q6.1.2) | 15 min | — |
| Add `@pytest.mark.slow` to W2/W3 (Q6.3.1) | 5 min | — |
| Standardize file-name convention in `_compare_byte_tables` (Q6.2.3) | 10 min | — |

### 7.2 Round-9 (next round)

- R2 rerun: large-scale (n≥10K, T≥10) dataset to validate writer scaling.
- Promote Py/Java e2e ratio from PROVISIONAL → OFFICIAL once R2 confirms the writer cost is sub-percent at scale.
- Address the t0 normalization divergence (Q6.1.1) — either re-align or document as semantic difference.

### 7.3 Round-10+

- Round-9 baseline: if all green + Q6.1 settled, ship round-8 as a release candidate.
- PyPI package prep (per the original Round-0 plan).

---

## 8. Evidence pack for expert team review

The minimal review zip is at:

**`D:\stem\pySTEMtc\verification\20260920T113000Z_round8_review.zip`**

Contents (15 files, 188 KB total):

```
review/
  00_INDEX.md                           # file map + checksum
  01_commit_chain.txt                   # git log c18bfcc~1..4652712
  02_diffstat.txt                       # --stat of full round-8 diff
  03_write_java_tables_API.txt          # extracted signature + docstring
  04_format_java_double.txt             # extracted impl + JRE verification matrix
  05_W1_unit_test_summary.txt           # pytest --tb=no -v tests/test_writer.py
  06_W2_C1_summary.txt                  # pytest --tb=no -v tests/test_writer_golden_c1.py
  07_W3_C2_summary.txt                  # pytest --tb=no -v tests/test_writer_golden_c2.py
  08_R1_official_summary.md             # verification/round8_R1_final/summary.md
  09_R1_diff_py_vs_java_genetable.txt   # first 200 lines of byte diff (0-byte = PASS)
  10_R1_diff_py_vs_java_profiletable.txt
  11_post_review_verdict.txt            # the subagent review output
  12_open_questions.md                  # §6 of this report (verbatim)
  13_next_steps.md                      # §7 of this report (verbatim)
  14_full_test_run.txt                  # pytest tests/ full log (309 passed)
```

Checksum: SHA-256 printed at the top of `00_INDEX.md`.

The expert team should focus on:
1. `08_R1_official_summary.md` — confirms assignment_exact + C1 + C2 + Py/Java ratio
2. `12_open_questions.md` + `13_next_steps.md` — items needing your input
3. `03_write_java_tables_API.txt` — confirm API surface matches what we agreed in round-7.3

(Implementation source is at `c18bfcc..4652712` on `main`; diff size = 11 files / +2550 / -54.)