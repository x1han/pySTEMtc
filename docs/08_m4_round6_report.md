# pySTEMTC M4 第 6 轮执行报告与遗留问题清单（供专家团评审）
（品牌注记，2026-09-19：品牌铁律第 6 轮定案——py 小写、STEM 大写、tc 小写，写作 pySTEMTC；PyPI/import/CLI = `pystemtc` 全小写不变。历史文档 docs/01/02/04-07 中的 PySTEMTC 为当时记录，按 D12 不做追溯改写、以顶部 dated 注记为准。）

- 日期：2026-09-20
- 范围：第 6 轮裁决的完整执行——(a) P1 阻塞修复（STEMResult 丢失 Java genetable 末列载荷）；(b) to_dict schema v2 + stage timing；(c) 打包/CI/依赖下界/文案（M4/M6/M8）；(d) 品牌铁律清扫；(e) `benchmarks/benchmark_core.py` 按专家原案建成并跑完核心组。门禁全流程：planner → pre-work review（GO-with-changes，2 P1 / 5 P2 / 8 P3 全部吸收）→ 实现（先红后绿）→ **verifier 独立复核 10/10 PASS** → **post-work review APPROVE** → 4 项发现全部处置 → 136/136。
- 评审包：`D:\stem\pySTEMTC_m4_round6_review_20260920_031200.zip`（精选内容，见 §6 导读）
- 关联文档：`docs/07`（M3 结题 + 第 6 轮裁决背景）、`HANDOFF.md` §7（D12–D15 决策记录）、`docs/03` §1.7（P1 修复记录）/§1.10（schema v2 + 发布文案模板）
- 本报告所有数字均来自当日本机实测（Python 3.14.3 + numpy 2.4.6 + pandas 3.0.3，Windows-11 10.0.26200，git `a8dbb22`，工作树干净）

---

## 1. 一段话总结

第 6 轮裁决全部执行完毕。P1 阻塞修复：STEMResult 丢失 Java genetable 末列载荷的根因，是 Python 侧对**无重复数据集**也无条件执行了零初始化的 cellwise 中位数合并，而 Java 在无 repeat 时**从不调用 mergeDataSets**（different_periods 直接 `theDataSetsMerged = theDataSet1`，ST.java:2577；same_period 是纯引用别名包装，ST.java:2669）——修复为直通分支（`if not repeats: return main`），先红后绿，新增的 14 配置全字段值列金标测试证明 A 层零反噬。to_dict schema v2（11 顶层键、`profile_ids: list[int]`、value_states 真值表、config/input 分离、timestamp 单次生成）与 8 键 stage timing 落地。`benchmarks/benchmark_core.py` 按专家原案建成（B1-B6 专家网格 + n_permutations 扫描组 + 重复组），核心组实测：**wall 0.66 s（1k×5T）→ 51.0 s（10k×10T），peak RSS 76.2 → 872.5 MiB**；置换阶段在 B1–B5 占 85–95%，B6 因越过 subsample→on_the_fly 阈值额外背 20.6 s profile_generation；**B6 的 872.5 MiB 与 M3 冻结证据的 ~870 MiB 互相印证**。单机 benchmark 未给出 V1.0 必须先优化的理由。**136/136 测试通过**（105 基线 + 2 payload 回归 + 4 直通契约 + 14 金标值列 + 11 schema）。

## 2. 结果总结

### 2.1 第 6 轮裁决执行清单

