# Round-8 Plan Diff 摘要（user 团 round-7.7 review 12 项修正）

> 日期：2026-09-20
> 来源：`docs/08_m4_round8_prereview_plan.md`
> 类型：plan 修正（review feedback 落地）
> 未创建新 commit（HEAD 仍 `01b954a`，等 round-8 第一笔 commit 正式纳管）

---

## 总览

| 级别 | 项 | 旧版错误 | 新版合同 |
|---|---|---|---|
| P1-1 | Header 注入规则 | 无条件写 `0`/`sample_labels[1:]` | `*result.input["time_points"]` 完整 sample_labels；writer 绝不自写 `00` |
| P1-2 | GBK hidden contract | c14 oracle 是 `errors="replace"` 行为 `-∞→2D3F` | c14 全文 0 处 `0x3F`；`-∞` 是 GBK 真编码 `2D A1 DE`；NaN→U+FFFD 走单独 W1 测试 |
| P1-3 | newline 写入 | `f.write(line + newline_str)` 双转换产生 `\r\r\n` | `LINE_TERMINATOR = "\n"`；让 Python text I/O 负责 newline；W1 新增 `b"\r\r\n" not in py_bytes` 断言 |
| P1-4 | Profiletable 列数 | 错写 5 列 | 实测 6 列 + 硬编码完整 header `["Profile ID", "Profile Model", "Cluster (-1 non-significant)", "# Genes Assigned", "# Gene Expected", "p-value"]` |
| P1-5 | custom_header config | config 不在仓；W2 无法复现 | 新增 `tests/golden/writer_configs/headers_custom.txt` 入仓；三件套（config + input + oracle）闭环 |
| P1-6 | git dirty 三态 | `except Exception: return False, ""` 误报 clean | 三态 `"clean" | "dirty" | "unknown"`；unknown ≠ clean；official baseline 拒绝 dirty **或** unknown |
| P1-7 | large finite | `1e30 / 1e100 / 1e308` 触发 InvalidOperation | `localcontext` 提升精度；W1 新增 4 个 large finite 测试 |
| P2-1 | C2 覆盖度 | 4 套抽样 | 全 15 套 × 2 表 = 30 cases |
| P2-2 | C1 不受 encoding 影响 | 绝对表述 | 遇 lossy replacement 不成立；Java 固定 GBK 解码，Python 固定 `errors="replace"` |
| P2-3 | `errors="replace"` 暴露 | API 不暴露 | writer 内部固定 `errors="replace"`；API 仍只 `encoding=None` |
| P2-4 | 行序冻结 | tie 不 sort 但整表行序没说 | profiletable 按 `self.profiles` 现有顺序；genetable 按 `self.gene_assignments` 现有顺序；Compatibility A 负责上游顺序 |
| P2-5 | ALL_CASES 复用 | `f"c{i:02d}"` 假 stem | 直接 `from tests.test_golden import ALL_CASES` |

---

## 各项 diff 详情

### P1-1：Genetable 表头规则

```diff
- gene_header        ← result.input["gene_header"]（dataset gene_header 字段）
- probe_header       ← result.input["probe_header"]（dataset probe_header 字段；非 SPOT 形式）
- Profile            ← 字面字符串 "Profile"
- 0                  ← 字面字符串 "0"（time 0 标识）
- dsamplemins...     ← dataset.sample_labels[j]（j=1..T-1）
+ gene_header        ← result.input["gene_header"]（dataset gene_header 字段）
+ probe_header       ← result.input["probe_header"]（dataset probe_header 字段；非 SPOT 形式）
+ Profile            ← 字面字符串 "Profile"
+ time_points        ← result.input["time_points"]（**完整 sample_labels**，含 t0 标识；不是 j=1..T-1）
+
+ **关键合同（user 团 round-7.7 P1-1 修正）**：
+ c01 oracle header: Gene Symbol\tSPOT\tProfile\t0h\t0.5h\t3h\t6h\t12h
+ c04 add0 oracle header: Gene Symbol\tSPOT\tProfile\t0\t0h\t0.5h\t3h\t6h\t12h
+ c14 oracle header: Gene Symbol\tSPOT\tProfile\t0h\t1h\t2h\t4h\t8h\t24h
+
+ header = [
+     result.input["gene_header"],
+     result.input["probe_header"],
+     "Profile",
+     *result.input["time_points"],
+ ]
```

### P1-2：GBK facts

