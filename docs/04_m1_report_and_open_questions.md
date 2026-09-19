# STEMpy M1 结题报告与遗留问题清单（供专家团评审）
（品牌注记，2026-09-19：品牌自 2026-09-19 起写作 pySTEMTC（py 小写、STEM 大写、tc 小写）；文中 PySTEMTC 为当时记录）

> 命名迁移注记（第 4 轮，2026-09-19）：项目正式定名 **PySTEMTC**（PyPI/import/CLI = `pystemtc`）。本文为 M1 阶段历史记录，保留当时"STEMpy"称谓；现行命名与最高原则以 `03_v1_implementation_spec.md` §0 为准。

- 日期：2026-09-19
- 范围：第 2 轮评审后的 3 个 P1 修正 → 金标 fixtures → M1 实现 → 三道闸门（实现自验 / 独立验证 / post-review）→ findings 修复
- 评审包：`D:\stem\STEMpy_review_20260919_170951.zip`（精选内容，见 §6 导读）

---

## 1. 一段话总结

按第 2 轮评审要求，先修正 3 个 P1（其中"≤8 时间点=精确检验"确认为我的事实错误，已按源码改写），随后生成了 12 配置的 Java batch 金标 fixtures 和 680 条真实 `java.util.Random` 向量，把 V1.0 implementation spec 钉死并过预审（预审又抓出 2 个 MAJOR 的 spec 错误并修正），然后由 implementer 完成 M1（读取→标准化→重复合并→过滤链 + Java RNG 逐位复刻），独立 verifier 复跑全部验证（RNG 680/680 逐值一致；c01 金标 2137/2137 行字符串级一致），post-review 判 GO 并提出 6 条 MINOR，全部修复后扩展集成对拍到 5 个配置，最终 **52/52 测试通过**。核心算法（profile/置换/显著性/聚类）按计划属于 M2，尚未实现、尚未验证。

## 2. 本轮做了什么（可回溯）

| 步骤 | 产出 | 证据 |
|------|------|------|
| P1 修正 | 3 个 P1 全部落入两份文档（16 处编辑） | `docs/01` §一/二、`docs/02` A7/B3/B4 |
| 置换机制核验 | T<9 物化 universe + **每基因独立、有放回**子抽样（:1148-1168）；默认 50 次精确边界 T≤4（置换 t0）/ T≤5（固定 t0） | `STEM_DataSet.java:1043-1168` |
| 金标 fixtures | 12 配置 batch 运行（24 张表）、680 条 jjs RNG 向量、2 个合成数据集 | `tests/golden/`（时间戳 14:10:05-10，一次性生成，实现阶段未被触碰——verifier 已核验 mtime） |
| spec 预审 | GO + 2 MAJOR：①`genespottimedata` 引用别名语义（重复组主行=合并后中位数、其余行=合并前标准化值）；②`sortedcorrvals` 是**过滤前全部** dup-merged 基因的升序表 | 修入 `docs/03` §1.2 |
| M1 实现 | 9 个源码模块 + 3 个测试文件 + pyproject（GPL-3.0），约 72KB | `src/stempy/`、`tests/` |
| 独立验证 | RNG 4 种子 680/680 exact（含 nextInt 溢出路径对真实 JVM 对拍）；c01 全列字符串级一致；fixtures 完整性；零 GUI 依赖；零 TODO/污染 | verifier 报告（ALL GREEN） |
| post-review | GO + 6 MINOR（`Double.parseDouble` 空白/d 后缀、NaN→U+FFFD、DataFrame NaN spot 抛错、样例数据入包、集成扩展、冗余 import） | 全部修复，52/52 |

## 3. 现在可以下的结论（观察 → 推断）

