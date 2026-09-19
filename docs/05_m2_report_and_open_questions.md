# PySTEMTC M2 结题报告与遗留问题清单（供专家团评审）
（品牌注记，2026-09-19：品牌自 2026-09-19 起写作 pySTEMTC（py 小写、STEM 大写、tc 小写）；文中 PySTEMTC 为当时记录）

- 日期：2026-09-19
- 范围：第 3 轮 4 个前置 P1 → M2 实现（profiles→assign→permutation→significance→clustering→engine）→ 四道闸门（pre-work review / implementer / 独立 verifier / post-review）→ findings 修复 → 第 4 轮命名定案 → 项目目录更名迁移
- 评审包：`D:\stem\PySTEMTC_review_20260919_215038.zip`（精选内容，见 §6 导读）
- 本报告所有数字均来自 2026-09-19 当日本机实测（Python 3.14.3，JRE 1.8.0_451）

---

## 1. 一段话总结

M2 将 STEM v1.3.14 的核心算法链完整移植并通过全部金标验收：**12/12 配置 Compatibility A 全部 exact（字符串级 0 mismatch），Compatibility B 达到 Java 打印值全等（超出原定容差要求）**；96/96 测试通过。第 3 轮评审的 4 个前置 P1 全部按裁决处置完毕；命名定案 PySTEMTC/`pystemtc` 并完成迁移；用户将项目目录更名为 `D:\stem\pySTEMtc`，证据链完整保留（c09/c10/c11 冻结配置一字未动，复跑通过）。

## 2. 结果总结

### 2.1 第 3 轮 4 个前置 P1 的处置

| P1 | 要求 | 处置 | 证据 |
|----|------|------|------|
| P1-1 raw/standardized 文档矛盾 | 统一为"只收原始表达值" | spec §1.1 定稿：raw only、行=spot 的 DataFrame、无裸 ndarray 入口；全文清除"已标准化矩阵"表述 | docs/03 §1.1 |
| P1-2 "# Genes Assigned" 整数错误 | 改为 double、允许 1/k 并列分数 | spec + 测试 docstring 同步改写；Level A 判据 = 结构/离散 exact + observed tally 经 `Double.toString` 复制品字符串全等 | docs/03 §0；tests/test_golden.py |
| P1-3 binomialtail 边界钉死 | 源码逐行 + 边界单测，不接受自行修正 | StatUtil.java:286-336 逐行钉入 §1.6（count=0 → p≡1；dp≥1 → p=1；严格尾 P(X>x)）；真 JRE `jjs -cp stem.jar` 导出 277 个边界含金向量对拍 | tests/golden/java_statutil/vectors.txt；test_units.py |
| P1-4 on-the-fly 置换逐行核验 | T≥9 路径逐行钉死后再实现，否则缩 V1 | STEM_DataSet.java:1148-1206 逐行钉入 §1.6；c11_synth10 金标覆盖该路径且全列 0 mismatch | docs/03 §1.6；c11 金标 |

### 2.2 M2 交付范围

- 新模块 8 个：`profiles.py`（枚举+抽样+compactprofiles2 贪心）、`assign.py`（掩码 Pearson + 并列 1/k）、`permutation.py`（全排列精确 / universe 有放回子抽样 / on-the-fly 三路径）、`significance.py`（binomialtail + Bonferroni/step-down FDR/none）、`clustering.py`（贪心扩球 + percentile 抬升）、`engine.py`（按 A2 顺序编排）、`javaformat.py`（`Double.toString` + `Util.doubleToSz` 复刻）、`result.py`。
- M2 单测 20 个（test_units_m2.py）；M2 前置钉死文档 §1.6/§1.7。

### 2.3 验证结果（当日本机全新复跑）

| 项 | 结果 |
|----|------|
| 全量测试 | **96 passed**（52 M1 + 20 M2 单测 + 24 金标） |
| 金标（12 配置 × profiletable/genetable） | **24/24 passed，38.41s**，字符串级全等（0 mismatch） |
| Compatibility A | 12/12 全 exact：Profile ID/Model、Cluster、# Genes Assigned、genetable gene/probe/Profile 列 + 全行序 |
| Compatibility B | # Gene Expected 与 p-value 达到 **Java 打印值全等**（原要求容差，实测超出） |
| 浮点纪律 grep（np.sum/mean/std/dot/corrcoef/add.reduce/einsum 于 src/pystemtc） | **0 违规** |
| 冻结 fixtures | c09/c10/c11 配置一字未动（历史 `STEMpy/` 路径前缀保留为证据） |

### 2.4 M2 发现并复刻的 Java quirk（全集见 docs/03 §1.6/§1.7）

