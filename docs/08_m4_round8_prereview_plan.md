# Round-8 Writer Pre-Review Plan — `write_java_tables` + Compatibility C 落地

> 日期：2026-09-20
> 类型：Medium light-rip pre-work plan（提交给 reviewer subagent 审查；非 live code edit）
> 治理上下文：Round-7.7 CLOSED（user 团裁决 2026-09-20）；Round-7.8 DO NOT CREATE；Round-8 = Compatibility C / writer round
> spec 锚点：`docs/03_v1_implementation_spec.md §1.10`（round-7.3 frozen contract sweep；round-7.6 spec §1.10 文案最终化）
> 本 plan 唯一目标：让 reviewer 回答"**这份 plan 有没有遗漏 Java 输出语义？**"——而不是重新理解整个项目。

---

## 1. Scope（已冻结）

```text
A. 必须清扫（5 项 P2/P3 + 1 项 working tree 清理）：
   - benchmark_real.py docstring 3 处（benchmark_real.py:38, 125, 127）
   - determinism key-set 重写（benchmark_real.py:1060-1086）
   - final_retained_genes 回填（写 dataset_profile.csv 之前）
   - summary 标题切换 writer 接入前后状态（benchmark_real.py:920）
   - git_commit / **git_state** 字段（user 团 round-7.7 P2-3：改名为 `git_state`，避免与布尔混淆；profile 加 `git_state` + 可选 `git_diff_sha256`）
   - working tree 真实清理（git status --porcelain → keep+track / delete / ignore → `git_state="clean"`）

B. Writer 实现：
   - format_java_double 晋升到 src/pystemtc/javaformat.py（从 tests/test_integration_fixture.py:36-58）
   - STEMResult.write_java_tables(output_dir, prefix=None, encoding=None, newline=None)
   - genetable（per-cell: present=False + 非末列 → ""；末列无条件 format_java_double）
   - profiletable（**6-column** formatter matrix；user 团 round-7.7 P1-4 修正）

C. Verification 4 层：
   - W1: writer unit behavior（formatting / header / prefix / missing / tie）
   - W2: c01-c14 fixture C1 decoded exact + custom_header
   - W3: canonical Windows JRE8 oracle C2 byte exact（GBK + CRLF + errors=replace）
   - W4: R1 v2 clean-commit 重跑（Python fit+write vs Java analyze+write）→ assignment_exact + C1 + 等工作量 Py/Java e2e
```

### 1.1 不要做（user 团明确否决）

```
❌ benchmark_real.py 拆模块（dataclass / _profile_dataset / _spawn_workers / _compare）
❌ dict → dataclass 架构重构
❌ dataio.py 新增 gene_keys 公共 helper
❌ repository-wide EOL policy 重构（.gitattributes + eol=lf 全局）→ 会破坏 tests/golden/java_reference/** 字节 oracle
❌ effective_missing_rate 实现（不是 writer 职责，也不是 V1.0 门禁）
❌ R2 (repeats) / R3 (missing/high-T) 真实数据 benchmark
❌ 任何性能优化
```

### 1.2 byte oracle 资产保护

`tests/golden/java_reference/**` 全部保持 `-text` 保护——不要让任何格式化工具、Git 属性或编辑器批量改行尾。Round-8 不引入 `.gitattributes`。

---

## 2. Frozen Java Writer Behavior（spec §1.10）

### 2.1 Genetable（round-7.3 frozen）

**Header 行**（`ST.java` batch genetable header）：

```text
gene_header        ← result.input["gene_header"]（dataset gene_header 字段）
probe_header       ← result.input["probe_header"]（dataset probe_header 字段；非 SPOT 形式）
Profile            ← 字面字符串 "Profile"
time_points        ← result.input["time_points"]（**完整 sample_labels**，含 t0 标识；不是 j=1..T-1）
```

**关键合同（user 团 round-7.7 P1-1 修正）**：

```text
c01 oracle header:
Gene Symbol\tSPOT\tProfile\t0h\t0.5h\t3h\t6h\t12h

c04 add0 oracle header:
Gene Symbol\tSPOT\tProfile\t0\t0h\t0.5h\t3h\t6h\t12h

c14 oracle header:
Gene Symbol\tSPOT\tProfile\t0h\t1h\t2h\t4h\t8h\t24h
```

**writer 绝不能再次自行注入字面 `"0"` 列**——只有 `none_add0` 路径的数据模型本身已经把 `"0"` 注入 `sample_labels`/`time_points` 时才出现 `0`。

```python
header = [
    result.input["gene_header"],
    result.input["probe_header"],
    "Profile",
    *result.input["time_points"],   # 完整 sample_labels；含或不含 t0 由 dataset 决定
]
```

**每个 data cell**（genetable 行，`ST.java:3021-3033`）：

```python
if j < T - 1 and not present[j]:       # 非末列 + present=False
    cell = ""                            # 空字符串（不是 "0"、不是 "null"）
else:                                    # 末列无条件 OR present=True
    cell = format_java_double(values[j])  # format_java_double（ENGLISH, 2 decimals, HALF_EVEN, 千分位, NaN→U+FFFD, ±Inf→±∞, -0.00 保持）
```

**Profile 列**（每行的第 3 列）：

```python
profile_cell = ";".join(str(p) for p in profile_ids)   # tie profile 按 list 顺序直接 join；**禁止 writer 重新 sort**
```

**行分隔符**：`\t`（Tab 分隔，与 Java batch 命名一致）
**文件后缀**：`_genetable.txt`
**Encoding**：`encoding` 参数（默认平台默认；C1 解码后比较必须使用同一 target encoding + replacement policy——见 §6.1）
**Newline**：`newline` 参数（默认平台默认；C1 解码后比较不受 newline 影响——纯字节差异在解码后被吸收；C2 才比较 byte 序列）

### 2.2 Profiletable（round-7.3 frozen）