- **C1（观察→结论）**：`java.util.Random` 可在 Python 中逐位复刻——4 个种子 × 170 个值全部 `==` 一致，含 nextInt 拒绝采样的 int32 溢出路径（对真实 JRE 8 对拍）。⇒ 置换索引、profile 抽样、（V1.1 的）K-means 初始化的随机性**不构成**对拍障碍。
- **C2（观察→结论）**：M1 数据链（解析→三模式标准化→重复基因中位数合并→两种重复模式合并→重复相关过滤→缺失过滤→阈值过滤）在 **5 个配置**（c01 基准 / c03 log / c04 add0 / c07 同一时段 / c08 无重复）上与 Java genetable **逐行逐格字符串级一致**（行数 2137 / 3496 / 3107 / 2862 / 2948）。⇒ 数据入口层与 Java v1.3.14 等价性已有强证据；genetable 不含 profile/p-value 列，故此结论**不外推**到核心算法。
- **C3（观察→推断）**：exact-match 验收在工程上成立——batch 模式可无人值守生成金标、随机性可复刻、格式化（`NumberFormat` HALF_EVEN / 千分位 / `-0.00`）可精确复刻。唯一原则性边界是浮点 transcendental 的跨平台末位差（Level B 分层的依据）。
- **C4（过程证据）**：评审流水线有效——两轮共抓出 5 个会被写进代码的高危错误（3 个 P1 + 2 个 MAJOR），全部发生在写代码之前或 Golden 对拍之前。
- **C5（观察）**：已建立 9 项 quirk 复刻清单（有放回置换子抽样、percentile 对全长预过滤表索引、genetable 最后一列无条件输出、引用别名存储、`FLOATERROR=1e-7`、`Util.getmedian` 偶数取均值、probe `;` 连接、log 模式 ≤0 只清 pma、`NumberFormat` HALF_EVEN），全部有源码行号。

## 4. 尚不能下的结论（如实声明）

1. **核心算法链的正确性**：候选 profile 生成/精选、基因分配、置换 expected counts、binomial tail p 值、显著 profile 聚类——M2 才实现，M3 才对拍（24 张 profiletable 一张都还没比过）。
2. **Java 自身跨 JRE 稳定性**：`Math.exp/log/pow` 在 JRE 8 vs 11/17 是否产生不同 p 值——**未测**。当前金标钉死 JRE 1.8.0_451。
3. **性能与内存可扩展性**：未做基准（Java 原版同样全内存）。
4. **PyPI 包名 `stempy` 占用情况**：未查证（M4 任务）。
5. **on-the-fly 置换生成段（T≥9）**：仅核对骨架，未逐行验证（c11 fixture 已备好，M2 对拍兜底）。

## 5. 遗留问题清单（请专家团给意见）

### 算法层

| # | 级别 | 问题 | 我的倾向 | 请专家裁决 |
|---|------|------|---------|-----------|
| A1 | P1 | **Level B 判据与金标 JRE 钉死**：transcendental 跨 JVM 不保证末位一致。方案：(a) 金标永久钉 JRE 1.8.0_451；(b) Level B 主判据=与 Java 打印字符串一致；(c) 数值容差兜底（M2 首批对拍后定值） | 接受 (a)+(b)+(c) | 是否同意？是否需要额外测一次 stem.jar 在 JRE 17 下的输出漂移（成本约半小时）？ |
| A2 | P2 | **有放回置换子抽样的统计语义**：重复排列被重复计数，有效样本量 < n_perms。复刻无疑，但用户文档是否要警示该 quirk 的统计后果 | 复刻 + 文档警示 | 是否同意在文档中显式警示（而非沉默复刻）？ |
| A3 | P1 | **binomialtail 边界未核清**：observed count 因并列 1/k 累加可为非整数，Java 取 `(int)ceil(count−1)`；count=0 时参数为 −1，`StatUtil.binomialtail(−1, n, p)` 行为我**还没读码确认** | M2 开工前逐行核对 StatUtil.java:286-336 及调用点 | 无需裁决，列入 M2 前置任务；若专家熟悉该实现可直接给结论 |
| A4 | P2 | **add0 × permute_t0=true 交互**：合成 0 列会被置换移动，输出可能有统计意义问题（Java 照算） | 照复刻 + 文档标注"不推荐组合" | 是否需要在文档/CLI 层面加警告？ |
| A5 | P2 | on-the-fly 置换段（T≥9）未逐行验证 | c11 金标对拍兜底 | 无需裁决 |
| A6 | P3 | K-means reservoir sampling（V1.1）的 RNG 流顺序 | 实施时重读 | 无需裁决 |

### 架构层