1. `genespottimedata` 引用别名：dup 组主行 = 合并后中位数、其余行 = 合并前标准化值（M1 期发现，M2 消费）。
2. `sortedcorrvals` = **预过滤前**全长升序表（percentile 抬升的输入）。
3. `Util.getmedian` 用 `Arrays.sort` 双精度全序——NaN 排最后；log 模式重参照时 `vals[]` 只掩码 `pma[ncol]`、不掩码 `pma[nbegin]`（:1235/:1269 vs :1207），NaN/±Inf 真的会进入中位数。
4. 期望计数缩放 `(expected·numrows)/ntotal`（:1373）——乘除顺序影响 1 ulp。
5. `Math.sqrt(负数)` → NaN 而非异常（Util.java:468/522）——post-review MAJOR 修复。
6. `NumberFormat(NaN)` 输出单个 U+FFFD（jjs 实测，裁决了两个 reviewer 的争议）。
7. FDR 全显著时 Java 数组越界崩溃——Python 复刻为等价 IndexError。
8. `FLOATERROR=1e-7`、compactprofiles2 加入/停止条件与 tie-break（max|value| 小者）逐行复刻。

### 2.5 命名与目录迁移

- 第 4 轮定案：品牌 **PySTEMTC**，PyPI/import/CLI = **`pystemtc`**（PyPI JSON API 实证 404；`stempy` 被 Kitware 4D-STEM 占用）。迁移 `src/stempy`→`src/pystemtc` 等，零行为变化（迁移后 96/96）。
- 用户将项目目录更名为 `D:\stem\pySTEMtc`：gen_fixtures Data_File 动态化、`test_golden.py::_resolve` basename 兜底、全部文档/HANDOFF 同步；冻结配置不动；迁移后 96/96 复跑通过（本报告 §2.3 数字即迁移后实测）。

## 3. 可以得出的结论

1. **M2 有条件 GO 的全部前置条件已满足**——按第 3 轮评审判据，M2 验收达成。
2. **Java v1.3.14 的离散决策结构已被完整复刻**：12 个配置横跨 3 种标准化 × 3 种校正 × 3 条置换路径 × 两种重复模式 × percentile 抬升 × 全排列/子抽样，Compatibility A 无一失败。任何 1e-15 级相关系数抖动导致的 assignment 翻转都会被字符串级断言抓住——没有发生。
3. **浮点纪律没有阻碍 exact 达成**：显式标量循环 + numpy 规约禁运的代价可接受，"先 golden 后优化"路线的前提成立。
4. **B 级实测超出要求**（打印值全等 vs 容差），spec §2 解冻区第 2 条的升级触发条件已满足，待专家确认后冻结为 exact strings。
5. **金标仍有 2 个已知覆盖缺口**：T≥9 且含缺失格的 on-the-fly 掩码路径（synth10 恰好无缺失）；JRE 17 环境下的 oracle 漂移未表征。均为 M3 事项，不阻塞当前结论。
6. **证据链在目录更名后完整**：冻结配置未动，历史路径前缀由解析兜底维护。

## 4. 遗留问题清单（请专家团给意见）

### 算法层

| # | 级别 | 问题 | 我的倾向 | 请专家裁决 |
|---|------|------|---------|-----------|
| N1 | P1 | **Compatibility B 冻结**：实测已达打印值全等，解冻区第 2 条触发条件成立 | 冻结为 exact strings（同 A 级判据方式），容差条款保留为兜底但不再使用 | 是否同意冻结？ |
| N2 | P1 | **T≥9 + 缺失格金标缺口**：on-the-fly 掩码路径（quirk ③ 所在路径）无金标覆盖 | M3 加 `c13_synth10_missing`（synth10 注入 ~8% 缺失，其余参数同 c11），重跑 stem.jar batch 生成参照 | 配置参数是否认可？是否需要额外覆盖 log 模式 × 缺失（quirk ③ 的 NaN 入中位数路径）？ |
| N3 | P2 | **性能包线**：on-the-fly 为纯 Python；此前实测样例级约 75s；3 万基因 × 50 置换 × 500 profile 量级估算到小时级（**未实测**）。优化必须走 D7 协议（先 golden 后优化） | V1 不优化、发布时如实标注性能特征；性能包线数据 M3 实测产出 | V1 可接受的性能包线是什么？目标数据规模（基因数×时间点×置换数）？若 V1.x 优化，专家建议优先方向？ |
| N4 | P3 | **JRE 17 漂移 characterization**：一次性 ~30min，预期无漂移则成为附加证据 | M3 做一次，结果只记录、不动 JRE 8 基准 | M3 做还是推迟到发布前？ |

### 架构层