**6 列**，每列独立 formatter（**不能为了"统一代码"全部走 `format_java_double`**）。user 团 round-7.7 P1-4 修正：plan 之前错写 5 列，实际是 6 列。

**Profiletable header 硬编码**（来自 `tests/golden/java_reference/c01_guillemin_core_profiletable.txt` 第 1 行实测）：

```text
Profile ID
Profile Model
Cluster (-1 non-significant)
# Genes Assigned
# Gene Expected
p-value
```

```python
PROFILETABLE_HEADER = [
    "Profile ID",
    "Profile Model",
    "Cluster (-1 non-significant)",
    "# Genes Assigned",
    "# Gene Expected",
    "p-value",
]
```

| 列 | Formatter | 来源 |
|---|---|---|
| Profile ID | `str(int(profile_id))` | 整数化（如 `3`，不是 `"3.0"`）|
| Profile Model | `",".join(java_double_to_string(p) for p in profile_models)` | Java `Double.toString`；T 个双精度的逗号分隔字符串 |
| Cluster | `str(int(cluster_id))` | 整数化（cluster_id，非显著 profile = `-1`）|
| # Genes Assigned | `java_double_to_string(count)` | Java `Double.toString`（分数值允许）|
| # Gene Expected | `java_double_to_string(expected)` | Java `Double.toString` |
| p-value | `double_to_sz(p)` | `Util.doubleToSz`（含 0.995 阈值循环 + E-notation 分支）|

**行分隔符**：`\t`（Tab 分隔）
**文件后缀**：`_profiletable.txt`

**行序冻结**（user 团 round-7.7 P2-4）：

```text
profiletable：按 self.profiles 现有顺序输出，禁止 writer 排序
genetable：按 self.gene_assignments 现有顺序输出，禁止 writer 排序

Compatibility A 已经负责上游顺序；writer 只负责忠实序列化。
```

### 2.3 Prefix 规则（spec §1.10 frozen）

```python
result.write_java_tables(output_dir, prefix=None)

# 默认行为：
if prefix is None and result.input["form"] == "path":
    prefix = Path(result.input["data_file"]).stem           # 自动从 data_file stem 推导（便利）
elif prefix is None and result.input["form"] == "dataframe":
    raise ValueError(                                        # 必须显式 prefix
        "write_java_tables: prefix required for DataFrame-built results; "
        "pass prefix= to specify the output basename."
    )

# CLI 调用（config_path → prefix）：
prefix = config_path.stem                                    # 与 Java batch <defaults文件名>_genetable.txt 一致
```

**C 验收**：C1/C2 比较的是**文件内容**，文件名只在显式 `prefix=` 或 CLI config 模式才参与 Java batch 命名一致。

### 2.4 Encoding / Newline（C1 vs C2 分级）

```python
result.write_java_tables(output_dir, encoding=None, newline=None)

# 默认：跟随平台默认（镜像 Java 行为）
# C1 decoded exact — 按各 artifact 实际编码解码后做字段级比较（见 §6 P2 修正）
# C2 byte exact — 必须显式 pin encoding + newline（推荐 GBK + CRLF 对齐 Windows JRE8 oracle）

# 字节写入（user 团 round-7.7 P1-3 修正，避免 \r\r\n 双重转换）：
LINE_TERMINATOR = "\n"  # 永远写 LF；newline 参数只让 Python text I/O 层负责转换

with open(
    path,
    "w",
    encoding=resolved_encoding,
    errors="replace",                  # 内部固定，user 团 P2-3：API 不暴露
    newline=resolved_newline,
) as f:
    for row in rows:
        f.write(row + "\n")             # 永远 +LF；不写 +newline_str
```

**为什么不能再 `f.write(line + newline_str)`**：Python text I/O 在 `newline="\r\n"` 模式下会把写入字符串里的 `\n` 自动转换为 `\r\n`——再叠加手写的 `newline_str="\r\n"` 会得到 `\r\r\n`。**只选一种机制**：让 text layer 负责 newline 转换，写入永远只用 `"\n"`。

**W1 必须新增断言**：

```text
test_no_double_crlf_under_explicit_newline:
  write_java_tables(output_dir, prefix="x", encoding="gbk", newline="\r\n")
  → bytes 内容里 0 处 b"\r\r\n"
```

**NaN / ±Inf 在 GBK 下的字节写入**（user 团 round-7.7 P1-2 修正）：

实测 `python -c "s.encode('gbk', errors='replace')"`：

| 字符 | Unicode | GBK bytes（实测） | 备注 |
|---|---|---|---|
| `∞` (U+221E) | 圆 | `A1 DE` | **GBK 可编码**——`errors="replace"` 不触发 |
| `-∞` | `-` + U+221E | `2D A1 DE` | 同上 |
| `+∞` | `+` + U+221E | `2B A1 DE` | 同上 |
| U+FFFD | 替换字符 | `3F` | **GBK 不可编码**——`errors="replace"` → `?` |

**关键事实（user 团实测）**：

- `±Inf` 经 `format_java_double` / `double_to_sz` 后渲染为 `±∞`（U+221E 字符），**GBK 可编码**——`errors="replace"` 不触发。
- **只有真正落到 U+FFFD（即 NaN 渲染路径）的字符**才会被 GBK `errors="replace"` 替换为 `?`。
- **c14 oracle 实测**（`grep -c "3F" tests/golden/java_reference/c14_log_missing_genetable.txt`）：`0 occurrences`；c14 全文 `-∞` 全部是 `2D A1 DE`（GBK 真编码字节）——**c14 不能作为 `U+FFFD→?` 的 byte-oracle 证据**，因为 c14 没有 NaN 落盘。

**JRE8 characterization 证据**（NaN→U+FFFD→GBK `?` 的唯一证据）：

```text
JRE8 NumberFormat.format(Double.NaN) → "\ufffd"
U+FFFD.encode("gbk", errors="replace") → "?" (0x3F)
```

