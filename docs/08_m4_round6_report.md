# pySTEMTC M4 第 6 轮执行报告与遗留问题清单（供专家团评审）
（品牌注记，2026-09-19：品牌铁律第 6 轮定案——py 小写、STEM 大写、tc 小写，写作 pySTEMTC；PyPI/import/CLI = `pystemtc` 全小写不变。历史文档 docs/01/02/04-07 中的 PySTEMTC 为当时记录，按 D12 不做追溯改写、以顶部 dated 注记为准。）

- 日期：2026-09-20
- 范围：第 6 轮裁决的完整执行——(a) P1 阻塞修复（STEMResult 丢失 Java genetable 末列载荷）；(b) to_dict schema v2 + stage timing；(c) 打包/CI/依赖下界/文案（M4/M6/M8）；(d) 品牌铁律清扫；(e) `benchmarks/benchmark_core.py` 按专家原案建成并跑完核心组。门禁全流程：planner → pre-work review（GO-with-changes，2 P1 / 5 P2 / 8 P3 全部吸收）→ 实现（先红后绿）→ **verifier 独立复核 10/10 PASS** → **post-work review APPROVE** → 4 项发现全部处置 → 136/136。**第 7 轮修订注记（2026-09-20）**：专家团裁定 schema v2 的 `present=True ⇒ state=="finite"` 方向不变量**写错**（实现与测试一直证明 `present` 与 `value_states` 正交）；同时 B6 因果归因**不成立**（B5→B6 同时发生 on_the_fly permutation 与 candidate-profile sampling 两个路径切换，profile_generation=20.6 s 属候选采样，872.5 MiB 无阶段级内存测量无法归因）。两处已在 §1/§2.3/§2.4 钉正：spec 03 §1.10 改为正交合同（10 格真值表 + 参数化测试钉死）；本报告 §1 段与 §2.4 解读重写；新增 B9 = 10k×9T 隔离 bench（专家点名的路径拆分诊断点）。**round-7.1 收口注记（2026-09-20）**：专家团复核发现 §3.4 仍带"sample-1M 主项 +589 MiB" 单因素归因 + "Java 同样有 ~870 MiB" 跨语言暗示 + "改参数=破坏 Java 兼容性" 措辞不当。三处已降级为描述性陈述：`time points` 单列为实验输入结构；B9 定位为 **transition diagnostic point**（非 clean path isolator）；跨语言 RSS 比较已删除。**146/146 测试通过**（136 + 10-cell 正交矩阵）。

---

## 1. 一段话总结

第 6 轮裁决全部执行完毕。P1 阻塞修复：STEMResult 丢失 Java genetable 末列载荷的根因，是 Python 侧对**无重复数据集**也无条件执行了零初始化的 cellwise 中位数合并，而 Java 在无 repeat 时**从不调用 mergeDataSets**（different_periods 直接 `theDataSetsMerged = theDataSet1`，ST.java:2577；same_period 是纯引用别名包装，ST.java:2669）——修复为直通分支（`if not repeats: return main`），先红后绿，新增的 14 配置全字段值列金标测试证明 A 层零反噬。to_dict schema v2（11 顶层键、`profile_ids: list[int]`、value_states 真值表 + **正交合同**修订、config/input 分离、timestamp 单次生成）与 8 键 stage timing 落地。`benchmarks/benchmark_core.py` 按专家原案建成（B1-B9 专家网格 + n_permutations 扫描组 + 重复组），核心组实测：**wall 0.66 s（1k×5T）→ 51.0 s（10k×10T），peak RSS 76.2 → 872.5 MiB**；置换阶段在 B1–B5 占 85–95%，**B6 是 T=10 默认配置下的高资源形态，同时发生 on_the_fly permutation 和 candidate-profile sampling 两个路径切换**（T=10 时 `5^9 = 1,953,125` 越过 candidate_cap=1,000,000 进入采样路径），当前 benchmark 没有阶段级内存测量，**无法单独把 873 MiB peak RSS 归给 on_the_fly**。Python 与 Java 内存布局不同，跨语言 RSS 量级不直接可比——本报告只给本机 Python 测量值，不对照 Java RSS。M3 冻结证据的 ~870 MiB 是历史 M3 bench.py 在同窗口同 Python 环境下的独立 Python 路径测量，二者属于同一实现路径不同时间的实测一致性，不是"Java 也同样如此"的暗示。**资源预算提示**（round-7.1 专家原话）：在当前 Windows benchmark 中，10,000 spots × 10 time points、默认兼容参数下观察到约 873 MiB peak RSS。资源受限环境建议先用代表性数据进行 benchmark。**为复现某次 Java STEM 分析，应保持输入与算法参数一致；仅为降低资源消耗而修改 `time points`、`max_unit_change`、`candidate_cap` 或 `n_permutations` 可能改变分析结果，因此修改后的结果不应再与原参数 Java run 直接比较**。注意：`time points` 本身首先是**实验输入结构**（与 spot 数同层），不应与 `max_unit_change` / `candidate_cap` / `n_permutations` 这些算法参数简单混称。单机 benchmark 未给出 V1.0 必须先优化的理由。**146/146 测试通过**（136 + 10-cell 正交矩阵）。