```diff
- | 字符 | Unicode | GBK bytes |
- | `∞` (U+221E) | 圆 | `A1 DE`（实测 oracle fixture）|
- | `-∞` | `-` + U+221E | `2D A1 DE` |
- | U+FFFD | 替换字符 | **GBK 不能直接 encode**；必须 `errors="replace"` → `?` (0x3F) |
-
- **关键实现细节**：`open(..., encoding="gbk", errors="replace")` → NaN/±Inf/其他非 GBK 字符会变成 `?`；这是 c14 冻结的 byte oracle 行为（c14 oracle fixture 里 `-∞` 写为 `2D 3F` 而非 `2D A1 DE`——这是 GBK `errors="replace"` 的副作用，**必须复刻**）。

+ 实测 `python -c "s.encode('gbk', errors='replace')"`：
+
+ | 字符 | Unicode | GBK bytes（实测） | 备注 |
+ | `∞` (U+221E) | 圆 | `A1 DE` | **GBK 可编码**——`errors="replace"` 不触发 |
+ | `-∞` | `-` + U+221E | `2D A1 DE` | 同上 |
+ | `+∞` | `+` + U+221E | `2B A1 DE` | 同上 |
+ | U+FFFD | 替换字符 | `3F` | **GBK 不可编码**——`errors="replace"` → `?` |
+
+ **c14 oracle 实测**：0 处 `3F`；c14 全文 `-∞` 全部是 `2D A1 DE`——**c14 不能作为 `U+FFFD→?` 的 byte-oracle 证据**。
+
+ W1 新增 test_format_java_double_nan_encodes_to_ufffd_then_question_mark_under_gbk_errors_replace
```

### P1-3：newline 防 `\r\r\n`

```diff
- with open(path, "w", encoding=encoding, newline=newline) as f:
-     f.write(line + newline_str)  # 每行后写 newline
+ LINE_TERMINATOR = "\n"  # 永远写 LF
+ 
+ with open(
+     path,
+     "w",
+     encoding=resolved_encoding,
+     errors="replace",                  # writer 内部固定
+     newline=resolved_newline,
+ ) as f:
+     for row in rows:
+         f.write(row + "\n")             # 永远 +LF；不写 +newline_str
+
+ W1 新增断言：
+   write_java_tables(..., encoding="gbk", newline="\r\n")
+   → 0 处 b"\r\r\n"
```

### P1-4：Profiletable 6 列

```diff
- ### 2.2 Profiletable（round-7.3 frozen）
- 5 列，每列独立 formatter（**不能为了"统一代码"全部走 `format_java_double`**）：
+ ### 2.2 Profiletable（round-7.3 frozen；user 团 round-7.7 P1-4 修正）
+ **6 列**，每列独立 formatter。
+
+ PROFILETABLE_HEADER = [
+     "Profile ID",
+     "Profile Model",
+     "Cluster (-1 non-significant)",
+     "# Genes Assigned",
+     "# Gene Expected",
+     "p-value",
+ ]
+
+ 行序冻结（user 团 round-7.7 P2-4）：
+   profiletable 按 self.profiles 现有顺序输出，禁止 writer 排序
+   genetable 按 self.gene_assignments 现有顺序输出，禁止 writer 排序
```

### P1-5：custom_header config 入仓

```diff
+ tests/golden/writer_configs/headers_custom.txt       ← 入仓（原 config 字节）
+ tests/golden/java_reference/headers_custom/headers_custom_genetable.txt    ← 已存
+ tests/golden/java_reference/headers_custom/headers_custom_profiletable.txt  ← 已存
+
+ 不要放进 tests/golden/java_configs/（会被 test_golden.py glob 自动消费）
```

### P1-6：git_dirty 三态

```diff
- def _git_dirty_state(repo_root: Path) -> tuple[bool, str]:
-     """Return (is_dirty, diff_sha256-or-empty)."""
-     try:
-         out = subprocess.run(["git", "status", "--porcelain"], ...)
-         diff = out.stdout.strip()
-     except Exception:
-         return False, ""          # ← 误报 clean！
-     return bool(diff), ...

+ def _git_dirty_state(repo_root: Path) -> tuple[str, str]:
+     """Return ("clean" | "dirty" | "unknown", diff_sha256-or-empty).
+     Never silently map "unknown" to "clean"."""
+     try:
+         out = subprocess.run(["git", "status", "--porcelain"], ...)
+     except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
+         return "unknown", ""          # NOT "clean"
+     if out.returncode != 0:
+         return "unknown", ""          # NOT "clean"
+     diff = out.stdout.strip()
+     if not diff:
+         return "clean", ""
+     return "dirty", hashlib.sha256(diff.encode("utf-8")).hexdigest()
+
+ 三态语义：
+   clean → git status --porcelain 空；official baseline 通过
+   dirty → git status --porcelain 非空；official baseline 拒绝
+   unknown → git 命令失败；official baseline 拒绝（不接受猜测）
```