W1 必须新增**专门的**：

```text
test_format_java_double_nan_encodes_to_ufffd_then_question_mark_under_gbk_errors_replace
```

测试——不依赖 c14 oracle；靠 U+FFFD 字符本身的 GBK encode 行为。

> 删去原 plan 错误陈述："c14 oracle 是 GBK `errors="replace"` 行为，而不是真 GBK 编码后的字节"——这是错的，c14 全是 GBK 真编码字节。

---

## 3. Files to Change

| 文件 | 动作 | 说明 |
|---|---|---|
| `src/pystemtc/javaformat.py` | **追加** `format_java_double()`（从 tests/test_integration_fixture.py:36-58 晋升） | 120 行现有文件 + 24 行新增 |
| `src/pystemtc/result.py` | **追加** `STEMResult.write_java_tables()`（`result.py:132` 后） | 新增方法，不动现有 schema v2 |
| `tests/test_integration_fixture.py` | **修改** `format_java_double` import 路径指向 `pystemtc.javaformat.format_java_double` | 行为不变，测试通过 |
| `tests/test_writer.py`（**新建**） | W1 unit tests | formatting / header / prefix / missing / tie / encoding / newline / DataFrame ValueError |
| `tests/test_writer_c1.py`（**新建**） | W2 c01-c14 C1 fixture + custom_header | 14 cases × 2 tables + custom_header × 2 tables = **30 cases**（user 团 round-7.7 final cleanup）|
| `tests/test_writer_c2.py`（**新建**） | W3 canonical byte exact | writer 调用：`encoding="gbk", newline="\r\n"`（API 不暴露 `errors=`；writer 内部固定）；与 Java oracle 字节比对 |
| `benchmarks/benchmark_real.py` | 5 项清扫 + **`git_state`** 字段 + working tree 清理 | §5 details |
| `docs/08_m4_round8_report.md`（**新建**） | round-8 实施报告（post-review 后） | 含 W1-W4 evidence package |
| `docs/03_v1_implementation_spec.md §1.10` | **小修**：补充 `git_state="clean"` 作为 official baseline 入口条件（user 团裁决 + round-7.7 P2-3 改名） | 仅 1-2 行 |

**修改后预估 diffstat**（不含 verification artifacts）：

```
src/pystemtc/javaformat.py             |  +24
src/pystemtc/result.py                 | +150 (write_java_tables method)
tests/test_integration_fixture.py      |   ±2 (import path)
tests/test_writer.py                   | +200 (new file, W1)
tests/test_writer_c1.py                | +150 (new file, W2)
tests/test_writer_c2.py                |  +80 (new file, W3)
benchmarks/benchmark_real.py           |  +30 / -20 (5 sweep + git_state)
docs/03_v1_implementation_spec.md      |   +3 (git_state gate)
docs/08_m4_round8_report.md            | +300 (new file, post-review)
9 files changed, ~+900 / -25
```

---

## 4. Exact Implementation Mapping（关键 reviewer 焦点）

### 4.1 `format_java_double` 晋升

| Java 源 | 行号 | PySTEMTC 实现 |
|---|---|---|
| `ST.java` NumberFormat | `ST.java:3017-3019` | `src/pystemtc/javaformat.py::format_java_double`（**新增**）|
| JDK8 DecimalFormat `Locale.ENGLISH` | JDK docs | 显式 `Decimal(float(value))` + ENGLISH 量化（HALF_EVEN）|
| HALF_EVEN | JDK docs | `Decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)` |
| 千分位 | JDK docs | Python f-string `f"{q:,}"` |
| NaN → U+FFFD | JDK 8 验证（jjs） | `if d.is_nan(): return "\ufffd"` |
| ±Inf → ±∞ | JDK 8 验证 | `if d.is_infinite(): return "\u221E" if value > 0 else "-\u221E"` |
| -0.00 负零保持 | JDK 8 验证 | Decimal 从 -0.0 量化得 "-0.00" |

**晋升来源**：`tests/test_integration_fixture.py:36-58`（已含完整实现 + docstring + 12 个 parametrize 期望值）。

**晋升时实装 large finite 修复**（user 团 round-7.7 P1-7）：

```python
# 实测：
Decimal(float(1e20)).quantize(Decimal("0.01"))         → 100000000000000000000.00  ✓
Decimal(float(1e30)).quantize(Decimal("0.01"))         → InvalidOperation        ✗
Decimal(float(1e100)).quantize(Decimal("0.01"))        → InvalidOperation        ✗
Decimal(float(1e308)).quantize(Decimal("0.01"))        → InvalidOperation        ✗
Decimal(float(-1e30)).quantize(Decimal("0.01"))        → InvalidOperation        ✗
```

```python
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

def format_java_double(value) -> str:
    """java.text.NumberFormat(Locale.ENGLISH) with minimumFractionDigits =
    maximumFractionDigits = 2 (ST.java:3017-3019).

    JDK 8 DecimalFormat rounds HALF_EVEN on the exact binary expansion of the
    double (verified against JRE 1.8.0_451: 2.675 -> "2.67", -0.0 -> "-0.00",
    999.995 -> "1,000.00").

    Large finite values (up to 1e308) use localcontext with sufficient precision
    to avoid InvalidOperation (Java NumberFormat accepts the full double range).
    """
    d = Decimal(float(value))
    if d.is_nan():
        return "\ufffd"
    if d.is_infinite():
        return "\u221E" if value > 0 else "-\u221E"
    with localcontext() as ctx:
        ctx.prec = max(50, len(d.as_tuple().digits) + 10)   # 覆盖 double 全范围
        q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return f"{q:,}"
```

**晋升后 W1 新增 large finite 测试**（user 团 round-7.7 P1-5 + P1-7 强制要求）：

