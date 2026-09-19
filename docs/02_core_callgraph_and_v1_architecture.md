# STEM v1.3.14 核心计算链调用图 与 PySTEMTC V1 架构设计

- 日期：2026-09-19
- 证据基础：`D:\stem\sourcecode`（edu/cmu/cs/sb/{stem,core}）。所有 file:line 均可直接回溯。
- 配套文档：`01_expert_plan_review.md`（专家方案评审结论）。

---

## Part A. Java 版端到端调用图（batch 路径，即无 GUI 的完整分析链）

### A1. 驱动层

```
main(args)                                   ST.java:5813
  ├─ "-b inDir outDir" → new ST(in, out)     ST.java:514-522（bbatchmode=true）
  │    └─ runBatchDir()                      ST.java:1258-1353
  │         ├─ initializeDefaults()          ST.java:1186
  │         ├─ parseDefaults(file)           ST.java:1359-2314（key→static *DEF 字段）
  │         └─ clusterscript(...)            ST.java:3043-3354  ← 单个 defaults 文件的端到端分析
  │              ├─ 参数校验                  ST.java:3076-3299
  │              ├─ (batch 跳过进度对话框)     ST.java:3301-3326
  │              ├─ buildsetwithOrig(...)    ST.java:2465-2917  ← 核心编排
  │              └─ mkdir outDir
  │                 printBatchOutputGeneTable    ST.java:2985 → <name>_genetable.txt
  │                 printBatchOutputProfileTable ST.java:2923 → <name>_profiletable.txt
  └─ "-d defaults.txt" → 仍启动 Swing GUI（仅预填参数），不是 headless 入口
```

注意：`-d` 与 batch 是两条不同路径；真正 headless 可用的只有 `-b`。batch 路径在构造期仍实例化 Swing 组件（`ST extends JFrame`，ST.java:23；`ST.java:208-227, 437-488, 489`），Linux 无显示环境需 Xvfb。

### A2. buildsetwithOrig 的 STEM 分支（balltime=true，即"不同时段重复"默认模式）ST.java:2695-2810

```
 1. new STEM_DataSet(主文件, ...)           STEM_DataSet.java:144-185
 2. logratio2()                             DataSetCore.java:733-763   标准化
 3. averageAndFilterDuplicates()            DataSetCore.java:641-725   同名基因按列中位数合并
 4. (每个重复文件) 读入 → logratio2 → duplicates 合并       ST.java:2765-2777
    （重复集复用主集的 modelprofiles                        STEM_DataSet.java:181-184）
 5. errorcheck                              ST.java:2321-2402          重复文件与主文件行列对齐校验
 6. mergeDataSets(repeats)                  DataSetCore.java:772-825   逐格跨重复取中位数；
                                                                       保留**已标准化** per-spot/repeat 序列
                                                                       （genespottimedata 语义，唯一以 03 §1.2 为准）
 7. filterdistprofiles(...)                 DataSetCore.java:848-884   含主文件在内 (R+1)R/2 对等权平均
                                                                       Pearson 相关过滤（严格 >）；
                                                                       **过滤前全部 dup-merged 基因**的相关值
                                                                       升序表 sortedcorrvals（sort :881 在
                                                                       过滤 :883 之前，后续过滤不改 :952-958）
 8. filterMissing()                         DataSetCore.java:574-604   t0 缺失或缺失数>上限则剔除
 9. filtergenesthreshold2()                 DataSetCore.java:969-1038  max−min 或 |v| 阈值过滤
10. findbestgroupassignments()              STEM_DataSet.java:1718-1758  基因→profile（并列保留，权重1/k）
11. tallyassignments()                      STEM_DataSet.java:191-209    observed 计数
12. computeaveragetally()                   STEM_DataSet.java:1038-1375  置换 → expected 计数
13. computePvaluesAssignments()             STEM_DataSet.java:287-335    binomial tail + 多重校正
14. clusterprofiles(...)                    STEM_DataSet.java:870-997    显著 profile 聚类
15. GO 步骤（无 annotation 文件时空转）       ST.java:2801-2808
16. 输出两张表                               ST.java:2923-3036
```

balltime=false（"同一时段重复"）分支差异：重复文件**原始值先中位数合并**（ST.java:2885），再 logratio2 → duplicates 合并（:2892-2893）；无相关性过滤、无 sortedcorrvals。

### A3. 数据读取（DataSetCore.dataSetReader，DataSetCore.java:285-548）