## 2. 结果总结

### 2.1 第 6 轮裁决执行清单

| 裁决项 | 状态 | 证据 |
|----|------|------|
| M0 命名铁律 pySTEMTC（py 小写/tc 小写/STEM 大写） | 完成 | `src/ pyproject.toml tests/*.py benchmarks/` 命中数 = 0（verifier 独立 grep）；docs/01-07 顶部 dated 注记 + HANDOFF 标题改写；2 个冻结文件内的残留列入解冻申请（§4） |
| P1 阻塞：末列载荷保真（先测后改 write_java_tables） | 完成 | 根因链见 §2.2；c14 四行 + c13 phantom 回归测试；14/14 金标值列逐格 |
| M1 to_dict schema v2（4 项修改 + timestamp 单次）+ **正交合同修订（round-7）** | 完成 | §2.3；`tests/test_result_schema.py` 21 测试（11 原有 + 10 参数化正交矩阵）；strict JSON（allow_nan=False）实测；spec 03 §1.10 改为正交合同 |
| M2/M3/M5/M6/M8 冻结落盘（writer C 定义、CLI 0/1/2、warning 逐字、文案红线、发布模板） | 完成 | spec 03 §0 三条新冻结 + §1.10；docs/06/07 修正注记（870 MiB 事实性陈述，无"跨平台已验证"类宣称） |
| M4 打包：requires-python ≥3.11 + 依赖下界 + CI matrix | 完成 | pyproject（numpy>=2.4,<3、pandas>=3.0,<4，provisional 至 3.11 CI 绿）；ci.yml 3.11/3.12/3.14 × ubuntu/windows，push 后生效 |
| benchmark harness 建成 + 核心组全跑（含 B9 路径隔离点） | 完成 | §2.4；执行期修正：implementer 初版网格偏离专家原案（丢 30k×5、sweep 扫错变量），主会话已纠正为 B1=1k×5 … B6=10k×10T、sweep 扫 n_permutations；round-7 新增 B9=10k×9T（on_the_fly + enumerate 交集，路径拆分诊断点） |
| M4 首批三实现（write_java_tables / CLI run+batch / M5 warning 实现） | 未开始 | 按第 6 轮门禁顺序属下一批（§5） |

### 2.2 P1 阻塞修复：末列载荷保真

**症状（专家发现）**：c14 的四行 S_0003/S_0015/S_0027/S_0039，Java genetable 末列打印 `-∞`，而 `STEMResult` 的 `values[-1]` 是 `0.0`——两层数据都错了（B-output 值错，A 层载荷错）。