```python
# 这些 expected 字符串必须从 JRE8 probe 实际抓取——**不要自己推导**。
# probe 命令（实施前一次性执行）：
#   jjs> var nf = java.text.NumberFormat.getInstance(java.util.Locale.ENGLISH);
#   nf.setMinimumFractionDigits(2); nf.setMaximumFractionDigits(2);
#   nf.format(1e30); nf.format(-1e30); nf.format(1e100); nf.format(1e308);
# 把 4 个 JRE8 实际输出字符串冻结成 expected。
@pytest.mark.parametrize(
    "value, expected",
    [
        (1e30,  "<JRE8 actual: e.g. '1,000,000,000,000,000,000,000,000,000.00'>"),
        (-1e30, "<JRE8 actual: e.g. '-1,000,000,000,000,000,000,000,000,000.00'>"),
        (1e100, "<JRE8 actual: e.g. '10,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000.00'>"),
        (1e308, "<JRE8 actual: e.g. '100,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000.00'>"),
    ],
)
def test_format_java_double_large_finite(value, expected):
    assert format_java_double(value) == expected
    # 不要只断言 "not NaN" —— 必须 byte-exact 复刻 JRE8 NumberFormat
```

**实施步骤**（user 团 round-7.7 P1-5）：
1. 实施 round-8 前，在 Windows JRE 1.8.0_451 上跑 jjs probe，抓取 4 个实际 expected 字符串
2. 把 expected 字符串 freeze 进 W1 测试
3. **不能用自己推导的 expected**——Compatibility First 原则要求 Java 行为为唯一 oracle

**晋升后**：测试改为 `from pystemtc.javaformat import format_java_double`，行为不变，147/147 + 新增 writer 测试全部绿。

### 4.2 `java_double_to_string`（已有，需验证）

| Java 源 | 行号 | PySTEMTC 实现 |
|---|---|---|
| `Double.toString(double)` | JDK 8 docs | `src/pystemtc/javaformat.py:26 java_double_to_string` |

**实测**（`javaformat.py:13-25`）：the only observed deviation of JDK 8's legacy `Double.toString` from the ...（user 团裁决"不要简化——已在文件中详尽记录"）。

### 4.3 `double_to_sz`（已有）

| Java 源 | 行号 | PySTEMTC 实现 |
|---|---|---|
| `Util.doubleToSz(double)` | `Util.java:156-196` | `src/pystemtc/javaformat.py:96 double_to_sz`（已含 0.995 阈值循环 + E-notation 分支）|

**实测**（`javaformat.py:97-119`）：line by line 实现（user 团裁决"round-7.3 已冻结 + c14 已验证"，无需改）。

### 4.4 `write_java_tables`（新增）

**核心循环**（genetable per-cell）：

```python
# result.py 新增方法（user 团 round-7.7 contract 恢复）
def write_java_tables(
    self,
    output_dir,
    prefix=None,
    encoding=None,
    newline=None,
) -> list[str]:
    """Write Java-compatible genetable + profiletable.

    Returns the absolute paths (as str) of the two written tables:
      [genetable_path, profiletable_path]

    Parameters
    ----------
    output_dir : Path-like
        Directory to write the two .txt files into. Created if missing.
    prefix : str or None
        Output basename (without extension). Required for DataFrame-built
        results; auto-derived from `result.input["data_file"].stem` for
        path-built results (matches Java batch <defaults文件名>).
    encoding : str or None
        Encoding for write. None = platform default. C2 byte exact requires
        explicit pin (e.g. "gbk"). Writer internally fixes errors="replace"
        (API does NOT expose errors=).
    newline : str or None
        Newline for write. None = platform default. C2 byte exact requires
        explicit pin (e.g. "\\r\\n"). Writer writes "+LF" only and lets
        Python text I/O handle conversion (no double-CRLF).
    """
    if prefix is None:
        if self.input.get("form") == "dataframe":
            raise ValueError(
                "write_java_tables: prefix required for DataFrame-built results; "
                "pass prefix= to specify the output basename."
            )
        if self.input.get("form") == "path":
            prefix = Path(self.input["data_file"]).stem
        else:
            raise ValueError(
                f"write_java_tables: cannot derive prefix from form={self.input.get('form')!r}"
            )
    # ... full implementation per docs/03 §1.10
    return [str(genetable_path), str(profiletable_path)]
```

**reviewer 关键检查点**：

1. **`gene_header` / `probe_header` 取自 `self.input["gene_header"]` / `self.input["probe_header"]`**（不是 `self.metadata`、不是 dataset）——确认 `engine.py:339-340` 已写入 `input_record["probe_header/gene_header"]`。
2. **末列无条件**：`for j, (value, present) in enumerate(zip(g.values, g.present)): if j < T - 1 and not present: cell = "" else: cell = format_java_double(value)`。
3. **Tie profile**：`";".join(str(p) for p in g.profile_ids)`——**禁止** `.sort()` / `sorted()`。
4. **Profiletable 6-column formatter matrix**（user 团 round-7.7 P1-4 修正）：每列独立 formatter——禁止把 `# Genes Assigned / # Gene Expected` 也走 `format_java_double`（那是 2 decimals + 千分位，会破 byte oracle）。W1 必须断言 `len(header_cols) == 6`。
5. **Profiletable p-value**：必须用 `double_to_sz`（含 0.995 阈值循环）——禁止用 `format_java_double` 或 `java_double_to_string`。
6. **Encoding + newline 参数**：默认 `None` → 平台默认；C2 byte exact 必须显式 pin（GBK + CRLF）。
7. **GBK NaN/Inf 字节**（user 团 round-7.7 P1-2 修正）：±Inf formatter → U+221E → GBK 可编码 → `A1 DE` / `2B A1 DE` / `2D A1 DE`；NaN formatter → U+FFFD → GBK 不可编码 → `errors="replace"` → `0x3F`。**c14 oracle 没有 NaN 落盘**——不能作 `U+FFFD→0x3F` 的 byte-oracle 证据；W1 必须新增独立 NaN→U+FFFD→GBK `errors="replace"`→`0x3F` 测试。