- 制表符分隔，先按 gzip 尝试（:297-302）；首非空行为表头；列为 `[SPOT] GENE t1 ... tT`。
- 缺失值 = 空单元格 → `data=0, pma=0`（:510-512）；有值 → `pma=2`（:535）；log 模式下 ≤0 的原始值也记缺失（:530-534）。
- gene 名缺省或为 `0` 时合成 `"0 (SPOT_x)"`（:466-479）；gene/spot 名统一大写（:454, :491）。
- `badd0` 模式插入全 0 合成首列（:495-497）；时间标签存 `dsamplemins[]`（:393-408）。

### A4. 标准化（三种模式）

| 模式 | 实现 | 公式 |
|------|------|------|
| Log normalize data | `btakelog=true`（ST.java:1337） | `log2(v_t / v_0)` |
| Normalize data（默认） | `btakelog=false` | `v_t − v_0` |
| No normalization/add 0 | `badd0=true`（ST.java:1338） | 合成 0 列后 `v_t − 0` = 原值 |

t0 本身缺失时，该基因其后全部时间点记缺失（DataSetCore.java:740-744）。

### A5. 模型 profile 生成与精选

- **候选生成**（STEM_DataSet.java:766-806）：每步 ∈ {−u, …, +u}、首点恒 0 的整数路径全枚举 `generatemodelprofilesall`（:1004-1029，最后一位变化最快）；若 `(2u+1)^(T−1) ≥ nsamplesmodel`（默认上限 100 万，ST.java:93）改走固定种子抽样 `generatemodelsampled`（:812-835，`Random(3733246)`；样本 0 = 严格递减 {0,−u,−2u,…}）。全 0 profile 在枚举后被移除（:780-796）。
- **精选 `compactprofiles2`**（STEM_DataSet.java:1561-1711，贪心 max-min 多样性）：
  1. 种子 = 候选索引 `ndown = n·(u+1)·Σ_{i≥1}(1/(2u+1))^i`（:1582-1587，代数上恒等于单调 profile {0,1,2,…,L−1}）。
  2. 迭代加入"与已选集合的最大相关值最小"的候选（closestcorr 初始化 :1594-1610，更新 :1677-1693）；并列时取 max|value| 更小者（:1612-1626, :1639-1667）。
  3. 加入条件 `closestcorr + FLOATERROR < dMaxCorrelation`（:1671）；停止条件：最优 remaining 的 closestcorr ≥ `min(dMaxCorrelation, 1.5)`（:1574, :1695）或达到 `nmaxprofiles`（:1575-1579）。
  4. 默认 `Maximum_Correlation=1.0` 时该上限几乎不生效，**实际起作用的是 50 的数量上限**。
- **Profile ID**：入选候选按枚举索引升序重排后编号 0..n−1（:1703-1710）。

### A6. 基因→profile 分配（findbestgroupassignments，STEM_DataSet.java:1718-1758)

- 度量：掩码 Pearson 相关（`Util.correlation(data[row], profile, pma[row])` → Util.java:427-472；缺失列剔除）。Pearson 平移/尺度不变 ⇒ 等价于逐基因标准化后比较。
- 并列：所有 argmax profile 均保留（:1742-1751），基因对每个并列 profile 贡献 1/k。
- 退化：方差为 0 或无重叠列时相关记 0（Util.java:453-465）；因扫描从 dcorrmax=−2 起（:1734），平坦基因与所有 profile 并列（各 1/n）。

### A7. 置换检验（computeaveragetally，STEM_DataSet.java:1038-1375）

```
T < 9 (ALLPERMSTHRESH, :16) 或 nsamplesgene≤0 → 全枚举置换表：
    permute_t0=true  → generatepermutations(numcols)          :1468-1521（numcols! 个）
    permute_t0=false → generatepermutationsExcept0(numcols)   :1403-1461（(numcols−1)! 个，0 固定）
    nselectedperms = min(n_permutations, universe)（:1100）；≤0 或 ==universe → ballperms 全用（精确检验，:1102）
    否则【每个基因】在基因循环内从共享 Random(9873287) 流抽 floor(nextDouble()×universe)
    个索引 + Arrays.sort（:1148-1168）——有放回，重复索引按重复计数（必须复刻）
    默认 n=50 精确边界：permute_t0=true → T≤4；permute_t0=false → T≤5；n=0 → 恒精确
每基因 × 每置换：
    1. 置换后 t0 缺失 → 跳过                                    :1207
    2. 基准重参照：基准点变为 nbegin 时，用**已标准化**的 per-spot 序列重算
       vals[c] = spottimedata[c] − spottimedata[nbegin]，跨 spot 取中位数；
       有重复时 = 跨重复的中位数的中位数                          :1229-1288（按 nbegin 缓存 :1210-1213）
    3. 对置换序列按 pma 掩码算 mean/std                          :1291-1305
    4. 重算与所有 model profile 的相关（无缺失走预计算统计量的
       闭式路径 :1324-1334；有缺失走 Util.correlation :1336-1340），
       并列拆分 1/k，NaN 跳过                                   :1342-1353
    5. expected[profile] += 1/k                                :1356-1365
最终 expected[p] *= n_genes / 总分配数                          :1371-1374
```