**根因链**：`build_stem_dataset` 无条件调用 `merge_repeats(gt_main, [], mode)`（dataset.py:146）→ `_cellwise_median` 对 `mergedata` **零初始化**（DataSetCore.java:794-828 的忠实复刻）→ 只要有 repeat 参与这是正确的（Java 同样如此），但**无 repeat 时 Java 根本不进这条路**：different_periods 直接引用主表（ST.java:2577），same_period 是 `new STEM_DataSet(theDataSet1, theDataSet1)` 纯别名（ST.java:2669）→ Java 里全缺失格保留主表归一化后的存储值（`averageAndFilterDuplicates` 只在 nvalindex>0 时覆写，DataSetCore.java:707-712）→ Python 侧的零初始化矩阵把 `log(0)=−Inf` 载荷重写成幻影 `0.0`。

**修复**：`merge_repeats` 首行直通 `if not repeats: return main`（两种模式共用；模式校验提升到直通之前，未知 mode 的契约不收窄）。**为什么是直通而不是专家字面上的"另加载荷通道"**：影子通道只救末列渲染，矩阵本体仍与 Java 不一致——Java 的置换链本来就在携带这些载荷的矩阵上跑（置换可把非零 pma 移到载荷格上）；直通让 Python 矩阵与 Java 自身对齐，偏差理由完整记录于 spec 03 §1.7。

**先红后绿证据**：修复前 2 个新 payload 回归测试红（c14 四行 `values[-1]` 为 0.0 ≠ −inf；c13 GENE_0008 为 0.0 ≠ 0.948）→ 修复后绿；**14/14 金标配置（c01–c14）全字段值列逐格比较全过**，证明直通对 A 层零反噬（verifier 另以位级掩码对比确认 masks 不变、present 格值不变）。

### 2.3 to_dict schema v2（第 6 轮 M1 四项修改全落地）

| 修改项 | 落地 |
|----|------|
| `profile_ids: list[int]` | 替代原 `profile: str`；S_0003 → `[7]` 有测试 |
| value_states 真值表 + **正交合同（round-7 修订）** | `present` 与 `value_states` 两个维度**正交**：`present` 是 Java pma 唯一权威位，由 `GeneAssignment.present` 字段独立报出；`value_states` 只回答"存储 double 的 payload 类别"，**非有限 payload 与 present 无关**——NaN/+Inf/−Inf 在 `present=True/False` 下都报对应非有限态且 values=null；finite+present=True → `"finite"`；finite+present=False → `"missing"`（填充载荷保留）。**禁止**写成 `present=True ⇒ state=="finite"`（实证：`_encode_value(math.inf, True) == ("positive_infinity", None)`、`_encode_value(-math.inf, True) == ("negative_infinity", None)`；c14 行 `present=False ∧ −Inf` 报 `"negative_infinity"`）。`value_states` 字段名保留（round-7 专家否决改名"missingness_state"），含义"value 的状态"，与 present 各司其职。10 格真值表 `tests/test_result_schema.py` 参数化钉死。 |
| config/input 分离 | config = 18 个显式算法键（枚举自 STEMConfig，JSON 可序列化，不做"hashable"宣称）；input = data_file / repeat_files / time_points / input_form |
| timestamp 单次 | `engine.fit` 内生成一次存 metadata，`to_dict` 只拷贝；两次调用全等有测试 |

顶层 11 键：`schema_version(=2), reference, generator, config, input, metadata, profiles, gene_assignments, filtered_genes, clusters, timing`。`json.dumps(result.to_dict(), allow_nan=False)` 对 c13/c14 及活体小样本实测通过。timing 8 键（perf_counter）：input_read / normalize_filter / profile_generation / assignment / permutation / significance / clustering / wall。

### 2.4 核心组 benchmark 实测（专家网格 + B9 transition diagnostic + candidate_path 列，2026-09-20T04:45Z）

