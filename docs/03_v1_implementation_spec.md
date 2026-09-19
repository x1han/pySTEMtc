# PySTEMTC V1.0 Implementation Spec

- 日期：2026-09-19（第 2 轮评审后定稿）
- 基准：本地 STEM v1.3.14（`D:\stem\stem.jar` + `D:\stem\sourcecode` 72 个 Java 文件）
- 配套：`01_expert_plan_review.md`（评审结论）、`02_core_callgraph_and_v1_architecture.md`（调用图与架构）
- 规则：**冷冻区**不得更改；**常温区**本轮钉死，改动必须记录理由；**解冻区**等 M2 首批真实对拍数据后定稿。

---

## 0. 冷冻区（frozen，不得再议）

- **命名（第 4 轮定案，2026-09-19）**：品牌/项目 **PySTEMTC**；PyPI distribution、import namespace、CLI 统一 **`pystemtc`**。PyPI JSON API 实证 404 未被占用（2026-09-19；另 `stempy` = Kitware 4D-STEM 数据包 v3.5.0、`pystem` = 显微 STEM 成像包，均确定被占，来自专家检索 + `stempy` 已独立复核）。**发布前必须再走一次 PyPI 实时接口确认，不能把"检索不到"当成占坑成功**。仓库目录 2026-09-19 起为 `D:\stem\pySTEMtc`（用户主动由 `D:\stem\STEMpy` 更名，详见 §1.8）；c09/c10/c11 fixture 配置内嵌 `STEMpy/tests/...` 生成期路径，属冻结证据，**配置内容不改**，解析由 `test_golden.py::_resolve` 的 basename 兜底维护。
  - **第 6 轮 dated 修订（2026-09-19，品牌大小写铁律）**：品牌自本注记起写作 **pySTEMTC**（py 小写、STEM 大写、tc 小写）。上文及历史文档中的 "PySTEMTC" 为当时记录，不作追溯改写。PyPI distribution / import namespace / CLI **`pystemtc`（全小写）不变**，且不参与品牌大小写规则——新写代码 docstring、文档标题与发布物料一律用 pySTEMTC。
- 许可证 **GPL-3.0**（衍生自 GPLv3 的 STEM，源码头保留 Ernst/Patek/Bar-Joseph 归属）。
- **最高原则（Compatibility First，第 4 轮冻结）**：PySTEMTC 首先是 **Java STEM v1.3.14 time-course 计算核心的 headless Python 兼容实现**，而不是一个重新设计的 time-course 算法包。本地 STEM v1.3.14 是唯一行为 oracle；所有设计争议先问"Java v1.3.14 到底怎么做"，不问"Python 里通常怎么做"。
- **优先级链**：Java v1.3.14 行为一致性 > 代码简洁 > 运行速度 > Pythonic 写法。
- **必须 100% 一致（任一不同 = TEST FAIL，因为这些差异会改变生物学解释）**：过滤后保留哪些 gene、过滤掉哪些 gene；生成哪些 model profiles、profile ID 与顺序；每个 gene 分到哪个 profile、并列时分到哪些 profiles 及并列顺序；每个 profile 的 observed gene count（double，允许分数值）；哪些 profile 显著/不显著；profile 属于哪个 cluster、cluster 成员与 cluster ID；最终 genetable 的 Profile 列；Java 的全部 legacy quirk。相关系数只差 1e-15 导致 assignment 翻转也算失败。
- **允许极小浮点末位差的仅限连续量**：correlation、expected profile count、p-value（内含 sqrt/log/exp 与浮点顺序累加）。且必须同时满足：数值误差 ≤ 规定容差；significant/non-significant 结论完全相同；不改变任何 assignment；不改变任何 cluster 结果。**浮点末位可以略有不同，科学结果不能不同**——若 Java p=0.0049999998 而 Python p=0.0050000001 并导致显著性翻转，即为兼容性失败，必须继续追查。
- 基准实现：本地 STEM v1.3.14 `stem.jar` + 对应 72 个 Java 源码文件。GitHub master 不作对照基准。
- V1 目标：headless Python 实现 STEM short time-course 核心算法。
- V1 必须包含：raw time-course 读取、repeat 处理、normalization、duplicate aggregation、gene filtering、candidate model profiles、profile compaction、gene→profile assignment、permutation、expected profile count、profile significance、multiple-testing correction、significant-profile clustering、structured result、config、CLI、Python API、Java-compatible RNG。
- V1 明确不包含：GO、annotation、enrichment、gene-set analysis、chromosome/GFF、two-condition comparison、GUI、plotting、K-means。
- **工程原则（冻结）**：core 不得依赖 GUI/display/matplotlib；CLI/API 只是 adapter；正确性优先于性能、兼容性优先于 Pythonic 重构；Java 源码优先于论文公式与手册描述；不修 Java quirk、不替换成"统计上更合理"的方法、不做改变浮点顺序的 vectorize、不用 scipy 等现成函数替换 Java 算法除非证明等价；**任何优化：先有 golden test → 优化 → 重新 golden**。
- **验收分层（Compatibility A/B/C，第 4 轮起取代 Level A/B）**：
  - **A 结构结果——必须 exact**：candidate/model profiles、profile IDs、gene assignments（含并列与顺序）、observed tally、significant flags、clusters、输出顺序。
  - **B 数值结果（第 5 轮冻结为两层，2026-09-19）**：**B-output**——canonical oracle fixtures（本机 JRE 1.8.0_451 生成）下，Java 打印字符串 == PySTEMTC 打印字符串，必须 exact；**B-internal**——原始 float 不承诺跨 OS/跨 libm bitwise 一致，但任何末位误差不得改变任何 A 层结果（显著性翻转、assignment 翻转 = P0 级兼容失败）。**禁止宣称"所有平台/输入组合下连续量逐位或逐字符串一致"——当前无此证据，也不追求此承诺**；所有支持平台必须保证 A 层 exact。
  - **C 文件输出**：Java/Python 的 genetable、profiletable 除明确允许的浮点末位外逐字段一致（实现物 = M4 `write_java_tables`，tab 分隔复刻 batch 两表；**不占用 `to_csv` 名称**——那留给未来 Pythonic CSV 导出，两件事不混。截至 M2 已达成 A 全 exact + B 打印值全等）。
  - 延续映射：旧 Level A ≈ A（含 observed tally）；旧 Level B ≈ B。