**对数据模型的要求**：步骤 2 需要**已标准化**的 per-spot/repeat 序列（`genespottimedata` 有效内容，语义唯一以 `03_v1_implementation_spec.md` §1.2 为准）+ pma 矩阵在内存中保留——这是 PySTEMTC 内部数据结构设计的硬约束。

### A8. 显著性与多重校正（computePvaluesAssignments，STEM_DataSet.java:287-335）

- `p_p = P(X ≥ count_p)`，X ~ Binomial(n_genes, expected_p/n_genes)，`StatUtil.binomialtail` 对 `ceil(count−1)` 求尾部和（StatUtil.java:286-336，log 空间累加）。
- 校正（`nfdr`：0 无 / 1 "FDR" / 2 Bonferroni，默认 2）：
  - Bonferroni：阈值 α/n_profiles（:325-327）；
  - "FDR"：p 升序的 step-down 走查 `p_(i) < (i+1)·α/n`，**非 Benjamini-Hochberg 公式**（:298-316）；
  - 非 FDR 模式额外要求 `count_p > 1`（:329-334）。

### A9. 显著 profile 聚类（clusterprofiles，STEM_DataSet.java:870-997）

```
thr = 0.7（Clustering_Minimum_Correlation）
若提供了"不同时段"重复数据：thr = max(thr, sortedcorrvals[floor(percentile × len)])
  ⚠ percentile 默认 0 ⇒ 取过滤前全部 dup-merged 基因相关值的最小值，可能把 0.7 抬高   :878-885
S = 显著 profile 集合（按 profile ID 序扫描）
循环：对每个候选中心，收集与中心相关 > thr 的邻居，
      贪心扩球（成员须与球内全部成员相关 ≥ thr，closeToAllNeighbors :844-863），
      球得分 = Σ球内基因数；取得分最高的球为一个 cluster；移除后重复    :916-995
cluster ID = 生成顺序 0,1,2,…；非显著 profile 在输出中标 −1            ST.java:2950-2963
```

只有显著 profile 可入簇；每个显著 profile 最终恰属一个簇（可为单元素簇）。

### A10. K-means（kmeans，STEM_DataSet.java:413-701；V1 暂缓，仅记录）

K=10（复用 nmaxprofiles 字段）、重启 20 次（复用 nmaxchange 字段，`Random(2211)` + reservoir sampling 初始化 :479-494）；目标 = 簇内平方欧氏距离和（ties 权重 1/k :639-649）；最优一次的最终中心按字典序排序定 cluster ID（:659-671）。复用同一套输出表（表头不同，ST.java:2928-2943）。

### A11. 输出表精确格式

| 文件 | 表头 |
|------|------|
| `<name>_profiletable.txt` | `Profile ID \t Profile Model \t Cluster (-1 non-significant) \t # Genes Assigned \t # Gene Expected \t p-value`；Model 为逗号连接的 profile 值 |
| `<name>_genetable.txt` | `<基因列名> \t <SPOT列名> \t Profile \t t1 \t t2 …`；并列 assignment 用 `;` 连接；缺失单元格输出空串；数值两位小数 |
| `<name>_kmeansclustertable.txt` | `Cluster \t Cluster Mean \t Number of Genes` |

文件名前缀 = defaults 文件名去扩展名（Util.stripLastExtension）。

### A12. 关键参数 → 默认值（defaults.txt ↔ 源码）

`max_unit_change=2`、`max_model_profiles=50`、`candidate_cap=1,000,000`、`max_correlation=1.0`、`n_permutations=50`（0=全排列）、`permute_t0=true`、`alpha=0.05`、`correction=Bonferroni`、`clustering_min_corr=0.7`、`clustering_percentile=0`、`min_abs_expr=1.0`、`max_missing=0`、`repeat_min_corr=0.0`、`normalize="Normalize data"`、`maxmin=true`；K-means：K=10、restarts=20。

---