| 裁决项 | 状态 | 证据 |
|----|------|------|
| M0 命名铁律 pySTEMTC（py 小写/tc 小写/STEM 大写） | 完成 | `src/ pyproject.toml tests/*.py benchmarks/` 命中数 = 0（verifier 独立 grep）；docs/01-07 顶部 dated 注记 + HANDOFF 标题改写；2 个冻结文件内的残留列入解冻申请（§4） |
| P1 阻塞：末列载荷保真（先测后改 write_java_tables） | 完成 | 根因链见 §2.2；c14 四行 + c13 phantom 回归测试；14/14 金标值列逐格 |
| M1 to_dict schema v2（4 项修改 + timestamp 单次） | 完成 | §2.3；`tests/test_result_schema.py` 11 测试；strict JSON（allow_nan=False）实测 |
| M2/M3/M5/M6/M8 冻结落盘（writer C 定义、CLI 0/1/2、warning 逐字、文案红线、发布模板） | 完成 | spec 03 §0 三条新冻结 + §1.10；docs/06/07 修正注记（870 MiB 事实性陈述，无"跨平台已验证"类宣称） |
| M4 打包：requires-python ≥3.11 + 依赖下界 + CI matrix | 完成 | pyproject（numpy>=2.4,<3、pandas>=3.0,<4，provisional 至 3.11 CI 绿）；ci.yml 3.11/3.12/3.14 × ubuntu/windows，push 后生效 |
| benchmark harness 建成 + 核心组全跑 | 完成 | §2.4；执行期修正：implementer 初版网格偏离专家原案（丢 30k×5、sweep 扫错变量），主会话已纠正为 B1=1k×5 … B6=10k×10T、sweep 扫 n_permutations |
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
| value_states 枚举（存储双精度优先的真值表） | NaN→`"nan"`；+Inf→`"positive_infinity"`；−Inf→`"negative_infinity"`（三者 values→null，与 pma 无关）；finite+pma==0→`"missing"`（填充载荷保留：0.0 或 −v0 幻影值）；finite+pma≠0→`"finite"`。方向不变量：missing⟹present=False；present=True⟹finite。非对称性钉死：全缺失格里的非有限载荷报非有限态而非 missing（c14 路线） |
| config/input 分离 | config = 18 个显式算法键（枚举自 STEMConfig，JSON 可序列化，不做"hashable"宣称）；input = data_file / repeat_files / time_points / input_form |
| timestamp 单次 | `engine.fit` 内生成一次存 metadata，`to_dict` 只拷贝；两次调用全等有测试 |

顶层 11 键：`schema_version(=2), reference, generator, config, input, metadata, profiles, gene_assignments, filtered_genes, clusters, timing`。`json.dumps(result.to_dict(), allow_nan=False)` 对 c13/c14 及活体小样本实测通过。timing 8 键（perf_counter）：input_read / normalize_filter / profile_generation / assignment / permutation / significance / clustering / wall。

### 2.4 核心组 benchmark 实测（专家网格，2026-09-19T18:12Z）

环境：Windows-11 / Python 3.14.3 / numpy 2.4.6 / pandas 3.0.3；seed 20260919；warm-up 1 + formal 3 取 **median**（min/max 保留，从不平均）；每 (bench,run) 独立子进程隔离，peak RSS 为进程单调值（Psapi PeakWorkingSetSize）。记录：`benchmarks/results/20260919T181249Z/`（CSV 24 行 + MD）。

| bench | 规模 | 存活基因 | 置换模式 | wall median (s) | peak RSS (MiB) |
|---|---|---|---|---|---|
| B1 | 1 000 × 5T | 892 | subsample_universe | 0.66 | 76.2 |
| B2 | 5 000 × 5T | 4 478 | subsample_universe | 4.16 | 81.8 |
| B3 | 10 000 × 5T | 8 962 | subsample_universe | 10.59 | 87.2 |
| B4 | 30 000 × 5T | 26 878 | subsample_universe | 38.98 | 111.3 |
| B5 | 10 000 × 8T | 9 000 | subsample_universe | 19.93 | 119.3 |
| B6 | 10 000 × 10T | 9 000 | **on_the_fly** | 50.99 | **872.5** |

各阶段（median，秒）：

| bench | input_read | normalize_filter | profile_generation | assignment | permutation | significance | clustering |
|---|---|---|---|---|---|---|---|
| B1 | 0.005 | 0.005 | 0.010 | 0.036 | 0.601 | 0.008 | 0.000 |
| B2 | 0.023 | 0.028 | 0.010 | 0.184 | 3.828 | 0.073 | 0.000 |
| B3 | 0.044 | 0.049 | 0.010 | 0.357 | 9.943 | 0.165 | 0.000 |
| B4 | 0.135 | 0.140 | 0.011 | 1.082 | 37.025 | 0.477 | 0.000 |
| B5 | 0.063 | 0.067 | 1.645 | 0.492 | 17.451 | 0.158 | 0.000 |
| B6 | 0.077 | 0.082 | 20.634 | 1.257 | 28.372 | 0.193 | 0.000 |