环境：Windows-11 / Python 3.14.3 / numpy 2.4.6 / pandas 3.0.3；seed 20260919；warm-up 1 + formal 3 取 **median**（min/max 保留，从不平均）；每 (bench,run) 独立子进程隔离，peak RSS 为进程单调值（Psapi PeakWorkingSetSize）。记录：`benchmarks/results/20260920T044548Z/`（CSV 36 行 + MD；CSV+MD 表均含 `candidate_path` 与 `candidate_universe` 两列）。

| bench | 规模 | 存活基因 | 置换模式 | 候选空间 `5^(T-1)` | 候选路径 | wall median (s) | peak RSS (MiB) |
|---|---|---|---|---|---|---|---|
| B1 | 1 000 × 5T | 892 | subsample_universe | 625 | enumerate | 0.71 | 76.5 |
| B2 | 5 000 × 5T | 4 478 | subsample_universe | 625 | enumerate | 4.61 | 81.8 |
| B3 | 10 000 × 5T | 8 962 | subsample_universe | 625 | enumerate | 11.22 | 87.4 |
| B4 | 30 000 × 5T | 26 878 | subsample_universe | 625 | enumerate | 38.03 | 110.9 |
| B5 | 10 000 × 8T | 9 000 | subsample_universe | 78 125 | enumerate | 19.77 | 119.3 |
| **B9** | **10 000 × 9T** | **9 000** | **on_the_fly** | **390 625** | **enumerate** | **30.42** | **283.5** |
| B6 | 10 000 × 10T | 9 000 | on_the_fly | 1 953 125 | sample 1M | 50.50 | **872.7** |
| B7 | 10 000 × 5T + 2 repeats | 4 027 | subsample_universe | 625 | enumerate | 4.82 | 95.3 |
| B8 | 10 000 × 10T + 2 repeats | 4 203 | on_the_fly | 1 953 125 | sample 1M | 40.58 | 879.9 |

各阶段（median，秒）：

| bench | input_read | normalize_filter | profile_generation | assignment | permutation | significance | clustering |
|---|---|---|---|---|---|---|---|
| B1 | 0.005 | 0.005 | 0.011 | 0.038 | 0.637 | 0.008 | 0.000 |
| B2 | 0.025 | 0.029 | 0.011 | 0.194 | 4.261 | 0.080 | 0.000 |
| B3 | 0.048 | 0.053 | 0.011 | 0.385 | 10.528 | 0.159 | 0.000 |
| B4 | 0.146 | 0.153 | 0.011 | 1.167 | 35.990 | 0.477 | 0.000 |
| B5 | 0.066 | 0.072 | 1.780 | 0.527 | 17.117 | 0.161 | 0.000 |
| **B9** | **0.075** | **0.081** | **3.365** | **1.106** | **25.571** | **0.160** | **0.000** |
| B6 | 0.081 | 0.086 | 20.298 | 1.249 | 28.417 | 0.155 | 0.000 |
| B7 | 0.144 | 0.191 | 0.011 | 0.174 | 4.203 | 0.073 | 0.000 |
| B8 | 0.243 | 0.328 | 20.563 | 0.673 | 18.549 | 0.074 | 0.000 |

**B9 transition diagnostic（round-7.1 描述性定位）**：B5（subsample + enumerate）→ B9（on_the_fly + enumerate）→ B6（on_the_fly + sample 1M）的两个相邻跃迁**同时改变了多个量**，不是干净的因果隔离实验：

- **B5 → B9 同时变化**：T 8→9、candidate 向量长度、candidate universe 78,125→390,625（5×）、permutation 路径 subsample→on_the_fly；wall 19.77→30.42 s（+10.65 s）、profile_generation 1.78→3.37 s、assignment 0.53→1.11 s、peak RSS 119.3→283.5 MiB（+164.2 MiB）。
- **B9 → B6 同时变化**：T 9→10、candidate 向量长度、candidate universe 390,625→1,953,125（5×）、candidate 路径 enumerate→sample 1M；wall 30.42→50.50 s（+20.08 s）、profile_generation 3.37→20.30 s（+16.93 s）、assignment 1.11→1.25 s、peak RSS 283.5→872.7 MiB（+589.2 MiB）。