## Part B. PySTEMTC V1 架构设计

### B1. 范围冻结（与专家第二轮结论一致）

**做**：读取（主文件+重复文件）、三模式标准化、缺失/阈值/重复相关过滤、候选 profile 生成（枚举+抽样双路径）、贪心精选、掩码 Pearson 分配（并列 1/k）、置换（全枚举+固定种子子抽样、t0 可选、基准重参照）、binomial tail 显著性 + 三种校正、显著 profile 聚类（含 percentile quirk）、结构化结果、YAML/JSON 配置（含 defaults.txt 导入）、CLI、`rng="java"` 复现模式、Level A/B 分层金标测试。

**不做（V1）**：GO/annotation/enrichment、基因集、染色体、GFF、ID cross-reference、两条件比较（GUI-only，且依赖两个完整 run）、绘图（`plot.py` 后置）、K-means（V1.1）。

### B2. 包结构

```
pySTEMtc/
├── pyproject.toml              # name=pystemtc (import pystemtc)，GPL-3.0，requires-python>=3.10
├── src/pystemtc/
│   ├── rng.py                  # JavaRandom：java.util.Random 48-bit LCG 逐位复刻
│   ├── dataio.py               # STEM 格式 tsv/tsv.gz 读取：表头/spot/缺失(pma)/大写/合成0列
│   ├── dataset.py              # 内部数据集：data, pma, spot_data(已标准化 per-spot 序列),
│   │                           #   repeats 分组, sample_labels, 基因/probe 元数据
│   ├── normalize.py            # log2(v/v0) | v−v0 | raw+add0（含 t0 缺失级联）
│   ├── filtering.py            # duplicates 中位数合并、重复合并+相关过滤、missing、阈值过滤
│   ├── profiles.py             # 全枚举 / 固定种子抽样候选 + compactprofiles2 贪心精选
│   ├── assign.py               # 掩码 Pearson + 并列 argmax（1/k 权重）
│   ├── permutation.py          # 全排列枚举(±t0固定) + Random(9873287) 子抽样 + 基准重参照
│   ├── significance.py         # binomialtail（log 空间）+ Bonferroni/step-down FDR/none
│   ├── clustering.py           # 贪心扩球聚类（含 percentile 抬升 quirk）
│   ├── engine.py               # fit()：严格按 A2 顺序编排
│   ├── result.py               # STEMResult：profiles/genes/filtered/clusters/config + to_dict/to_csv
│   ├── config.py               # STEMConfig dataclass；默认值镜像 Java；defaults.txt 双向转换
│   ├── cli.py                  # `pystemtc run data.tsv --config cfg.yaml --output out/`
│   └── plot.py                 # （后置）matplotlib adapter，不进 core
└── tests/
    ├── golden/                 # stem.jar batch 生成的 profiletable/genetable fixtures
    ├── test_rng.py             # JavaRandom 对拍已知 java.util.Random 序列
    ├── test_units.py           # 各模块单测（构造小矩阵，断言与手算一致）
    └── test_golden.py          # 分层验收：Level A exact + Level B 容差（见 §B4）
```

### B3. 公开 API（默认值全部镜像 Java defaults.txt）

```python
import pystemtc

model = pystemtc.STEM(
    normalize="normalize",            # "log" | "normalize" | "none_add0"
    max_unit_change=2,
    max_model_profiles=50,
    max_correlation=1.0,
    candidate_cap=1_000_000,
    n_permutations=50,                # 0 = 全排列（精确检验）
    permute_t0=True,
    alpha=0.05,
    correction="bonferroni",          # "bonferroni" | "fdr_stem" | "none"
    cluster_min_correlation=0.7,
    cluster_corr_percentile=0.0,
    max_missing=0,
    min_abs_expr=1.0,
    change_rule="max_minus_min",      # | "diff_from_zero"
    repeat_min_correlation=0.0,
    # （第 3 轮裁决：rng 参数已删除——V1 只实现 java.util.Random 复刻，无第二模式）
    random_state=None,                # 仅 rng="numpy" 时生效
)

# V1 输入契约（严格模式）：只接受「原始表达值」，行=spot/observation
result = model.fit(path)                          # 原生 STEM tsv/tsv.gz
result = model.fit(df, replicates=[...],          # DataFrame：spot 级宽表（见下）
                   repeat_mode="different_periods")  # | "same_period"
result = model.fit(STEMDataset)                   # 内部数据类（测试/高级用法）
# ⚠ V1 不接受裸 ndarray（V1.1 再议），不接受预标准化矩阵（契约约束，见下）

result.profiles        # DataFrame: profile_id, model, cluster, n_assigned, n_expected, p_value, significant
result.gene_assignments# DataFrame: gene, probe, profile(并列用;连接), 各时间点处理值(缺失为NaN)
result.filtered_genes  # 被过滤基因及原因
result.clusters        # cluster → [profile_id]
result.config          # 纯算法配置快照（无时间戳，可 hash、可复现）
result.metadata        # timestamp、软件版本、输入形态、运行时信息
result.to_dict()       # JSON 兼容，供 agent/MCP 使用
result.to_csv(dir)     # 与 Java 输出同构的两张表
```