- **M2 正式 GO（第 5 轮门禁结论，2026-09-19）**。M3 范围锁定：c13/c14 金标扩展（§1.9）→ git+CI → benchmark（只测不优化）→ 其余收尾；**不扩大范围、不做新功能**。
- **writer 字符集裁决（第 6 轮冻结，Compatibility C 的 writer 轮定义）**：C 层"逐字段一致"按**解码后字段**判定（decoded-table-field exact）；字节级 exact 仅在**显式 pin 字符集与行分隔符**时承诺；默认跟随**运行平台默认字符集**（镜像 Java 行为）并提供 `encoding=` 参数（实现于 writer 轮）。∞（U+221E）/−∞/U+FFFD 的渲染形式无条件复刻（§1.7）。
- **CLI 裁决（第 6 轮冻结）**：退出码 `0` 成功 / `1` 运行失败 / `2` 用法错误；`batch` 模式单配置失败**继续**处理其余配置，结束时以 stderr 汇总失败清单；stdout 保持**简洁成功摘要**（行数级镜像 Java batch，不做逐 gene 噪声输出）。
- **M5 warning 冻结原文（第 6 轮冻结；第 5 轮 N9 定组合、第 6 轮定文案）**：仅 `none_add0 × permute_t0=True` 组合弹运行时 warning，**只 warn 一次**，文案冻结为："`normalize='none_add0'` with `permute_t0=True` permutes the synthetic zero baseline together with observed time points, matching legacy STEM v1.3.14 behavior. Interpret permutation-based significance with caution." legacy 有放回置换不逐次警告，由 metadata（`legacy_with_replacement`/`permutation_mode`）+ 文档承载；warning 只说明风险，不改计算结果。

## 1. 常温区（pinned this round）

### 1.1 输入契约（V1 严格模式）

**唯一接受的语义：原始表达值（raw expression），行 = spot/observation。**

| 入口 | 说明 |
|------|------|
| `fit(path)` | 原生 STEM tsv/tsv.gz：`[SPOT] GENE t1..tT`；空单元格=缺失；gene/spot 统一大写；gene 名缺失或为 `0` 时合成 `"0 (SPOT_x)"`；log 模式下 ≤0 记缺失；`none_add0` 模式插入合成 0 列。语义完全按 `DataSetCore.dataSetReader`（DataSetCore.java:285-548）。 |
| `fit(DataFrame)` | 必需列 `gene`；可选列 `spot`（缺省按行序合成 `SPOT_<i>`）；其余列按列序为时间列（列名=时间标签）；NaN=缺失；重复 gene 行**保留**并按 STEM 语义中位数合并；行序不打乱、不去重、不改列名。 |
| `fit(STEMDataset)` | 内部数据类直接注入（测试/高级用法）。 |

- **V1 不提供裸 ndarray 入口**（解冻区 #4）；**不接受预标准化矩阵**（契约约束——无法可靠运行时检测，文档与 `result.metadata.input_form` 声明）。`normalize="none_add0"` 是 STEM 输入模式（合成 t0=0），**不等价于**"传入已标准化数据"。
- 时间点数（含 add0 合成列）`< 2` → 抛 `STEMTCValueError`。
- 重复文件：`replicates=[path|DataFrame,...]` + `repeat_mode="different_periods" | "same_period"`，语义按 A2（不同时段：各自标准化→逐格中位数→相关过滤；同一时段：原始值先中位数合并→再标准化，无相关过滤）。

### 1.2 内部数据模型（STEMDataset）

| 字段 | 类型 | 说明 |
|------|------|------|
| `spot_data` | (n_spots, T) float64 | **标准化后** per-spot 序列（含 add0 合成列） |
| `spot_pma` | (n_spots, T) int8 | 0=缺失，2=present |
| `spot_ids` / `spot_genes` | list[str] | 大写；spot→gene 归属 |
| `gene_data` / `gene_pma` | (n_genes, T) | duplicates 中位数合并后（分析主矩阵） |
| `gene_probes` | list[str] | probe id 以 `;` 连接 |
| `repeat_sets` | list[SpotSet-like] | 每个重复文件的 per-spot 标准化序列（different_periods 模式） |
| `repeat_corr_sorted` | list[float] \| None | **全部 dup-merged 基因**（在相关性/缺失/阈值过滤**之前**）的平均两两相关值升序表——Java `sortedcorrvals` 的 `Arrays.sort`（DataSetCore.java:881）先于过滤（:883），且后续过滤不修改它（:952-958）；percentile quirk 索引按这张全长表算；**仅 different_periods 模式非 None**（same_period 模式 Java 置 null，DataSetCore.java:787-792） |
| `sample_labels` | list[str] | 时间标签 |

**存储时点硬约束（预审修正）**：`spot_data` 必须逐位复刻 Java `genespottimedata` 的**有效内容**（DataSetCore.java:672-719）。填充发生在 `logratio2` 之后（两种重复模式皆然，ST.java:2750-2751 / :2892-2893），但 Java 存的是 `data[nrow]` 的**引用**（:682），随后 dup-merge **原地覆写**重复组主行为组内中位数（:719，pma 取 max :716）。故有效内容 = **重复组主行：合并后（中位数）值；重复组其余行 [1..k]：合并前的标准化值；非重复基因：标准化值本身**。置换重参照 `(v_c−v_0)−(v_begin−v_0)`（STEM_DataSet.java:1237/:1271）直接用该内容相减——浮点上与 `v_c−v_begin` 不等价，**禁止代数等价式替换**。中位数必须复刻 `Util.getmedian`（Util.java:581-595）的排序与取中规则。