### 4.5 determinism 重写（5 项 P2/P3 清扫之一）

```python
# benchmark_real.py:1060-1086 改写为：
ref = py_payloads[0]["gene_assignments"]
ref_keys = set(ref.keys())
ref_lists = {g: list(ref[g]) for g in ref_keys}
for k, p in enumerate(py_payloads[1:], start=2):
    cur_keys = set(p["gene_assignments"].keys())
    if cur_keys != ref_keys:                                    # retained gene 集合一致
        determinism["py_consistent"] = False
        determinism["py_diff_examples"].append(("keys", ref_keys - cur_keys, cur_keys - ref_keys))
        break
    for g in ref_keys:
        cur = list(p["gene_assignments"][g])
        if cur != ref_lists[g]:                                 # ordered profile_ids 一致
            determinism["py_consistent"] = False
            determinism["py_diff_examples"].append((k, g, ref_lists[g], cur))
            break
    if not determinism["py_consistent"]:
        break
```

**Java 侧同样改写**（`benchmark_real.py` 后半段）。

### 4.6 `git_state` 字段（writer round 实装；user 团 round-7.7 P2-3 改名）

`git_dirty` 天然像布尔值，且前面已冻结 `git_dirty=false` 易混淆——本 round 改名为 `git_state`，避免歧义。

```python
# benchmark_real.py::_profile_dataset 加（user 团 round-7.7 P1-6 修正：必须三态，禁止 unknown→clean）：
def _git_state(repo_root: Path) -> tuple[str, str]:
    """Return ("clean" | "dirty" | "unknown", diff_sha256-or-empty).

    "unknown" means git command failed / repo_root is not a repo / git not installed.
    Never silently map "unknown" to "clean" -- it would falsify the official
    baseline gate (Round-7.6 P1-EVIDENCE pattern).
    """
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "unknown", ""                                          # NOT "clean"
    if out.returncode != 0:
        return "unknown", ""                                          # NOT "clean"
    diff = out.stdout.strip()
    if not diff:
        return "clean", ""
    return "dirty", hashlib.sha256(diff.encode("utf-8")).hexdigest()

# 在 profile dict 加（user 团 round-7.7 P2-3 命名）：
"git_state": git_state,             # "clean" | "dirty" | "unknown"
"git_diff_sha256": diff_sha256,     # 当 git_state == "dirty" 时有意义
```

**三态语义**：

```text
clean   → git status --porcelain 空；official baseline 通过
dirty   → git status --porcelain 非空；official baseline 拒绝
unknown → git 命令失败 / 不是 repo / git 未安装；official baseline 拒绝（不接受 "可能是 clean" 猜测）
```

**Official gate**：

```python
if git_state != "clean":
    raise RuntimeError(
        f"official baseline requires clean worktree; got git_state={git_state!r}"
    )
```

**普通运行**：允许 dirty 或 unknown，artifact 明确写 `git_state=dirty|unknown`。
**Official baseline 模式**：遇到 dirty **或 unknown** 都拒绝。Round-8 **不暴露新 CLI 参数**——只在 R1 重跑流程内部强制 gate。

**W1 测试要求**：

```text
test_git_state_clean_when_no_diff:
  mock subprocess.run 返回 (rc=0, stdout="")
  → ("clean", "")

test_git_state_dirty_when_has_diff:
  mock subprocess.run 返回 (rc=0, stdout="?? foo.py")
  → ("dirty", "<sha256>")

test_git_state_unknown_when_subprocess_fails:
  mock subprocess.run 抛 FileNotFoundError
  → ("unknown", "")      # NOT "clean"

test_git_state_unknown_when_nonzero_exit:
  mock subprocess.run 返回 (rc=128, stdout="")
  → ("unknown", "")      # NOT "clean"
```

---

## 5. Test Matrix（4 层验收）

### 5.1 W1: writer unit behavior（`tests/test_writer.py`，~200 行）

| 测试组 | 内容 |
|---|---|
| `test_format_java_double_*` | 12 个 parametrize case（直接 import 自晋升路径）|
| `test_header_from_input` | header 取自 `result.input["gene_header/probe_header"]`，不取 metadata |
| `test_prefix_default_path` | `prefix=None` + `form=="path"` → `Path(data_file).stem` |
| `test_prefix_default_dataframe_raises` | `prefix=None` + `form=="dataframe"` → ValueError |
| `test_prefix_explicit` | `prefix="custom"` → 写 `custom_genetable.txt` |
| `test_missing_non_terminal` | `present=False` + `j<T-1` → 空串 |
| `test_missing_terminal_unconditional` | `present=False` + `j==T-1` → `format_java_double(value)`（即使是 NaN/±Inf）|
| `test_tie_profile_order` | `profile_ids=[2,0]` → `"2;0"`（**禁止 sort**）|
| `test_genetable_nan_inf` | NaN → U+FFFD；+Inf → U+221E；-Inf → -U+221E |
| `test_profiletable_columns` | **6 列**各自 formatter 验证（不能串）；assert `len(header_cols) == 6` |
| `test_profiletable_pvalue_doubletoz` | p=0.995 → 不进 0.995 阈值循环；p=0.0000123 → E-notation |
| `test_encoding_newline_default` | `encoding=None, newline=None` → 平台默认 |
| `test_encoding_explicit` | `encoding="utf-8"` → UTF-8；`newline="\n"` → LF |
| `test_encoding_gbk_replace_default` | `write_java_tables(..., encoding="gbk", newline="\r\n")`（**API 不传 `errors=`**，writer 内部固定 `errors="replace"`；user 团 round-7.7 P2-2）→ bytes 内容验证 U+FFFD 路径 0x3F |

**W1 验收门槛**：~25 个 unit test 全绿。

### 5.2 W2: C1 fixture exact（`tests/test_writer_c1.py`，~150 行）