| # | 级别 | 问题 | 我的倾向 | 请专家裁决 |
|---|------|------|---------|-----------|
| S1 | P2 | **内存规模**：全量保留 spot 级 + repeat 级序列（Java 同为全内存）。样例 2.4 万 spot 无压力；现代数据 50 万 spot × 多重复会到 GB 级 | V1 对齐 Java 不做 lazy；V2 再评估 memmap/zarr | 是否存在已知的超大输入场景需要 V1 就支持？ |
| S2 | P3 | `result.to_dict()` schema 是 agent/MCP 的消费接口 | M4 前请专家过目一次 | 谁来定 schema 评审时点 |
| S3 | P3 | `rng="numpy"` 模式与金标不兼容 | 保留 + 文档强标注 | 去留 |
| S4 | P2 | PyPI 名 `stempy` 占用未查证 | M4 首日核查 | 备选名优先级 |

### 代码层

| # | 级别 | 问题 | 处置 |
|---|------|------|------|
| C1 | P3 | Unicode trim/upper 与 Java `trim()/toUpperCase(ENGLISH)` 在 NBSP 等字符上不同；表头空 token 时 Python 报错比 Java 崩溃更友好 | 接受现状，已记录 |
| C2 | M4 | LICENSE 文件、config 全键解析、CLI、`to_csv`（注意最后一列无条件输出） | M4 |
| C3 | M3 | 集成对拍覆盖 5/12 配置；c02/c05/c06 的 genetable 预期与 c01 同构（仅校正/t0 参数不同），M3 全量对拍；profiletable 全部依赖 M2 | M3 |
| C4 | — | post-review 6 MINOR 已全部修复，无未清项 | 本轮已完成 |
| C5 | P3 | "禁用 np.sum 于金标路径"目前靠 review 纪律 | 建议 M2 起加 CI grep 检查 |

## 6. 下一步计划

| 阶段 | 内容 | 完成判据 |
|------|------|---------|
| **M2**（下一步） | 前置核清 A3/A5 → profiles（枚举+抽样+compactprofiles2，FLOATERROR=1e-7）→ assign（并列 1/k）→ permutation（三条路径：全排列精确 / universe 子抽样 / on-the-fly）→ significance（binomialtail + 三种校正）→ clustering（贪心球）→ engine 串联 | **Level A 全 exact**：12 配置 profiletable 全字段（Profile ID / Model / Cluster / # Genes Assigned）+ genetable Profile 列对拍通过 |
| **M3** | Level B 容差定稿（M2 首批对拍数据）；p-value 打印字符串一致性；金标全绿 | 24 张表全部达标；A1 判据冻结 |
| **M4** | config 全键 + CLI + result.to_dict/to_csv + LICENSE + PyPI 核查 + 打包 RC | `pip install` 后 CLI 复现样例分析 |
| V1.1 | K-means（seed 2211 + reservoir sampling）、plot、from_gene_matrix | K-means 金标 |

每阶段继续执行既定闸门流程：预审 → 实现 → 独立验证 → post-review。

## 7. 评审包导读（`D:\stem\STEMpy_review_20260919_170951.zip`）

精选原则：只装"专家需要亲自核对的东西"。**未打包**：Java 源码（专家可用本地 `D:\stem\sourcecode` 或 GitHub `jernst98/STEM_DREM`）、其余 19 张金标表、合成数据、stem.jar（按需另发）。总大小约 200KB。

| 优先级 | 文件 | 看什么 |
|--------|------|--------|
| 1 | `docs/04_m1_report_and_open_questions.md` | 本文件，重点是 §5 裁决请求 |
| 2 | `docs/01_expert_plan_review.md`、`docs/03_v1_implementation_spec.md` §1.2 | 3 P1 + 2 MAJOR 的修正记录；数据契约 |
| 3 | `src/stempy/filtering.py` → `rng.py` → `_stats.py` → `tests/test_integration_fixture.py` | 按此顺序抽查：存储时点约束 / LCG 复刻 / 求和顺序 / 验收判据与 NumberFormat 复刻 |
| 4 | `evidence/`：`vectors.txt`（可抽几行对本地 java 验证）、`c01_*_genetable/profiletable`、`_batch_stdout.log`、`pytest_report.txt` | 验收证据；profiletable 仅供预览，M3 才对拍 |

复现命令（任一装有 Python 3.10+ 的机器）：解压后 `pip install -e . && python -m pytest -q`（需 `tests/golden/` 完整目录，包内只带子集，完整版在 `D:\stem\STEMpy`）。