**复刻要点清单（预审补充，全部有源码依据）**：
1. RNG 向量文件不记录 `nextInt` 的 bound（=1000，见 `tools/gen_java_rng.js`），测试需硬编码。
2. genetable 值格式 = Java `NumberFormat(Locale.ENGLISH)`、min=max 小数位 2（HALF_EVEN 舍入、|v|≥1000 千分位分组、微小负数输出 `-0.00`）；集成测试按**字符串级**比对。
3. genetable 最后一列**无条件输出**（缺失单元格在最后一列不输出空串，ST.java:3021-3033）——M4 `write_java_tables` 时注意。
4. 重复相关性过滤：对 **(R+1)·R/2 对（含主文件 vs 重复）** 等权平均、严格 `>` 阈值、掩码=双方 pma 非零、方差 0 或无重叠 → 0（DataSetCore.java:850-879，Util.java:481-526）。
5. 重复文件必须与主文件原始行对齐（errorcheck，ST.java:2365-2402）；DataFrame 输入的重复/空白 spot 名按 dataio 同规则抛错（DataSetCore.java:429-452）。
6. 阈值过滤两种变体均扫描列 1..T−1 并用 `≥`，max−min 变体的 dmax/dmin 初始化为 0（DataSetCore.java:983-1038）；log 模式 ≤0 只清 pma、保留解析值（:530-536）。
7. 无 spot 列时 gene 缺失合成名用 `ID_<row>`（DataSetCore.java:463, :467, :479）。

### 1.3 M1 模块接口（本轮实现范围）

```python
# rng.py —— java.util.Random 逐位复刻（Javadoc 规范算法）
class JavaRandom:
    MULTIPLIER = 0x5DEECE66D
    ADDEND = 0xB
    MASK = (1 << 48) - 1
    def __init__(self, seed: int): ...            # seed = (seed ^ MULTIPLIER) & MASK
    def next(self, bits: int) -> int: ...         # 有符号；bits=32 时返回 int32 语义
    def next_double(self) -> float: ...           # ((next(26) << 27) + next(27)) * 2**-53
    def next_int(self, bound: int | None = None) -> int: ...  # Javadoc 拒绝采样算法

# dataio.py
def read_stem_file(path: str | Path) -> "SpotSet"   # 含 gzip 分支、表头解析、pma 规则、大写、合成 gene/spot、add0 合成列
def dataframe_to_spotset(df) -> "SpotSet"           # §1.1 契约

# dataset.py
@dataclass class SpotSet: ...
#   字段钉死：raw_data (n_spots,T) float64、raw_pma (n_spots,T) int8、
#            spot_ids、gene_ids、probe_ids、sample_labels（read_stem_file 只解析；
#            标准化在 normalize.py，组装在 dataset.py）
@dataclass class STEMDataset: ...                   # §1.2 全字段
# dataset.py 另需 builder：build_stem_dataset(main: SpotSet, repeats: list[SpotSet],
#     mode, config) -> STEMDataset   （M1 集成链与 M2 engine 复用同一 builder）

# normalize.py
def log_ratio(data, pma, mode) -> tuple[np.ndarray, np.ndarray]
#   mode: "log"(log2(v/v0)) | "normalize"(v−v0) | "none_add0"(合成0列后原值)
#   t0 缺失 → 该行其后全部列记缺失（DataSetCore.java:740-744）；log 模式读入时 ≤0 记缺失（:530-534）

# filtering.py
def merge_duplicates(spotset) -> gene-level          # 中位数、probe ";" 连接（DataSetCore.java:641-725）
def merge_repeats(main, repeats, mode) -> merged     # 两模式顺序不同（A2 §5-6）
def repeat_correlation_filter(...)                   # 平均两两 Pearson（掩码），产出 repeat_corr_sorted
def filter_missing(...) / filter_threshold(...)      # max−min | diff-from-0（DataSetCore.java:574-604, 969-1038）
```

**M1 验收条件（DoD）**：
1. `test_rng.py`：`JavaRandom` 与 `tests/golden/java_rng/vectors.txt` 逐值 exact（double 用 `==`，整数 exact；流交错顺序一致）。
2. `test_units.py`：手工构造用例覆盖——重复 gene 中位数合并、gene 空缺合成 `"0 (SPOT_x)"`、log 模式 ≤0 记缺失、add0 合成列、t0 缺失级联、`Util.getmedian` 偶数长度取均值规则、重复文件两种合并顺序。
3. `test_integration_fixture.py`：对 `c01_guillemin_core` fixture，Python 链 parse→normalize→dup-merge→repeat-merge→corr-filter→missing→threshold 的幸存基因集合（gene+probe）与 `_genetable.txt` 完全一致，且值列（Java 两位小数）逐一相等。Profile 列留 M2 校验。
4. `python -m py_compile` 全部通过；`pytest` 全绿；`pip install -e .` 可用；依赖仅 numpy+pandas+标准库。

### 1.4 M2/M3 接口预告（签名先钉，实现随后）