**14 套 c01-c14 + 1 套 custom_header = 15 套 fixtures × 2 tables = 30 cases**（user 团 round-7.7 P1-3 修正：明确拆 14 + custom）

实测 `tests/golden/java_configs/` = 14 个 config = c01-c14；`headers_custom` 不在此目录（要在新 `tests/golden/writer_configs/`）。

```python
# tests/test_writer_c1.py
from tests.test_golden import ALL_CASES  # 14 个 c01-c14
from tests.test_writer_c1 import HEADER_CUSTOM_CASE_NAME  # "headers_custom"

# c01-c14 genetable + profiletable = 28 cases
@pytest.mark.parametrize("case", ALL_CASES)
def test_genetable_c1_decoded_exact(case, tmp_path):
    # 1. 读 Java oracle fixture（tests/golden/java_reference/{case}_genetable.txt）
    # 2. 跑 engine.fit → STEMResult
    # 3. write_java_tables → tmp_path
    # 4. 读 Python 输出 + Java oracle，按 canonical GBK 解码（user 团 round-7.7 P1-4）
    # 5. 与 oracle 解码后内容逐字段比较（C1 decoded exact）

@pytest.mark.parametrize("case", ALL_CASES)
def test_profiletable_c1_decoded_exact(case, tmp_path):
    # 同样结构，profiletable

# custom_header genetable + profiletable = 2 cases（单独跑，config 路径不同）
def test_custom_header_genetable_c1_decoded_exact(tmp_path):
    # config_path = tests/golden/writer_configs/headers_custom.txt
    # oracle = tests/golden/java_reference/headers_custom/headers_custom_genetable.txt

def test_custom_header_profiletable_c1_decoded_exact(tmp_path):
    # 同上，profiletable
```

**C1 写阶段必须显式 GBK**（user 团 round-7.7 P1-4）：W2 写文件时用 `encoding="gbk"`——否则 Python 机器默认 UTF-8 时 NaN 渲染成 U+FFFD 真实字节，与 Java `errors="replace"` 后 `?` 字节路径不同，C1 会错误失败。

```python
result.write_java_tables(
    tmp_path,
    prefix=case,
    encoding="gbk",            # ← W2 必 pin GBK
    newline="\n",              # ← W2 C1 不要求 CRLF（CRLF 是 C2 职责）
)
python_text = (tmp_path / f"{case}_genetable.txt").read_text(encoding="gbk")
java_text = oracle.read_text(encoding="gbk")
# 逐字段/逐行内容比较
```

**custom_header config 入仓 + 复现验证**（user 团 round-7.7 P1-5 + P2-1）：

```text
第一次入仓时必须执行：
  tests/golden/writer_configs/headers_custom.txt
  +
  tests/golden/headers/custom_header.txt   (自定义 gene/probe header)
  +
  JRE8 STEM v1.3.14
  ↓
  重新生成两张表
  ↓
  与现有 tests/golden/java_reference/headers_custom/*.txt byte-exact
  ↓
  才证明：入仓 config 是产生现有 oracle 的那一份
```

三件套 = **形式闭环 + 证据闭环**：

```text
tests/golden/writer_configs/headers_custom.txt       ← 入仓：原 config 字节
tests/golden/java_reference/headers_custom/headers_custom_genetable.txt    ← 已存
tests/golden/java_reference/headers_custom/headers_custom_profiletable.txt  ← 已存
```

**W2 验收门槛**：30 cases 全绿（28 c01-c14 + 2 custom_header）。custom_header case 依赖 `writer_configs/headers_custom.txt` 入仓 + JRE8 复现验证——入仓 + 复现验证是 W2 验收前提。

### 5.3 W3: C2 canonical byte exact（`tests/test_writer_c2.py`，~150 行）

**14 套 c01-c14 + 1 套 custom_header = 15 套 × 2 tables = 30 cases**

```python
@pytest.mark.parametrize("case", ALL_CASES)  # 14 个 c01-c14
def test_c2_byte_exact(case, tmp_path):
    # 1. 跑 engine.fit → STEMResult
    # 2. write_java_tables(output_dir, prefix=case, encoding="gbk", newline="\r\n")
    #    writer 内部固定 errors="replace"（user 团 P2-3 / P2-2 不暴露）；API 不暴露 errors=
    # 3. 读 Python 输出 bytes（不要先 decode——C2 比 byte）
    # 4. 读 Java oracle bytes
    # 5. 字节比对（C2 byte exact）
    assert py_bytes == java_oracle_bytes
    assert b"\r\r\n" not in py_bytes                      # P1-3 \r\r\n guard

def test_custom_header_c2_byte_exact(tmp_path):
    # custom_header 单独跑，config 路径与 W2 一致
```

**关键检查点**（user 团 round-7.7 P1-2 修正）：
- c14 oracle 里**没有 NaN 落盘**——oracle 全文 0 处 `0x3F`（`grep -c "3F" c14_log_missing_genetable.txt` = 0）。
- c14 的 `-∞` 全部是 GBK 真编码字节 `2D A1 DE`，**不是** `2D 3F`。
- W1 必须新增独立的 NaN→U+FFFD→GBK `errors="replace"`→`0x3F` 测试（不靠 c14 oracle）。

**W3 验收门槛**：30 cases 全绿（C2 byte exact）；30 个文件均无 `b"\r\r\n"`。

### 5.4 W4: R1 v2 clean-commit 重跑（benchmarks/benchmark_real.py R1 path）

**入口条件**：
- `git_commit = round-8 writer 最终 commit hash`
- `git_state = "clean"`（R1 重跑流程内部强制 gate；不暴露 CLI 参数）
- Python 端：`engine.fit(...)` + `result.write_java_tables(...)`
- Java 端：`java -jar stem.jar -b <indir> <outdir>`（已含 batch table writes）
- 两端 workload 等量：analysis + table writes 双侧