### P1-7：format_java_double large finite

```diff
+ from decimal import Decimal, ROUND_HALF_EVEN, localcontext
+
  def format_java_double(value) -> str:
+     with localcontext() as ctx:
+         ctx.prec = max(50, len(d.as_tuple().digits) + 10)
+         q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
+     return f"{q:,}"
+
+ W1 新增 large finite 测试：
+   @pytest.mark.parametrize("value", [1e30, -1e30, 1e100, 1e308])
+   def test_format_java_double_large_finite(value):
+       result = format_java_double(value)
+       assert "\ufffd" not in result
+       assert "\u221E" not in result
```

### P2-1：W3 全 15 套

```diff
- @pytest.mark.parametrize("fixture_id", ["c01", "c02", "c03", "c14"])  # 4 个代表性 fixture
+ @pytest.mark.parametrize("case", ALL_CASES)  # 全 15 套 × 2 tables = 30 cases
```

### P2-2：C1 修正定义

```diff
- **未 pin encoding/newline** 时只承诺 C1。**`encoding` / `newline` 不影响 C1**（user 团可能不同 platform 默认，但解码后内容应一致）。
+ 关键约束（user 团 P2-2 修正）：
+ 对于 canonical Windows oracle，Java 侧固定 GBK 解码。
+ 涉及不可编码字符的 lossy replacement 时，C1 必须使用同一目标
+ encoding + replacement policy；不能宣称完全 encoding-independent。
```

### P2-3：errors=replace 内部固定

```diff
- # W3 显式 errors="replace"
+ # writer 内部固定 errors="replace"；API 不暴露 errors= 参数
```

### P2-4：行序冻结（已在 P1-4 修复同时落盘）

### P2-5：ALL_CASES 复用（已在 P2-1 修复同时落盘）

```diff
- @pytest.mark.parametrize("fixture_id", [f"c{i:02d}" for i in range(1, 15)] + ["custom_header"])
+ from tests.test_golden import ALL_CASES
+ @pytest.mark.parametrize("case", ALL_CASES)
```

---

## 文件变更总结

| 文件 | 改动 |
|---|---|
| `docs/08_m4_round8_prereview_plan.md` | 538 行 → 748 行（净增 210 行 / 修正 12 处 + 加 verbatim 合同块）|
| 未触碰 | 其它所有文件（live code + tests + 现有 docs）|
| 新增（仅 plan） | `docs/08_m4_round8_plan_diff.md`（本文）|
| 新 commit | 无（按 user 团"round-8 第一笔 commit 把最终 docs/08 正式纳管"）|

---

## 实施入口（plan 通过后）

按 user 团裁决 "REVIEW: GO-WITH-CHANGES，不允许按原文直接实施" → 修 plan → user 团确认 → 实施：

```text
0. working tree 清理（git status --porcelain → keep+track / delete / ignore → git_dirty=false）
1. P2/P3 5 项清扫
2. javaformat 晋升（含 P1-7 large finite localcontext 修复 + 12 个原 parametrize + 4 个新 large finite）
3. write_java_tables 实装（按 P1-1 header + P1-3 LF only + P1-4 6 列 + P2-4 行序冻结 + P2-3 errors=replace 内部固定）
4. W1 unit tests（含 P1-7 large finite + P1-6 git dirty 三态 4 个测试 + P1-2 GBK NaN 测试）
5. W2 c01-c14 C1（ALL_CASES 复用 + custom_header config 入仓）
6. custom_header C1
7. W3 canonical C2（全部 15 套 + b"\r\r\n" guard）
8. pre-final full test（147 + ~50 writer tests + ~30 c1 + ~30 c2 = ~250+ tests，全绿）
9. commit writer implementation（GIT_COMMIT_WRITER）
10. 确认 git_dirty=false（clean state 三态检测）
11. post-review（reviewer 针对 GIT_COMMIT_WRITER 审查；工具 bug 时 main-session 自 verify）
12. 若 review 有修改：修 → 重跑 W1-W3 → 新 commit → 再确认 clean
13. R1 official 重跑（Python fit+write vs Java analyze+write，等工作量）
14. 最终 full test + evidence package（docs/08_m4_round8_report.md + verification/round8_* artifacts）
```