```python
# profiles.py
enumerate_candidates(u, T) -> list            # generatemodelprofilesall（去全0）
sample_candidates(u, T, cap) -> list          # generatemodelsampled，Random(3733246)
compact_profiles2(cands, max_n, max_corr) -> (models, ids)   # FLOATERROR=1e-7，tie→max|value|小者
# assign.py
best_assignments(gene_data, gene_pma, models) -> list[list[int]]   # 掩码 Pearson，并列全保留
# permutation.py（第 3 轮裁决：rng 模式已删——V1 只有 JavaRandom，无 "numpy" 第二模式）
all_permutations(T, fix_t0) -> np.ndarray     # generatepermutations / Except0
expected_counts(ds, models, n_perms, permute_t0) -> (expected, meta)
#   bgenallperms=(T<9 或 n<=0)；ballperms=(min(n,universe)<=0 或 ==universe，此时不消耗 RNG)；
#   universe 子抽样：每基因独立 floor(next_double()*universe) 抽 n 次 + Arrays.sort，有放回（:1148-1168）；
#   on-the-fly（T>=9 且 n>0）：算法已钉死，见 §1.6；基准重参照：§1.2 硬约束 + 中位数缓存（按 nbegin）
# significance.py
binomial_tail(x, n, p) -> float               # StatUtil.java:286-336，边界语义见 §1.6（已钉死）
correct(pvals, alpha, method) -> sig_mask     # Bonferroni / step-down "FDR" / none，精确语义见 §1.6
# clustering.py
cluster_profiles(sig, models, thr, percentile_thr) -> clusters   # 贪心球：邻居 >thr，成员 ≥thr；ID=生成序
# engine.py / result.py / config.py / cli.py 按 02 文档 §B2/B3
```

### 1.5 浮点复刻规则（全部模块通用）

- **显式 scalar loop 纪律（第 3 轮裁决，无豁免）**：compatibility 模块中所有 Java 顺序累加（correlation、mean/std、profile 相关、expected tally、logaddexp）一律显式标量循环；**禁止** `np.sum / np.mean / np.std / np.dot / np.corrcoef / np.add.reduce / np.einsum` 出现在 `src/pystemtc/` 数值路径（CI 落 grep 禁运清单）。先正确，再谈性能。

## 1.6 M2 前置钉死结果（第 3 轮评审 P1-3/P1-4，源码逐行核验）

### binomialtail 边界（StatUtil.java:286-336，全部照抄、不得"修正"）

调用：`p = binomialtail((int)ceil(count−1), numrows, expected/numrows)`（STEM_DataSet.java:295）。

- `x > N` → **0**（不可能尾部，直接显著）。
- `x < 0`（即 count=0：ceil(−1)=−1）或 `dp<=0` 或 `dp>=1` → **1**（永不显著；注意 dp=1 也返回 1）。
- 其余：`x++` 后按 **P(X > x_orig)** 严格尾求和——首项 `log C(N,x_new) + x_new·log(dp) + (N−x_new)·log(1−dp)`（x_new = x_orig+1），循环 ni = x_new+1..N 递推 `dterm += log(N−ni+1) − log(ni) + (log dp − log(1−dp))`，logaddexp 累积公式照抄（:311-320 的 `Math.pow(Math.E,·)` 形状不得改写），最终 `exp(dlogprob)` 后夹取 [0,1]（:322-335）。
- `logbinomcoeff(ni,N)`（StatUtil.java:27-）：`dmax=max(ni,N−ni)`、`dmin=min(ni,N−ni)`；`Σ_{j=dmax+1..N} log j − Σ_{j=2..dmin} log j`，循环顺序照抄（Level B）；HashMap 缓存不影响值。
- 0<count<1 → x=0 → 计算 P(X≥1)；count=1 → ceil(0)=0 → 同为 P(X≥1)。
- **边界单测必须覆盖**：count=0 / 0<count<1 / count=1 / count>N / dp=0 / dp=1 / 常规区间；期望值用本机 JRE8 `jjs -cp stem.jar` 直接调用 `edu.cmu.cs.sb.core.StatUtil.binomialtail` 生成真实向量（新增 golden 向量文件）。

### 多重校正精确语义（STEM_DataSet.java:298-334）

- FDR（nfdr=1）：p 升序排序副本；`while pvalcopy[i] < (i+1)*alpha/nprofiles`（先乘后除的顺序照抄）走查，`dthresh` = 最后一个满足者（初始 0）；`significant = p <= dthresh`（**≤**）。⚠ 若全部 profile 都满足条件，Java 在 `pvalcopy[nprofiles]` 处 **ArrayIndexOutOfBounds 崩溃**——照复刻（抛等价异常），不得修复。
- 非 FDR：Bonferroni `alpha/nprofiles`、None `alpha`；`significant = p < dcorrectedalpha && count > 1`（**严格 <**，:331）。

### on-the-fly 置换生成（T≥9 且 n>0；STEM_DataSet.java:1148-1206 逐行钉死）

- RNG 消耗顺序：`Random(9873287)` 在基因循环外创建一次；每基因若 `!ballperms`：universe 路径消耗 `n` 个 nextDouble（`floor(nextDouble()*universe)` 后 `Arrays.sort`）；on-the-fly 路径每个置换消耗 `numcols−npermstart` 个 nextDouble。`ballperms=true` 时不消耗任何 RNG。
- 生成算法（每置换）：复位 `picked[0..numcols−npermstart−1]=false`；对输出槽 `nj = npermstart..numcols−1`：`nmove = (int)floor((numcols−nj)·nextDouble())`；在 picked 位图上做**跳过扫描** `while (ncount < nmove || picked[nk]) { if (!picked[nk]) ncount++; nk++; }`，退出时 nk 即选中项（等价于"选剩余未选中元素中跳过前 nmove 个后的那个"，nmove 均匀分布于 [0, 剩余数)；整数逻辑，两种实现严格等价，任选其一）；`picked[nk]=true`；`permutations[i][nj] = nk + npermstart`。
- 槽位 0..npermstart−1 保持 Java 数组零初始化的 0（t0 固定）。
- 合法性：每置换先查 `currpma[currperm[0]] != 0`，t0 缺失则跳过该置换（npermstart=1 时 currperm[0]≡0 恒合法）。
- 陈旧值 quirk：`logdata` 只在 `nvalindex>0` 时覆写——某列全缺失时保留上一列/上一置换的值，但该列 pma=0 会被掩码，故结果不受影响；照抄结构，不得"清理"。

### 输出格式（Level A/B 字符串比对依据）

- profiletable（ST.java:2944-2976）：Profile Model、`# Genes Assigned`、`# Gene Expected` 均走 Java 默认 `Double.toString`（如 `0.0,-2.0`、`45.0`、`42.7`）；p-value 走 `Util.doubleToSz`。
- cluster 列：非显著/未入簇 profile = −1（clusterassign 初始化 −1，:2950-2963）。