**因此 B9 与 B6 的 RSS 增量无法单独归因于某一条路径切换**——当前 benchmark 只有整个 worker 的 peak RSS（Psapi PeakWorkingSetSize），没有 stage-level memory 探针；Python 对象 / NumPy 数组与 Java 数组的内存布局不同，跨语言 RSS 量级比较也不直接可比。round-7.1 专家明确将 B9 定位为 **transition diagnostic point**，**不接受**"clean path isolator / clean causal decomposition"。

**时间证据相对更稳**：B9 profile_generation = 3.4 s、B6 profile_generation = 20.9 s，profile-generation 阶段在 T=10 配置下出现明显时间跃升，并与 candidate 路径从 enumerate 转为 sample-1M 同时发生（同一时刻）。这是描述性观察，不是 B6 = "candidate sampling 造成 +589 MiB" 的单因素归因。

**重复路径（B7/B8 vs B3/B6）**：
- B7（10k×5T+2 repeats）wall 4.82 s / 95.3 MiB vs B3（10k×5T no-repeat）11.22 s / 87.4 MiB：B7 wall 更短，因为 repeat-corr filter 把存活基因从 8 962 砍到 4 027（−55%），permutation 阶段工作量减半；RSS 微增 +7.9 MiB。
- B8（10k×10T+2 repeats）wall 40.58 s / 879.9 MiB vs B6（10k×10T no-repeat）50.50 s / 872.7 MiB：B8 wall 也更短（permutation 18.55 vs 28.42 s），RSS 微增 +7.2 MiB；filter 后存活基因 4 203 vs 9 000。
- repeat-corr filter 的早裁剪显著降低 permutation 阶段墙钟时间，但 RSS 总量仍由 sample-1M 路径形态主导——这是 B8 与 B6 RSS 几乎相同的事实观察，不是"B6 RSS 主项归 sample-1M" 的因果声明。

**其它观察**：
- B1–B4 permutation 阶段占 80–95%（STEM 算法本身以置换为计算主体）；B4（30k×5T）39 s 印证 M3 报告"3 万基因分钟级"外推。
- 基因数放大（B1→B4，30×）带来 wall 约 53×，超线性但在单机可接受包络内；本报告不做原因归因，留待优化轮（若有）。
- sweep 组（n_permutations ∈ {10,50,100,500,1000} @ 10k×8T）已建成但未跑——round-7 专家裁决："V1.0 已明确不优化发布，其决策价值有限；等后续真讨论 permutation 性能优化时再跑完整 sweep 更合适"。
- 执行期修正记录：implementer 初版把 B 网格改成 300×6/1k×10/3k×10/3k×6/10k×6/10k×10（丢了专家点名的 30k×5 与 5k×5）且 sweep 误扫 max_model_profiles；主会话对照专家原文纠正为上述网格并复测。round-7 新增 B9 = 10k×9T。

### 2.5 双重评审结果与处置