| # | 级别 | 问题 | 我的倾向 | 请专家裁决 |
|---|------|------|---------|-----------|
| N5 | P2 | **无 VCS/CI**：项目当前不是 git 仓库，"浮点禁运 grep"只是文档化手工检查 | M3 init git + 最小 CI（pytest 全量 + 浮点禁运 grep；不依赖 Java，fixtures 入库） | 是否同意？涉及发布流程，请用户/专家定 |
| N6 | P2 | **CLI 设计面**：Java 原版无 CLI（GUI + `-b` batch），CLI 是无 oracle 可依的新设计 | `pystemtc run <data.tsv> -d <defaults.txt 兼容 config> --output <dir>`：config 文件优先（与 stem.jar -d/-b 键名对齐），flags 保持最小 | 与 `stem.jar -b` 对齐 vs Pythonic argparse，专家倾向？ |
| N7 | P2 | **to_csv（Compatibility C）范围**：batch 模式 Java 产 profiletable/genetable 两表；GUI 另有导出物。`filtered_genes` 的 reason 字符串无 Java 对应物 | V1 只复刻 batch 两表、逐字段一致（最后一列无条件输出）；reason 字符串不导出 | 范围是否认可？ |
| N8 | P3 | `result.to_dict()` schema（S2 carry-over） | M4 实现前请专家过目一次 | 评审时点确认 |
| N9 | P3 | warning 策略落地（A2/A4 carry-over）：`none_add0 × permute_t0=true`、legacy 有放回子抽样 | warning 只说明风险不改结果；metadata 已规划 `legacy_with_replacement`/`permutation_mode` 字段（§1.6） | 警示组合清单与措辞，M4 定稿 |

### 代码层

| # | 级别 | 问题 | 处置 |
|---|------|------|------|
| N10 | P3 | **Python 版本矩阵**：`requires-python>=3.10` 但只在 3.14.3 实测；numpy 2.4.6/pandas 3.0.3 在 3.10–3.13 的可得性未验证 | 发布前决定：补矩阵测试或收紧 requires-python |
| N11 | P3 | PyPI 发布前清单：`pystemtc` 实时复检占坑、LICENSE 文件、README/long_description（C2 carry-over） | M4 |
| N12 | P3 | 历史 `STEMpy/` 前缀的处置已定型（保留证据 + 解析兜底），后续会话不得当 bug 修 | 已记录于 HANDOFF D8 / spec §1.8，无需裁决 |

## 5. 下一步计划

1. **M3 验证收尾**（依 N1–N5 裁决）：① B 冻结写入 spec；② `c13_synth10_missing` 配置 + 重跑 batch + 金标扩展；③ JRE 17 漂移 characterization；④ 性能包线实测报告（真实外推数据替代估算）；⑤ git init + 最小 CI。
2. **M4 发布工程**：`pystemtc run` CLI（N6）；`to_csv`（N7）；`to_dict` schema（N8）；metadata timestamp（config 保持可 hash）；warning 策略（N9）；LICENSE/README/版本矩阵（N10/N11）；PyPI 实时复检后以 `pystemtc` 发布。
3. **V1.1**：K-means（`Random(2211)` + reservoir sampling）、plot adapter、`STEMInput.from_gene_matrix`。
4. 每步继续 light-rip 闸门流程（Medium：pre+post review；Large：planner→reviewer→implementer→verifier→reviewer）。

## 6. 评审包导读

包内只含需要专家过目的内容；完整工程在 `D:\stem\pySTEMtc`（96 测试可独立复跑）。建议阅读顺序与焦点：

| 文件 | 焦点问题（每文件一个） |
|------|----------------------|
| `docs/05_...md`（本报告） | §4 的 N1–N9 裁决项 |
| `docs/03_v1_implementation_spec.md` | §1.6 钉死语义是否与专家对 Java 的理解一致；§1.7 偏差记录是否可接受 |
| `verification/pytest_full_*.log` | 96/96 与 0-mismatch 的原始证据 |
| `src/pystemtc/permutation.py` | on-the-fly 生成（§1.6 钉死算法）与 Java :1148-1206 的逐行对应 |
| `src/pystemtc/significance.py` | binomialtail 边界 + FDR 走查（含全显著崩溃复刻）是否忠实 |
| `src/pystemtc/javaformat.py` | `doubleToSz` 与 U+FFFD 裁决的落地 |
| `src/pystemtc/profiles.py` / `assign.py` / `clustering.py` / `engine.py` / `result.py` | 抽查即可，不必逐行（A 级 12/12 exact 是主要保证） |
| `tests/test_golden.py` | 断言是否足以代表"Compatibility A exact + B 打印值全等" |
| `golden/java_configs/`（12 配置）+ `java_reference/` c01、c11 样例表 + `java_statutil/vectors.txt` | 参数网格覆盖面；c09/c10/c11 的历史路径前缀是**有意保留的证据**，不是错误 |