### result.metadata 增记（A2 裁决）

`legacy_with_replacement: bool`（universe 子抽样路径为 true）、`n_permutations_requested`、`permutation_mode: exact | subsample_universe | on_the_fly`。warning 策略（A2/A4）M4 落 CLI/API 层，不得改变计算结果。

## 1.7 M2 落地偏差记录（spec 规则：改动必须记录理由）

- `compact_profiles2(candidates, max_profiles, max_corr, max_unit_change)`：比 §1.4 钉版多 `max_unit_change`——Java 种子索引 ndown 读取字段 `nmaxchange`（:1582-1587），钉版签名未列全。
- `cluster_profiles(..., gene_counts, repeat_corr_sorted)`：球得分需要 `countassignments`、percentile 抬升需要 `sortedcorrvals`（:878-885, :961-965），钉版欠参数。
- `correct(pvals, alpha, method, counts) -> (significant, pvalues)`：非 FDR 的 `count > 1` 规则（:331-332）要求传入 counts；返回 pvalues 供 result 使用。
- 校正枚举名 `"fdr"`（02 §B3 旧写 `"fdr_stem"`），与 Java nfdr 一一对应，无行为差异。
- `random_state` 参数删除（第 3 轮 S3 裁决：无 "numpy" 第二模式）。
- `result.profiles` 为 `list[ProfileRecord]`；DataFrame 视图与 metadata 时间戳推迟到 M4 `to_csv`/打包时物化。
- M2 实现期发现并复刻的 2 个新 quirk：①`Util.getmedian` 用 `Arrays.sort` 双精度全序——NaN 排最后；log 模式重参照时 `vals[]` 只按 `pma[ncol]` 掩码、不掩码 `pma[nbegin]`（:1235/:1269 vs :1207），故 NaN/±Inf 真的会进入中位数（post-review 已逐行复核该路径，确认修复忠实）；②期望计数缩放是 `(expected·numrows)/ntotal`（:1373），乘除顺序影响 1 ulp。
- `_stats.correlation` 的 `math.sqrt` 已改为 Java 语义（负输入 → NaN 而非异常，Util.java:468/522）——M2 post-review MAJOR 修复，M1 遗留问题。
- 第 5 轮评审发现的 2 个 P2（M3 修复，2026-09-19）：①`test_golden.py` 的 Profile ID 断言实为 `str(i)`（枚举索引）而非 `str(rec.id)`——engine 现恰好 `ProfileRecord(id=i)` 故 M2 结论不受影响，但字段此前未被测试保护，已改为 `str(rec.id)`。②`legacy_with_replacement` 原仅 `subsample_universe` 为 true——`on_the_fly` 同为跨置换可重复的有放回抽样，语义改为 `mode != "exact"`（exact/subsample_universe/on_the_fly → false/true/true），并同步 permutation.py docstring。
- **M3 c14 挖出的新输出 quirk（2026-09-19，jjs + 文件字节双重实证）**：genetable 数值列的 `NumberFormat`（DecimalFormatSymbols 文档默认）——`+Inf` → `∞`（U+221E）、`-Inf` → `-∞`、`NaN` → U+FFFD（M2 既有钉死，长度 1）。Java 以**平台默认字符集**写表（oracle 机 = GBK），c14 冻结参照表中 `-∞` 为字节 `2D A1 DE`；金标 reader 因此以 GBK 确定性解码（ASCII 表两种解码等价）。`write_java_tables`（M4，Compatibility C）必须复刻 ∞/U+FFFD 形式并按运行平台默认字符集写文件。
- **P1 数据保真修复（第 6 轮，2026-09-19）：`filtering.merge_repeats` 无重复直通**。根因：Java 在**无重复数据集时不调用 mergeDataSets**——different_periods 直接 `theDataSetsMerged = theDataSet1`（ST.java:2577），same_period 的 else 分支是 `new STEM_DataSet(theDataSet1, theDataSet1)`（ST.java:2669，两参构造为纯引用别名包装、零语义）；而 Python `build_stem_dataset`（dataset.py，两种模式各一处，:146/:182 一带）无条件调用 `merge_repeats(...)`，`_cellwise_median` 的 `np.zeros` 初始化把 all-missing 格的存储 payload（log 模式 −Inf/NaN、normalize 模式 `0.0−v0` 填充值）清成幻影 `0.0`。修复 = `merge_repeats` 函数体首行 `if not repeats: return main`（两模式共用）+ docstring 记录两处 ST.java 行号。
  - **发现路径**：c13 幸存基因中缺末列者恰 **27 行**，`GENE_0008 values[-1]` 应为 `0.0−(−0.948)=0.948`（normalize 填充值）却落成 `0.0`；c14 单 spot 组 `S_0003/S_0015/S_0027/S_0039` 的 `values[-1]==-Inf` 同被零化。修复前红证据：`S_0003: values[-1]=0.0`、`GENE_0008: values[-1]=0.0`。
  - **安全性论证（下游四点）**：① `_normalized` 的 `log_ratio` 以 `copy=True` 产出新数组，直通无别名突变风险；② `merge_duplicates` 只读输入；③ 置换重参照消费 `ds.spot_data`（直通后位等不变——有重复路径本就原样引用 `main.spot_data`）；④ assign/filter_threshold 均按 pma 掩码读取。回归后 c01–c07/c12（有重复配置）gene_data 逐位不变，14 配置金标全绿。
  - **偏离专家字面设计（"只补一条保真通道"）的理由**：`return main` 让 Python 矩阵与 Java 本身对齐（同一引用语义，而非再造一份"保真合并矩阵"），并消除"合并矩阵"与"主矩阵"两份真相的同步负担——Java 的无重复路径本就是零语义别名，直通是最忠实的复刻。
  - 回归保护：`tests/test_golden_branches.py` 两条 payload 断言（c14/c13 锚点）+ `tests/test_units.py` 三条直通契约（`is main`、all-missing 保留 primary 值、无突变；**无 oracle，钉契约**，docstring 已注明）。