- `fit()` 只接受**原始表达值**（引擎内部完成标准化与重参照缓存）。`normalize="none_add0"` 是 STEM 的输入模式（合成 t0=0 列、后续原值相对 0），**不等价于**"传入已标准化数据"——预标准化数据走 `none_add0` 会多出一个合成时间点，V1 干脆不提供预标准化入口，避免"能跑但已偏离 STEM 算法"的接口。DataFrame 行=spot/observation：必需列 `gene`，可选列 `spot`（缺省按行序合成），其余列按列序为时间列（列名即时间标签），NaN=缺失；重复 gene 行按 STEM 语义中位数合并，行序不打乱。
- `numcols < 2` 抛 `STEMTCValueError`（原版该分支为 GO-only 模式，V1 不实现）。

### B4. 分层验收（Level A/B）金标测试方案

1. **Fixture 生成**：本机（Windows + JRE 8）`java -mx1024M -jar stem.jar -b <cfgdir> <outdir>`。**已生成并入库**：`tests/golden/java_configs/` 12 组配置（Guillemin 样例网格：3 种标准化 × permute_t0 × 3 种校正 × 重复模式 × percentile；合成数据 synth6/synth10 触发置换子抽样、全排列、on-the-fly 路径）、`java_reference/` 24 张输出表 + stdout 日志、`java_rng/vectors.txt`（jjs 从真实 `java.util.Random` 导出）。再生成：`python pySTEMtc/tools/gen_fixtures.py`。
2. **比对粒度（分层）**：Level A 必须逐字段 exact——Profile ID、Profile Model 向量、Cluster、`# Genes Assigned`（**double，允许分数值**——并列 1/k 累积，确定性 exact，不得称整数）、genetable 的 gene/probe/Profile（含并列 `;` 顺序）；Level B exact 优先 + 容差兜底——`# Gene Expected`、p-value（第一目标：与 Java 打印字符串一致；兜底容差由解冻区定稿）。
3. **RNG 单测**：`JavaRandom(seed)` 与 `tests/golden/java_rng/vectors.txt`（本机 JRE 8 jjs 从真实 `java.util.Random` 导出，seeds {9873287, 3733246, 2211, 42}，含 nextDouble/nextInt(1000)/nextInt() 流交错顺序）逐值对拍。
4. **浮点策略**：金标相关路径禁用 `np.sum` 的成对求和，按 Java 朴素顺序累加；`FLOATERROR=1e-7`（STEM_DataSet.java:15）与 tie-break（max|value| 较小者）逐行复刻；per-spot 序列的存储时点须与 `genespottimedata` 填充时机一致（logratio2 之后，DataSetCore.java:672-703），不得用代数等价式替换（浮点上 (a−c)−(b−c) ≠ a−b）。
5. **CI**：fixtures 提交入库，金标测试不依赖 Java；Java 仅供重新生成 fixtures。

### B5. 里程碑

| 里程碑 | 内容 | 完成判据 |
|--------|------|---------|
| M1 | rng + dataio + normalize + filtering + dataset | 单测过；JavaRandom 对拍通过 |
| M2 | profiles + assign + permutation + significance + clustering + engine | 合成数据自洽（显著 profile 数、簇数合理） |
| M3 | 金标测试 | Level A 全 exact + Level B 达定稿容差（M2 首批对拍后定稿） |
| M4 | config/CLI/result.to_dict + 文档 + 打包 | `pip install -e .` 后 CLI 可跑样例数据 |
| V1.1 | kmeans + plot | K-means 金标（seed 2211 复刻） |

### B6. 许可证

STEM v1.3.9+ 为 GPL-3.0（readme.txt:49）。PySTEMTC 基于 Java 源码等价翻译，属衍生作品，必须以 **GPL-3.0** 发布，并在源码头部保留归属声明（Ernst, Patek, Bar-Joseph；ernstlab.github.io/STEM）。