**可跳过**：M1 已评审过的模块（dataio/normalize/filtering/dataset/rng/_stats/config/errors）、docs/01/02/04、HANDOFF.md、全部测试夹具数据文件。

---

## 7. 第 5 轮专家裁决与 M3 执行记录（2026-09-19）

**门禁结论：M2 正式 GO。** M3 可以启动，顺序：修正 c13 设计 → 立即建 git+最小跨平台 CI → 其余收尾。不扩大 M3 范围。

### 7.1 裁决摘要

| 项 | 裁决 | 落点 |
|----|------|------|
| N1 | 同意冻结，但措辞改为两层：B-output（canonical fixtures 打印字符串 exact）+ B-internal（不承诺 bitwise，误差不得反噬 A 层）；禁止宣称全平台逐位一致 | spec §0（已写入） |
| N2 | **原方案驳回**：c11 `max_missing=0` 会过滤掉缺失行，永远到不了 masked 路径；必须确定性设计 + 测试侧分支到达断言；建议加 c14（log × spot 级基线缺失 × dup） | spec §1.9（已重设计钉死） |
| N3 | 只做 benchmark（genes/T/n_perms/profiles/wall/RSS 三档），不优化、不设拍脑袋 SLA | tools/bench.py + docs/06 |
| N4 | M3 做一次 characterization；JRE 8 仍是唯一 oracle | **阻塞：本机无 JRE 17**，待用户安装 |
| N5 | **同意且升级 P1 流程保障：继续 M3 前先做**；CI 覆盖 Windows+Ubuntu 同套 golden | 本轮执行（git+CI+基线提交） |
| N6 | CLI：`run` + `batch` 双入口，defaults.txt 一等输入，不复刻历史参数形式 | spec §2-8（M4） |
| N7 | V1 只复刻 batch 两表，认可；**不叫 `to_csv()`**（Java 实为 tab 分隔 txt），命名 `write_java_tables` | spec §0/§2-9（M4） |
| N8 | `to_dict` 升 P2，M4 实现**前**送审；须定义 schema_version/reference_version/非有限值编码（倾向 null） | spec §2-10（M4 前评审） |
| N9 | 仅 `none_add0+permute_t0=True` 弹 warning；legacy 有放回不逐次警告，metadata+文档承载 | spec §2-7（M4） |
| N10 | 发布前必须解决 Python 版本矩阵；numpy 2.4.6 本身要求 ≥3.11 | spec §2-11（M4/发布前） |
| N11 | PyPI 发布前实时复检；LICENSE 不要拖到最后，评审包携带 GPL-3.0 文本 | 本轮 LICENSE 落库 |
| N12 | 已冻结，禁止再当 bug 折腾 | 关闭 |

### 7.2 新发现的 2 个 P2（评审从代码中查出，M3 顺手修）

1. `test_golden.py` 的 "Profile ID exact" 实断言 `str(i)` 而非 `str(rec.id)`——engine 现恰好 `id=i`，M2 结论不受影响；已改为 `str(rec.id)`，今后真正保护该字段。
2. `legacy_with_replacement` 仅 `subsample_universe` 为 true，但 `on_the_fly` 同属跨置换可重复的有放回抽样；语义改为 `mode != "exact"`（false/true/true）。

### 7.3 c13/c14 重设计要点（第 5 轮评审 + pre-work review 双重修正）

- c13：T=10、新文件 synth10m.txt（300 spots）、确定性缺失（行 i%3==2 在 0 基索引 (i%9)+1 置空、t0 永不缺）、`max_missing=1`；目标 = on-the-fly 合法性检查（:1223）+ masked correlation。
- c14：T=6、synth6d.txt（100 dup 对 + 40 单 spot、全正值）、组 1 空格（log(0)=−Inf → vals 得 +Inf → 中位数 +Inf → sqrt(NaN) → dcorr=NaN 跳过）、组 2 负值（loader 记缺失保留负值 → log(负)=NaN 进中位数）、`permute_t0=true`（universe=720 而非 120——120 蕴含 permute_t0=false，会使 quirk 永不触发）、`max_missing=1`。
- 生成：`gen_fixtures.py --fixtures ...` 增量 + **scratch 目录模式**批跑（执行期实证：单文件 `-b` 会把完整输入路径嵌入输出名而静默失败，ST.java:2947/:2989；整目录重跑则因 c09/c10/c11 历史前缀 FileNotFoundException 被静默跳过）；c01-c12 参照表根本不碰。
- 断言：permutation_mode、幸存基因中带缺失者的数量下限（见 spec §1.9）。