## 1.8 命名迁移记录（第 4 轮）

- Python 包目录 `src/stempy` → `src/pystemtc`；pyproject `name = "pystemtc"`；全部 import/文档字符串同步迁移。
- 异常类 `STEMpyValueError` → `STEMTCValueError`（品牌 PySTEMTC 的核心词为 STEM-TC；与包名 `pystemtc` 大小写解耦是可读性取舍，特此记录）。
- 仓库目录 `D:\stem\STEMpy` **不改名**：c09/c10/c11 fixture 配置内嵌 `STEMpy/tests/...` 生成期路径（Java 金标的 Data_File 字段），改目录会破坏 fixture 配置与证据链。
  - **2026-09-19 更新**：用户（项目所有者）主动将目录更名为 `D:\stem\pySTEMtc`，上述决策就此废止。原动机（保护证据链）仍然有效，处置方式改为：① c09/c10/c11 配置**内容一字不动**，其历史 `STEMpy/...` Data_File 前缀保留为生成期证据；② `test_golden.py::_resolve` 增加 basename 兜底——两处根目录都失配时回退到 `tests/golden/data/` 内置的同内容副本；③ `tools/gen_fixtures.py` 的 Data_File 改为按当前项目目录名动态生成（重新生成时写入新前缀，不再写死）；④ 文档/HANDOFF 中的路径同步更新。
- `tests/golden/java_configs/*.txt` 一字未动（冻结证据）。
- `FLOATERROR = 1e-7`（STEM_DataSet.java:15）；`compactprofiles2` 的加入条件 `dminval + FLOATERROR < dmaxcorr`（:1671）与停止条件（:1695）、tie-break（:1639, max|value| 小者）逐行复刻。
- `Util.correlation`（Util.java:427-472）的求和顺序、方差为 0 → 返回 0、无重叠列 → 返回 0 的语义照抄。

## 1.9 M3 金标扩展钉死（第 5 轮裁决 N2，2026-09-19）

**背景**：全部 12 个既有金标中 masked correlation 路径从未被触发——c09 synth6 虽含 ~8% 随机缺失，但 `Maximum_Number_of_Missing_Values=0` 把含缺失行全部过滤（DataSetCore.java:574-603 行级：t0 缺失即弃 + 缺失计数 ≤ nmaxmissing），幸存行全无缺失。原 c13 提案（"synth10 注入 8% 缺失、其余同 c11"）被第 5 轮评审驳回。金标 fixture 必须针对分支设计，不靠概率碰分支。

### c13_synth10_missing（on-the-fly × 缺失 × masked correlation）

- 新数据文件 `synth10m.txt`：T=10，300 spots（**新文件**，不改 synth10.txt），值 N(0,1) 固定种子（normalize 模式允许负值），保留 synth() 的 dup_every=10 重复结构。
- **确定性缺失模式**：行 i%3==2 在 0 基时间索引 (i%9)+1（该行集取值 {3,6,9}，三列轮转）置空；t0 永不缺失。i≡11 (mod 30) 的行既是重复组第二成员又含缺失 → 被 `Math.max` 合并救活（DataSetCore.java:716-723，merged pma 取 max），其余 ~90 行呈基因级缺失。
- 配置 = c11 基础上仅改：`Data_File`（synth10m）、`Maximum_Number_of_Missing_Values=1`。
- 目标分支：on-the-fly 置换（STEM_DataSet.java:1043 判定 T=10≥9）+ 基线缺失合法性检查（:1207 `currpmavalues[currperm[0]]!=0`，每缺失基因期望 ~5/50 置换被跳过）+ 置换中 masked correlation。
- normalize 模式无 NaN 减法污染：空 cell 落盘 data=0/pma=0（:508-510），缺失列的有限垃圾值被目标列 pma 掩码与合法性检查双重挡住。

### c14_log_missing（log 重参照 quirk × universe 路径 × 缺失）

- 新数据文件 `synth6d.txt`：T=6，240 spots = 100 个 dup 对（200 行）+ 40 个单 spot 基因；**值全部为正** uniform(0.5, 4.0)（3 位小数后仍 >0，规避 loader 规则 `btakelog && value<=0 → missing` 的意外触发，:513-521）；SPOT 列唯一（loader 对重复 spot 名抛异常，:437-447）。
- dup 对分两组钉住两条传播链（quirk 见 §1.7③，重参照掩码 STEM_DataSet.java:1210-1262）。**缺陷必须放在 dup 组第二行（行 2i+1，secondary），不能放主行**：`genespottimedata[·][0]` 按引用存主行、随后被合并中位数**原地覆写**（DataSetCore.java:675-679 vs :717-723，§1.2 别名的推论），主行的 −Inf/NaN 会被抹掉；secondary 保留合并前 log-ratio，缺陷才能进重参照 vals。
  - **组 1（±Inf 路线，对 0-49）**：secondary 在 0 基时间索引 2 置**空格** → log 模式 log(0)=−Inf 进 spot 序列；置换把索引 2 移到基线时，secondary 在场列贡献 `finite−(−Inf)=+Inf` → vals=[+Inf, finite] → getmedian 偶数取平均 = **+Inf** → 下游 `sqrt(Inf−Inf)=NaN` → dcorr=NaN 被跳过（:1353 注释 "if dcorr na then numbest not advanced"）→ ntotalassignments 分母变小。
  - **组 2（字面 NaN 路线，对 50-99）**：secondary 在 0 基时间索引 2 放**负值**（如 −0.7）→ loader 记 pma=0 但 data 保留负值（**DataSetCore.java:530-533** 的 `btakelog && value<=0` 规则）→ log(负)=**NaN** 进 spot 序列 → vals 得真 NaN → 中位数 NaN。