**验收**：
- `assignment_exact` PASS（1635/1635, 0 mismatch；与 R1 v2 baseline 一致）
- `C1 exact` PASS（30 个 fixture decoded exact——已在 W2 验过，这里是 Py/Java side-by-side）
- `Py/Java e2e ratio`：**等工作量** baseline（writer 接入前 PROVISIONAL 1.05× 升级为正式 baseline）
- `git_state="clean"` 实测确认

**W4 验收门槛**：R1 v2 重跑后 4 个 PASS。

---

## 6. C1/C2 Acceptance Criteria

### 6.1 C1 decoded exact（round-7.2 frozen；user 团 round-7.7 P2-2 修正定义）

```text
C1 = 按各 artifact 实际编码解码后做字段级比较

- header（含原始 gene/probe header）
- row order
- profiletable 全部字段
- genetable 全部字段
- 空缺格空串 ""
- 末列无条件输出
- -0.00 的负零渲染
- ±∞ / U+FFFD 的特殊值渲染
- tie profile 顺序（";" 分隔）

关键约束（user 团 P2-2 修正）：
对于 canonical Windows oracle，Java 侧固定 GBK 解码。
涉及不可编码字符的 lossy replacement 时，C1 必须使用同一目标
encoding + replacement policy；不能宣称完全 encoding-independent。
```

**C1 不是"完全不受 encoding 影响"**——对可无损编码的字符成立；遇 `U+FFFD → ?` 这种 lossy encoding 就不成立。Java 侧固定 GBK 解码，Python 侧 `errors="replace"` 固定为 writer 内部语义（user 团 P2-3），C1 比较两边的解码后字段。

### 6.2 C2 byte exact（round-7.2 frozen）

```text
C2 = 字节级一致
- 显式 pin encoding + newline
- 默认：encoding=None, newline=None（不承诺 byte exact）
- 显式：encoding="gbk", newline="\r\n"（与 Windows JRE8 oracle 对齐）

关键约束（user 团 P1-3）：永远 f.write(line + "\n")，让 Python text I/O
层负责 newline 转换——禁止手动写 "\r\n" 到 line 末尾，会产生 \r\r\n。
```

**Round-8 W3 验证点**（user 团 P1-2 修正）：c14 oracle **不能**作为 `U+FFFD→?` 的 byte-oracle 证据——c14 全文 0 处 `0x3F`，oracle 的 `-∞` 全部是 GBK 真编码 `2D A1 DE`。W1 必须新增独立的 `test_format_java_double_nan_encodes_to_ufffd_then_question_mark_under_gbk_errors_replace` 测试——靠 U+FFFD 字符本身的 GBK encode 行为 + `errors="replace"` 副作用证明。

---

## 7. R1 Official Rerun Protocol

按 user 团裁决"最终 R1 evidence 绑定到一个明确 commit + clean worktree"：

```text
0. working tree 清理（git status --porcelain → keep+track / delete / ignore）
1. P2/P3 5 项清扫
2. javaformat 晋升
3. write_java_tables 实装
4. W1 unit tests（green）
5. W2 c01-c14 C1（green）
6. W3 canonical C2（green）
7. pre-final full test（147 + ~50 writer tests，全绿）
8. commit writer implementation（commit hash 记下：GIT_COMMIT_WRITER）
9. 确认 `git_state == "clean"`（git status --porcelain 空；三态探测：clean / dirty / unknown，user 团 round-7.7 final cleanup）
10. post-review（reviewer 针对 GIT_COMMIT_WRITER 审查；工具 bug 时 main-session 自 verify）
11. 若 review 有修改：修 → 重跑 W1-W3 → 新 commit → 再确认 clean
12. R1 official 重跑（Python fit+write vs Java analyze+write，等工作量）
13. 最终 full test + evidence package（docs/08_m4_round8_report.md + verification/round8_* artifacts）
```

**关键**：post-review 必须在**commit 之后、`git_state == "clean"` 确认之后**进行——这样 reviewer 审查的是确切 commit 状态。

---

## 8. Explicit Out-of-Scope

| 项 | 类别 | 不做的理由 |
|---|---|---|
| `benchmark_real.py` 拆模块 | 架构重构 | user 团明确：Compatibility C 落地时最忌讳 writer + 重构一起发生；V1.0 后再拆 |
| dict → dataclass 重构 | 架构重构 | user 团明确：当前纯 dict 已有 R1 evidence；最小变化原则 |
| `dataio.py` 新增 `gene_keys` helper | 架构重构 | user 团明确：不是 writer 需求；留 P3 |
| repository-wide `.gitattributes` + `eol=lf` | 工程治理 | user 团明确：会破坏 byte oracle；EOL 治理延后 |
| `effective_missing_rate` 实现 | 新增指标 | user 团明确：不是 writer 职责；未来由独立 pipeline instrumentation 提供 |
| R2 (repeats) 真实数据 benchmark | 数据扩展 | user 团明确：non-blocking；V1.0 后 |
| R3 (missing/high-T) 真实数据 benchmark | 数据扩展 | user 团明确：non-blocking；V1.0 后 |
| 任何性能优化 | 优化 | user 团明确：baseline only，不设合格线 |
| 新 CLI 参数 `--official` | 接口扩展 | Round-8 不暴露新参数；只在 R1 重跑流程内部 gate |

---

## 9. Risks / P0-P2

### 9.1 P0（必须 green 才能 ship）

| Risk | 缓解 |
|---|---|
| ~~c14 oracle 的 GBK `errors="replace"` 行为（NaN → `?`）漏复刻~~ | **已撤**：c14 没有 NaN 落盘；改用 W1 独立 `test_format_java_double_nan_encodes_to_ufffd_then_question_mark_under_gbk_errors_replace` |
| Profiletable p-value formatter 用错（`format_java_double` vs `double_to_sz`） | W1 显式 `test_profiletable_pvalue_doubletoz` 验证 |
| Tie profile 顺序被 writer 错误 sort | W1 `test_tie_profile_order` 显式验证 `[2,0] → "2;0"` |
| 末列无条件 — 把 `present=False` 的 NaN 列错误返回 `""` 而不是 `format_java_double` | W1 `test_missing_terminal_unconditional` 显式验证 |
| Header 取错来源（`metadata` vs `input`） | W1 `test_header_from_input` + 代码 review |