解读（只述事实，不做优化承诺）：
- **B1–B5 置换阶段占 85–95%**，与 Java 一致（同为本工具的计算主体）；B4（30k×5T）39 s，M3 报告"3 万基因分钟级"的外推得到实测支持。
- **B6 是形态拐点**：10k×10T 越过 subsample→on_the_fly 阈值（`legacy_with_replacement` 语义切换处），profile_generation 从 1.6 s（B5）跳到 20.6 s，permutation 28.4 s；**872.5 MiB peak 与 M3 冻结证据 ~870 MiB 互相印证**（两个独立实现路径测到同一量级）。872 MiB 按第 6 轮裁决作事实性陈述，发布文案模板已按此措辞（spec §1.10）。
- 基因数维度的放大（B1→B4，30×）带来 wall 约 59×，超线性但在单机可接受包络内；本报告不做原因归因，留待优化轮（若有）。
- sweep 组（n_permutations ∈ {10,50,100,500,1000} @ 10k×8T）与重复组 B7/B8 已建成未跑——专家指令为"先跑 1k/5k/10k/30k × T=5/10 × 50 permutations 这一组"（§4 请裁决后续节奏）。
- 执行期修正记录：implementer 初版把 B 网格改成 300×6/1k×10/3k×10/3k×6/10k×6/10k×10（丢了专家点名的 30k×5 与 5k×5）且 sweep 误扫 max_model_profiles；主会话对照专家原文纠正为上述网格并复测（B1 冒烟 + 全组）。

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
2. **schema v2 是对既有 `to_dict` 的 pre-release 重定义**（第 6 轮裁决定性），已按四项修改 + timestamp 单次落地并有 11 个测试钉住；strict JSON 实测通过。
3. **单机 benchmark 未给出 V1.0 必须先优化的理由**（措辞遵 M8 修正注记）：1k→30k 基因 wall 0.66→39 s，10k×10T 51 s；内存上界由 B6 的 872.5 MiB 界定，发布文案按"未优化 + 事实性 870 MiB"模板执行。
4. **性能画像可用于优化轮的地基**：置换阶段主导（B1–B5 占 85–95%）、B6 的 on_the_fly 路径是内存/时间双热点——但任何优化都必须走 golden → optimize → golden（D15），本轮不动。
5. **流程收敛**：verifier 10/10 + post-review 无 P1，四项发现当日全部处置；136/136 绿。

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

包内只含本轮新增/变更且需专家过目的内容；完整工程 `D:\stem\pySTEMtc`（git `a8dbb22`，136 测试可独立复跑）。

| 文件 | 焦点问题（每文件一个） |
|------|----------------------|
| `docs/08_...md`（本报告） | §4 的五项意见征集；§2.4 的 benchmark 解读是否成立 |
| `docs/03_v1_implementation_spec.md` | §1.7（P1 修复：直通 vs 影子通道的偏差论证）、§1.10（schema v2 钉死）、§0（三条新冻结） |
| `verification/round6_full.diff` | fc38b13→a8dbb22 全量 diff（4 提交，+1335/−74）——P1 修复与 schema v2 的最终形态 |
| `src/pystemtc/filtering.py` | 直通分支是否完整复刻 ST.java:2577/:2669 的"无 repeat 恒等"语义 |
| `src/pystemtc/result.py` | value_states 真值表与方向不变量是否与第 6 轮 M1 裁决逐条一致 |
| `tests/test_result_schema.py` | 11 个 schema 测试的断言强度是否足够（strict JSON / 两次调用全等 / 真值表） |
| `tests/test_golden_branches.py` | c14 四行 + c13 phantom 回归是否钉住专家发现的原始症状 |
| `benchmarks/benchmark_core.py` | 网格/sweep 变量是否符合专家原案；warm-up+median 纪律；D15 目录隔离 |
| `benchmarks/results/20260919T181249Z/`（CSV+MD） | 数字与 §2.4 的一致性；B6 872.5 MiB 与 M3 ~870 MiB 的互证 |
| `verification/pytest_full_20260920_025500.log` | 136 passed 全量原始输出（当日本机全新复跑） |
| `verification/git_state.txt` | 提交历史与干净工作树 |

**可跳过**：M1–M3 已评审的 src 模块（本轮 src 变更集中在 filtering/result/engine 三文件，diff 里可见全貌）、docs/01/02/04/05/06/07（仅品牌注记与措辞修正）、HANDOFF.md、既有 c01–c12 全套 fixture（本轮零触碰）。