- 配置：`Log normalize data`、`Maximum_Number_of_Missing_Values=1`、`Permutation_Test_Should_Permute_Time_Point_0=true`、`Number_of_Permutations_per_Gene=50`、`Minimum_Absolute_Log_Ratio_Expression=0.5`、`Change_should_be_based_on=Maximum-Minimum`（显式写，不依赖默认）。**universe=6!=720**（permute_t0=true 走 `generatepermutations`，:1093/:1468；120=(6−1)! 属于 permute_t0=false 的 `generatepermutationsExcept0`，基线恒 t0、缺失列永远当不了基线、quirk 永不触发——第 5 轮评审修正），50 < 720 → subsample_universe 路径。
- dup 合并语义（已验证）：merged pma = Math.max（:716-723）→ 组 1/组 2 的 merged 行无缺失、filterMissing 放行；置换合法性检查读 merged pma（:1153）→ 基线=缺失列的置换**合法**、重参照块必然运行。

### 生成与断言

- 生成方式：`gen_fixtures.py --fixtures c13_synth10_missing,c14_log_missing` 只生成这两个配置 + 两个数据文件（**绝不重写** c01-c12 配置、synth6/synth10、vectors；且拒绝以冻结配置名调用）；随后把新配置复制进 scratch 目录对**该目录**跑 `java -jar stem.jar -b .batch_scratch <outdir>`（目录模式，裸文件名 → 输出命名正确，:1268-1282）。**禁止两种做法**：① 整目录重跑——c09/c10/c11 的历史 `STEMpy/` 前缀指向已不存在的目录，会被 runBatchDir 捕获 FileNotFoundException 后静默跳过（:1300-1311）；② 把单个配置**文件**直接传给 `-b`——`szcurrentDefaultFile` 会带上完整输入路径（:1289/:1294），输出名 = 完整路径去掉扩展名（:2947/:2989），FileWriter 静默失败（执行期实证，post-review 回填）。c01-c12 参照表以"根本不碰"保证不变。
- Data_File 前缀约定：新配置写当前目录名 `pySTEMtc/tests/golden/data/...`；冻结 c09/c10/c11 的 `STEMpy/` 前缀保留为证据（HANDOFF D8）。
- 测试侧分支到达断言（`tests/test_golden_branches.py`，评审要求：不能只靠"测试通过"）：c13 断言 `permutation_mode=="on_the_fly"` 且 ≥10 个幸存基因的基因级序列含 ≥1 个非 t0 缺失；c14 断言 `permutation_mode=="subsample_universe"` 且组 1、组 2 各 ≥10 个幸存 dup 基因（spot 级在索引 2 缺失）。

## 1.10 M4 schema v2 与发布工程（第 6 轮定案，2026-09-19）

### to_dict schema v2 全字段表（实现：`src/pystemtc/result.py` + `engine.py`）

顶层键**恰为** 11 个：`schema_version`、`reference`、`generator`、`config`、`input`、`metadata`、`profiles`、`gene_assignments`、`filtered_genes`、`clusters`、`timing`。

| 顶层键 | 内容 |
|---|---|
| `schema_version` | `2` |
| `reference` | `{"software": "STEM", "version": "1.3.14"}`（行为 oracle，与 package 版本解耦） |
| `generator` | `{"package": "pystemtc", "version": <pystemtc.__version__>}`（package 名全小写，不参与品牌大小写） |
| `config` | **显式列举**的 STEMConfig 算法参数键（`result.CONFIG_ALGORITHM_KEYS` = STEMConfig 全部字段 − `data_file`/`repeat_files`；不用 asdict 剔除法——新增配置字段必须是一次显式 schema 决策） |
| `input` | `{"form": "path"\|"dataframe"\|"stem_dataset"`, `data_file`, `repeat_files`, `time_points(= ds.sample_labels)`}；STEMDataset 直注入形态 `data_file=None, repeat_files=[]`（该路径忽略 replicates 参数，engine docstring 已注明）；DataFrame 形态 `repeat_files=[None×n]` |
| `metadata` | `input_form`、`num_genes`、`num_time_points`、`num_profiles`、`num_candidate_profiles`、`permutation_mode`、`n_permutations_requested`、`legacy_with_replacement`、`sample_labels`、`timestamp`（fit 时一次，UTC ISO-8601 秒级）；**删除** `software`/`reference` 两键（职责上移 `reference`/`generator`） |
| `profiles` | 原样（id/model/cluster/n_assigned/n_expected/p_value/significant） |
| `gene_assignments` | `{gene, probe, profile_ids: list[int], values, value_states, present}`；旧 `profile` 字符串字段由 `profile_ids` 列表取代 |
| `filtered_genes` | `[{gene, probe, reason}]`（reason ∈ repeat_correlation/missing/threshold；无 Java 对应物，不进 `write_java_tables`） |
| `clusters` | `[{"id": i, "profile_ids": [...]}]`（i = 生成序） |
| `timing` | 引擎 stage 计时 dict（键表见下） |

### `_encode_value(value, present)` 真值表（钉死优先级：先按存储 double 分类）

| 存储 double | state | values |
|---|---|---|
| NaN（任意 pma） | `"nan"` | `null` |
| +Inf（任意 pma） | `"positive_infinity"` | `null` |
| −Inf（任意 pma） | `"negative_infinity"` | `null` |
| 有限 & pma==0 | `"missing"` | 保留填充值 |
| 有限 & pma!=0 | `"finite"` | 原值 |

不变量：`values[i] is null ⟺ state ∈ {nan, positive_infinity, negative_infinity}`；`state=="missing" ⟹ present==False`、`present==True ⟹ state=="finite"`。注意非有限 payload 落在 all-missing 格（present=False）时 state 报**非有限态**而非 missing——c14 的 `present=False ∧ −Inf` 是实证（S_0003 末列）。**`values` 是无损 Java 矩阵快照，writer（未来）消费 STEMResult 内部 floats**：由 (value, state, present) 足以精确重建 Java genetable 任意格（含 `""` 判别、`-0.00` 与 ∞/U+FFFD 渲染）。严格 JSON：`json.dumps(to_dict, allow_nan=False)` 必须成功（测试钉死）。