### 9.2 P1（high risk）

| Risk | 缓解 |
|---|---|
| GBK encoder 与 JDK 8 NumberFormat 字节差异（千分位、负零、`-∞` 字节）| W3 c01-c14 C2 byte exact；逐字节对比 oracle |
| Prefix 自动推导错误（`Path(data_file).stem` 与 Java `defaults文件名` 不一致） | W1 `test_prefix_default_path` 验证；CLI 模式手动对照 |
| Encoding / newline 默认行为与 Java 不一致 | W1 `test_encoding_newline_default` 验证；W2 显式 pin `encoding="gbk"`；W3 进一步 pin `newline="\r\n"` 做 byte-exact（user 团 round-7.7 final cleanup） |

### 9.3 P2（medium risk）

| Risk | 缓解 |
|---|---|
| `git_state` 探测在 Windows / Linux 不同 git 版本下 `porcelain` 输出格式不同 | 测试时在 Windows + Linux 各跑一次 R1（user 团 round-7.7 final cleanup：rename `git_dirty` → `git_state`） |
| R1 v2 重跑 workload 不等量（Java 含 table writes，Python 含 write_java_tables） | W4 验证两边 workload 时间分布一致；如不等量重新平衡 |
| `determinism` 重写后 147 测试偶发 failure（key-set 顺序依赖 dict iteration） | W4 R1 验证 Py determinism PASS（已多次验过）|
| `final_retained_genes` 回填时机错误（写 csv 之前） | review 代码路径 + W4 R1 验证 profile.csv 该列非空 |

### 9.4 Out-of-Scope Risks（已知不做）

| Risk | 接受方式 |
|---|---|
| `benchmark_real.py` 超过 1200 行 | 接受；V1.0 后再拆 |
| dict 数据结构脆弱 | 接受；现有 147 tests 已覆盖关键路径 |
| 性能比 Java 慢（1.05× 当前） | 接受；baseline only |
| `effective_missing_rate` 未提供 | 接受；非 writer 职责 |

---

## 10. 给 reviewer 的关键问题

按 user 团要求："**这份plan有没有遗漏Java输出语义？**"

请 reviewer 重点审查：

1. **§2 Frozen Java Writer Behavior** 是否完整覆盖 `ST.java` genetable + profiletable 输出语义？
2. **§4 Exact Implementation Mapping** 4 个 formatter（`format_java_double` 晋升 / `java_double_to_string` / `double_to_sz` / 隐藏的 GBK `errors="replace"`）是否与 Java 字节一致？
3. **§5 Test Matrix** 4 层验收门槛是否合理（catch P0/P2 risk）？
4. **§7 R1 Official Rerun Protocol** 12 步顺序是否正确（commit → clean → post-review → R1 重跑）？
5. **§8 Explicit Out-of-Scope** 是否遗漏任何应做但未列出的事项？
6. **§9 Risks** P0/P1 缓解措施是否足够？

如 plan 通过 main-session 即开始实施；如需修改则吸收 reviewer feedback 后再实施。

---

## 附录 A：源码行号索引

| 引用 | 路径 + 行号 |
|---|---|
| `format_java_double` 晋升源 | `tests/test_integration_fixture.py:36-58` |
| `format_java_double` 12 parametrize cases | `tests/test_integration_fixture.py:148-160` |
| `java_double_to_string` 现有 | `src/pystemtc/javaformat.py:26` |
| `_number_format` 现有 | `src/pystemtc/javaformat.py:86` |
| `double_to_sz` 现有（Util.doubleToSz 复刻） | `src/pystemtc/javaformat.py:96` |
| `STEMResult` dataclass 起点 | `src/pystemtc/result.py:132` |
| `GeneAssignment` dataclass（含 `present: list[bool]` + `values: list[float]` + `profile_ids: list[int]`） | `src/pystemtc/result.py:125-130` |
| `engine.fit` 入口（写 `input_record["probe_header/gene_header"]`） | `src/pystemtc/engine.py:91` + `:339-340` |
| `dataset.sample_labels`（dsamplemins 来源）| `src/pystemtc/dataset.py`（具体行待定；plan 阶段未访问）|
| `benchmark_real.py` docstring 残留 | `:38, :125, :127` |
| `benchmark_real.py` determinism 漏检 | `:1060-1086` |
| `benchmark_real.py` summary 标题 | `:920` |
| Java genetable writer | `ST.java:3021-3033`（已冻结引用） |
| Java `Util.doubleToSz` | `Util.java:156-196`（已冻结引用） |
| Java NumberFormat | `ST.java:3017-3019`（已冻结引用） |
| c14 oracle 字节（c14 全文 0 处 `0x3F`；`-∞` 全部 GBK 真编码 `2D A1 DE`）| `tests/golden/java_reference/c14_*` |
| docs spec 锚点 | `docs/03_v1_implementation_spec.md §1.10`（round-7.3 frozen） |

## 附录 B：Round-7.7 → Round-8 治理状态迁移

```text
Round-7.7：CLOSED
Round-7.8：DO NOT CREATE
Round-8：Compatibility C / writer round（GO）

算法核心：FROZEN
真实benchmark：暂停扩数据（等 writer 后重跑 R1）
R2/R3：POST-V1.0 / non-blocking
JRE17：characterization only
性能优化：OUT OF ROUND-8
repository-wide EOL治理：OUT OF ROUND-8
GitHub Windows/Linux CI：V1.0 release blocker（仍在 user 侧）

byte oracle 资产：tests/golden/java_reference/** 继续 -text 保护
```