**verifier（独立复核，10 项检查全 PASS）**：全量 pytest 136 passed 独立复跑；冻结文件零触碰（tests/golden/**、tools/bench.py、tools/gen_fixtures.py、.gitattributes 的 diff 为空）；品牌 grep 代码面 0 命中；P1/schema v2/benchmark/打包锚点逐项 file:line 确认；benchmark 记录内部一致（MD 的 median 从 CSV 重算吻合）；B6 872.5 MiB ≈ 冻结证据。唯一 WARN = HANDOFF.md 标题大小写（已修）。

**post-work review（新视角对抗审查，APPROVE）**：无 P1。1 P2 + 3 P3，全部处置：

| # | 级别 | 发现 | 处置 |
|---|------|------|------|
| 1 | P2 | benchmark scratch 文件名不含 seed——换 `--seed` 重跑会静默复用旧数据、记录头却标新 seed | 已修：scratch 文件名嵌入 seed；既有记录用的正是默认 seed，内容仍然诚实，无需重跑 |
| 2 | P3 | 品牌残留于 3 处：HANDOFF.md 标题（活文件）、tests/golden/README.md:3、tools/gen_fixtures.py:1（冻结文件） | HANDOFF 已修；两个冻结文件按红线不触碰，列入 §4 解冻申请（仅文档字符串，不涉 fixture 字节） |
| 3 | P3 | `result.py` 死常量 `_NON_FINITE_STATES` | 已删 |
| 4 | P3 | 直通分支使 `merge_repeats(main, [], "bogus")` 不再抛 unknown mode | 已修：模式校验提升到直通之前 + 新测试；136/136 |

## 3. 可以得出的结论

1. **兼容性合同未被本轮破坏**：14/14 金标（c01–c14）在 P1 修复后全字段值列逐格全过——本轮的 A 层承诺从"表结构/打印值一致"升级为"值列逐格一致"，c14 的 −∞ 载荷自 Java 侧到 Python 数据结构全程可达。
2. **schema v2 是对既有 `to_dict` 的 pre-release 重定义**（第 6 轮裁决定性），按正交合同（round-7 修订：`present` 与 `value_states` 正交，非有限 payload 不论 present 都报对应非有限态）落地；strict JSON 实测通过，21 个 schema 测试钉死（含 10 格参数化正交矩阵）。
3. **单机 benchmark 未给出 V1.0 必须先优化的理由**（措辞遵 M8 修正注记）：1k→30k 基因 wall 0.66→39 s，10k×10T 51 s；内存上界由 B6 的 873 MiB 界定，发布文案按"未优化 + 事实性 870 MiB"模板执行。资源预算提示只写事实与测量建议：仅为了降低资源消耗而修改 `time points` / `max_unit_change` / `candidate_cap` / `n_permutations` 可能改变分析结果，修改后的 PySTEMTC 结果不应再与原参数 Java run 直接比较——它们是两次不同的分析，而非"破坏 Java 兼容性"。
4. **性能画像可用于优化轮的地基**：置换阶段主导（B1–B5 占 85–95%）。T=10 配置下 profile-generation 阶段出现明显时间跃升（B9→B6，3.4 → 20.9 s），并与 candidate 路径从 enumerate 转为 sample-1M 同时发生；peak RSS 在 B6（10k×10T）达 873 MiB、在 B8（10k×10T+2 repeats）880 MiB——两个都落在 sample-1M 形态。但当前 benchmark 只有 worker peak RSS、没有 stage-level memory 探针，**B5→B9→B6 的 RSS 增量无法严格分解为单一路径切换的因果**（每次跃迁同时改变 T、candidate 向量长度、universe 大小、permutation/candidate 路径）。B9 是 **transition diagnostic point**，不是 clean path isolator；任何优化都必须走 golden → optimize → golden（D15），本轮不动。
5. **流程收敛**：round-6 verifier 10/10 + post-review 无 P1，4 项发现当日处置；round-7 expert 复核发现 2 P1（schema 方向不变量写错 + B6 因果归因），已修；**146/146 绿**。

## 4. 遗留问题清单（请专家团给意见）

- **M4 剩余顺序确认**（当前计划，可调整）：① `write_java_tables`（Compatibility C：∞/U+FFFD 渲染、平台默认字符集 + `encoding=`、末列无条件渲染、`format_java_double` 晋升 src）→ ② CLI `run`+`batch`（退出码 0/1/2、batch 失败继续、M5 warning 逐字实现）→ ③ push + CI 绿 → ④ 依赖下界冻结 → ⑤ PyPI 发布。是否同意此序？
- **两个冻结文件的品牌残留解冻申请**：`tests/golden/README.md:3` 与 `tools/gen_fixtures.py:1` 的文档字符串仍是 PySTEMTC（各 1 行，不涉任何 fixture 字节）。按红线本轮未触碰；请裁决是否批准下轮清扫。
- **benchmark 后续节奏**：sweep 组与 B7/B8 重复组已建成未跑——现在补跑，还是等 write_java_tables/CLI 落地后作为 M4 验收基线一起跑？`results/` 记录目前"只提交最新一对"，是否维持？
- **B6 内存形态**：on_the_fly 路径 872 MiB 是 10 列大数据集的现实形态；V1.0 是否需要在文档里给"内存敏感用户"一条明确指引（如建议 subsample 阈值内的配置），还是按 D10 范围什么都不加？
- **阻塞项（待用户）**：N4 JRE 17 characterization（本机无 JRE 17）；M6 push（待提供 GitHub 仓库，首次 CI 绿 = Linux 侧 A-exact 证据闭环，亦是依赖下界冻结条件）。

## 5. 下一步计划

1. 等第 7 轮裁决 → 执行 M4 首批实现（write_java_tables → CLI → warning），照旧门禁流程。
2. 用户侧两项解锁后：push 启 CI（M6）、JRE 17 characterization（N4）。
3. 依赖下界在 3.11 CI 绿后从 provisional 转冻结；PyPI 实时复检后按 §1.10 模板发布（870 MiB 事实性陈述，不得称轻量）。

## 6. 评审包导读

包内只含本轮新增/变更且需专家过目的内容；完整工程 `D:\stem\pySTEMtc`（git HEAD 至 0d87878+a8dbb22 之上加 round-7 三提交，146 测试可独立复跑）。**round-7 评审包**：`D:\stem\pySTEMTC_m4_round7_review_20260920_034500.zip`（11 文件，约 100 KB）。

| 文件 | 焦点问题（每文件一个） |
|------|----------------------|
| `docs/08_...md`（本报告） | §2.3 的 value_states 正交合同是否取代方向不变量；§2.4 的 B9 路径隔离诊断（B5→B9→B6 拆 on_the_fly 与 sample 1M）是否成立 |
| `docs/03_v1_implementation_spec.md` | §1.10 正交合同（5 状态 × 2 present = 10 格真值表）+ 资源预算提示插入段 |
| `src/pystemtc/result.py` | `_encode_value` docstring 的正交矩阵语义是否完整（含 `_encode_value(math.inf, True)` 实证） |
| `tests/test_result_schema.py` | 21 schema 测试（11 原有 + 10 参数化正交矩阵）的钉死强度 |
| `benchmarks/benchmark_core.py` | CORE 列表新增 B9=10k×9T（专家路径拆分诊断点）；B5/B9/B6 三档路径切换序列 |
| `benchmarks/README.md` | core 默认组 B1-B9 表格更新 |
| `benchmarks/results/20260920T033542Z/`（CSV+MD） | 9 个 bench × 4 runs = 36 行；B9 实测数据是路径拆分的核心证据 |
| `verification/round7_full.diff` | a8dbb22→HEAD 全量 diff（3 提交）——schema 合同修正 + benchmark B9 + 资源预算措辞 |
| `verification/pytest_full_round7.log` | 146 passed 全量原始输出 |
| `verification/git_state.txt` | round-7 提交历史与干净工作树 |

**round-6 评审包**（仍可参考）：`D:\stem\pySTEMTC_m4_round6_review_20260920_031200.zip`。

**可跳过**：M1–M3 已评审的 src 模块（round-7 只动 result.py 的 docstring + test_result_schema.py 的新测试）、docs/01/02/04/05/06/07（仅品牌注记与措辞修正）、HANDOFF.md、既有 c01–c12 全套 fixture（本轮零触碰）。