### timing 键表（`time.perf_counter` 纯环绕现有阶段，不改任何计算顺序）

`input_read`（主 + 重复读取）→ `normalize_filter`（`build_stem_dataset` 全链）→ `profile_generation` → `assignment`（含 tallyassignments）→ `permutation`（expected_counts）→ `significance`（p 值 + 校正）→ `clustering` → `wall`（fit 全程）；STEMDataset 直注入路径前两键报 `0.0`。

### 版本矩阵定案

`requires-python = ">=3.11"`；CI matrix 3.11/3.12/3.14（Windows+Ubuntu）；依赖下界 `numpy>=2.4,<3`、`pandas>=3.0,<4` 为 **provisional**（冻结条件 = 3.11 CI 绿，即 M6 push 之后）。

### 发布文案模板

> "Compatibility-first implementation. The V1.0 core intentionally favors behavioral fidelity over vectorized performance." + 实测数字（`tools/bench.py` 三档：300×6T 0.3s / 3000×10T 29.3s / 10000×10T 53.5s wall；peak RSS ~870 MiB）。**870 MiB 不得称轻量**。

### format_java_double 晋升

现居 `tests/test_integration_fixture.py` 的 `NumberFormat` 复刻（ENGLISH、2 位小数 HALF_EVEN、千分位、NaN→U+FFFD、±Inf→±∞）在 **writer 轮**晋升 `src/pystemtc/javaformat.py`（`write_java_tables` 的格式化内核），测试改为 import，行为不变。


## 2. 解冻区（unfrozen，按第 6 轮专家裁决重整，2026-09-19）

1. ~~**Level B 容差数值**（暂定：expected 相对 1e-12；p-value 相对 1e-9 或绝对 1e-12；correlation 相对 1e-12）~~——**第 6 轮划除**：容差数值条款被第 5 轮 B 两层冻结（§0）取代；B-internal 不设数值容差判据（B-output 打印值全等为主判据，B-internal 只要求不得反噬 A 层）。
2. ~~金标最终严格度~~ **已于第 5 轮定案并移回冷冻区**：B 两层定义（B-output exact / B-internal 不得反噬 A），见 §0。
3. `STEMInput.from_gene_matrix(...)` 便利构造器（V1.1；不得污染 compatibility core）。
4. 裸 `ndarray` 入口（V1.1+，需自带 schema 参数）。
5. K-means（V1.1，`Random(2211)` + reservoir sampling 复刻）。
6. ~~PyPI distribution 名与 import namespace~~ **已于第 4 轮定案并移回冷冻区**：`pystemtc`（PyPI API 404 实证 2026-09-19）；发布前复检要求已写入 §0。
7. **JRE 17 漂移 characterization**：**阻塞——本机仅有 JRE 1.8.0_451，无 JRE 17**；待用户安装后执行（结果只作附加证据，JRE 8 仍是唯一 oracle）。warning 策略已定案，**文案冻结原文移入 §0**（M5 warning 冻结），本条只保留 JRE 17 环境阻塞本身。
8. **CLI（第 5 轮定向，M4）**：`pystemtc run --config <defaults.txt> --output <dir>` 与 `pystemtc batch --config-dir <dir> --output <dir>` 双入口；defaults.txt 保持一等输入；不复刻 `stem.jar -b` 的历史参数形式。**裁决（退出码 0/1/2、batch 失败继续 + stderr 总结、stdout 简洁成功）已落 §0，实现于下一轮（CLI 轮）**。
9. **`to_dict()` schema**：**v2 已实现（第 6 轮，全字段表见 §1.10），待 post-review 最终确认**；v1 提案（schema_version=1、`reference_version` 字符串、仅 null 编码）被 v2 取代（`reference` 对象、`value_states` 五态、`profile_ids`、`input`/`timing` 段）。
10. **Python 版本矩阵**：**requires-python 已定 3.11**（第 6 轮，CI matrix 3.11/3.12/3.14）；**依赖下界 provisional**（`numpy>=2.4,<3`、`pandas>=3.0,<4`），冻结条件 = 3.11 CI 绿（M6 push 后）。
11. **Compatibility C 数据保真**：数据通道已修复（P1，§1.7：无重复直通 + all-missing payload 保留），`write_java_tables` 的 writer 实现待下一轮；本条在 writer 实现获认可后关闭。

## 3. 工件与再生成

- `tests/golden/java_configs/`（14 组配置：c01–c12 + c13_synth10_missing + c14_log_missing，设计钉死见 §1.9）、`java_reference/`（28 张表 + `_batch_stdout.log`）、`java_rng/vectors.txt`、`java_statutil/vectors.txt`、`data/synth6.txt|synth10.txt|synth10m.txt|synth6d.txt`。
- 再生成：全量 `python pySTEMtc/tools/gen_fixtures.py`（需 JRE 8：`C:\Program Files\Java\jre1.8.0_451\bin`；注意全量会按当前目录名重写配置 Data_File 前缀）；**增量** `python pySTEMtc/tools/gen_fixtures.py --fixtures <新配置名>`（拒绝冻结配置名；scratch 目录模式批跑，§1.9）——**禁止整目录重跑**（c09/c10/c11 历史前缀会 FileNotFoundException 被静默跳过）、**禁止把单个配置文件直接传给 `-b`**（输出名嵌入输入路径，静默失败，§1.9）。
- fixtures 提交入库，CI 不依赖 Java。

## 4. 里程碑（不变）

M1 = §1.3（本轮）；M2 = §1.4 + engine；M3 = 金标分层验收全绿；M4 = config/CLI/result.to_dict + 文档 + 打包。V1.1 = K-means + plot + 便利构造器。
