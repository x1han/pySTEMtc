# STEMpy 专家方案评审（第 1 轮）

> 命名迁移注记（第 4 轮，2026-09-19）：项目正式定名 **PySTEMTC**（PyPI/import/CLI = `pystemtc`）。本文为历史评审记录，保留当时"STEMpy"称谓；现行命名与最高原则以 `03_v1_implementation_spec.md` §0 为准。

- 评审人：ZCode（GLM）
- 日期：2026-09-19
- 评审依据：**本地源码 v1.3.14**（`D:\stem\sourcecode`，72 个 Java 文件）+ `stem.jar` + `defaults.txt` + `readme.txt`。所有结论均给出 file:line 证据，可直接回溯。
- 专家方案引用的资料来源：STEM 官网（ernstlab.github.io/STEM）、v1.3.15 手册、GitHub `jernst98/STEM_DREM`。

---

## 总体结论

**方案通过，无 P0 问题。** 专家对 STEM 能力边界的描述、V1 范围收缩（纯 time-course 核心引擎，GO/比较/绘图后置）、"core 不依赖绘图/GUI、结构化结果对象、CLI 只是 adapter"的架构判断，全部与源码事实相符，予以确认。

初版核验发现 3 个 P1 级修正；**第 2 轮评审（2026-09-19）又指正初版评审自身的两处问题，已修正**：(1) 验收标准由"逐位一致（exact-match）"改为 **Level A（离散结果 exact，必须）+ Level B（连续量 exact 优先 + 明确容差）** 两层——浮点 transcendental 运算跨平台不保证末位一致，不能承诺 bitwise；(2) "T<9 即精确检验"表述有误，更正为"物化全排列 universe + 固定种子子抽样"，默认 50 次下精确检验边界为 T≤4（置换 t0）/ T≤5（固定 t0）。

---

## 一、专家关键论断逐条核验

| # | 专家论断 | 判定 | 证据 |
|---|---------|------|------|
| 40 | 原版支持 command-line batch，输出 gene table 和 profile table；但 batch 仍要求机器有 display | **全部正确** | `ST.java:5813` main() 解析 `-b batchInput batchOutputDir`；`ST.java:512-521` batch 构造器；输出写入 `<name>_profiletable.txt` 与 `<name>_genetable.txt`（`ST.java:2923-3036`）。display 依赖属实：`class ST extends JFrame`（`ST.java:23`），batch 构造路径仍会实例化 JComboBox/JButton/JFileChooser 等 Swing 组件（`ST.java:208-227, 437-488, 489`），`-Djava.awt.headless=true` 下会抛 HeadlessException，Linux 无显示环境需 Xvfb |
| 3 | 三种标准化：log2(v/v0)、vt−v0、不标准化补 0 | **正确** | `DataSetCore.java:733-763`（logratio2）、`:495-497`（合成 0 列）；参数 `Normalize_Data`（defaults.txt:14） |
| 2 | 重复实验分"同一时段/不同时段"，平均/标准化顺序不同 | **正确** | 不同时段：每套重复各自 normalize → 逐格中位数合并 → 重复间相关性过滤（`ST.java:2765-2783`，`DataSetCore.java:848-884`）；同一时段：原始值先中位数合并 → 再 normalize，无相关性过滤（`ST.java:2885-2893`） |
| 6/7 | 候选 profile 生成 + 用 Maximum_Correlation 避免过相似 + 数量上限 | **正确，补充机制细节** | 全枚举 `generatemodelprofilesall`（`STEM_DataSet.java:1004`）；候选数上限超 100 万时走固定种子抽样 `generatemodelsampled`（`:812`，`Random(3733246)`）；最终精选是贪心 max-min 多样性算法 `compactprofiles2`（`:1561-1711`），种子 profile 恒为 {0,1,2,…,L−1} |
| 8 | 允许并列最佳 profile | **正确** | `findbestgroupassignments`（`STEM_DataSet.java:1742-1751`）保留全部 argmax profile，每个基因对各并列 profile 贡献权重 1/k（`tallyassignments` `:199-208`） |
| 9/10 | 每基因随机排列时间点→重新标准化→重新匹配；可选是否置换 t0 | **正确，补充关键机制** | 见下文 P1-3：置换移动了基准时间点时，会用**已标准化**的 per-spot 序列（`genespottimedata` 有效内容）**重新减基准**再跨 spot/repeat 取中位数（`STEM_DataSet.java:1216-1256`；存储语义唯一以 `03_v1_implementation_spec.md` §1.2 为准）。"是否置换 t0" = `generatepermutations` vs `generatepermutationsExcept0`（`:1093/:1097`） |
| 11 | observed vs expected 计算 profile 显著性，支持 Bonferroni/FDR/不校正 | **正确，公式已补齐** | p = P(X ≥ count)，X ~ Binomial(n_genes, expected/n_genes)，`StatUtil.binomialtail`（`StatUtil.java:286-336`）；多重校正在 `computePvaluesAssignments`（`STEM_DataSet.java:287-335`）。注意其 "FDR" 是 step-down 实现，**不是 Benjamini-Hochberg** |
| 12 | 显著 profile 聚类，固定阈值或重复噪声 percentile | **正确，含一个隐藏 quirk** | `clusterprofiles`（`STEM_DataSet.java:870-997`）。quirk：percentile 默认 0，且**只要提供了不同时段重复数据，阈值就会被抬高到全部保留基因重复相关性的最小值**（`:878-885`），不只是 0.7 |
| 14 | K-means 保留目标函数最优的一次 | **正确** | `kmeans()`（`STEM_DataSet.java:413-701`）：20 次重启（`Random(2211)` 固定种子 + reservoir sampling 初始化），目标为簇内平方距离和，最终中心按字典序排序定 cluster ID |
| 5 | 预过滤基因文件让这些基因进入 GO background | **方向正确、表述含糊（P3）** | 该文件只在 GO 机器内读取，向 GO universe 追加 gene/probe 映射（`GoAnnotations.java:864-929`），并回填 filtered 表用于显示；**不**改变聚类输入。GO 阶段启动时再精确定义 |
| 29-31 | 双条件比较 | **确认 V1 排除正确** | 比较分析**只存在于 GUI**（`CompareGui.java`），batch 链路完全没有接：`Comparison_*` 参数被解析但 batch 从不使用（`ST.java:1932-1991`） |
| 45 | GUI 专属交互不移植 | **正确** | 纯 Swing/Piccolo/Batik 渲染层，数值计算零依赖 |

专家没有提到、但核验中确认的两点：
1. **【第 2 轮更正】T<9 个时间点时置换 universe 被完整物化，但不必然精确**（`bgenallperms`，`STEM_DataSet.java:1043`，`ALLPERMSTHRESH=9`）。初版写成"≤8 时间点即精确检验"，是错的：`nselectedperms = min(n_permutations, universe)`（`:1100`），仅当其 ≤0 或等于 universe 时才全部使用（`ballperms`，`:1102`）；否则**每个基因**在基因循环内从共享 `Random(9873287)` 流抽 `floor(nextDouble()×universe)` 个索引并 `Arrays.sort`（`:1148-1168`），**有放回**，重复索引按重复计数——这些都必须复刻。默认 50 次时的精确检验边界：`permute_t0=true` → T≤4（4!=24≤50）；`permute_t0=false` → T≤5（(T−1)!=24≤50）；`n_permutations=0` 恒精确。样例数据 g27 为 5 个时间点：默认配置落在子抽样路径，`t0 固定` 配置落在精确路径，两种金标 fixtures 都已生成。
2. **GO 步骤在 batch 中总会执行但无 annotation 文件时是空转**（`ST.java:2801-2806`，`GoAnnotations.java:683`）——V1 直接砍掉无副作用。

---

## 二、P1 修正（本轮已解决，写入架构文档）

**P1-1 版本钉死。** 专家引用官网/1.3.15 手册/GitHub master，但本地快照是 **v1.3.14**（readme.txt:1，自带 stem.jar）。金标测试一律对本地 `stem.jar`（`java -mx1024M -jar stem.jar -b ...` 可直接运行），GitHub master 不作为对照基准。若未来要兼容 1.3.15 行为差异，另行建立版本开关。

**P1-2 【第 2 轮修正】验收标准分层：Level A（离散 exact，必须）+ Level B（连续量 exact 优先 + 容差兜底）。** 初版声称可"逐位一致"，承诺过头，撤回。仍然成立的部分：STEM 三个随机环节全部**固定种子**——置换 `Random(9873287)`（`STEM_DataSet.java:1131`）、模型 profile 抽样 `Random(3733246)`（`:816`）、K-means 重启 `Random(2211)`（`:447`）；`java.util.Random` 是规范公开的 48 位 LCG，Python 可逐位复刻。因此**离散/逻辑结果**（profile model、profile ID、置换索引、基因分配、簇成员、observed count）可以要求 exact-match。但**浮点 bitwise 不承诺**：`Math.sqrt` 按规范正确舍入尚可确定，而 `Math.exp/log/pow` 跨 JVM/libm 不保证末位一致（`StatUtil.binomialtail` 在 log 空间累加，StatUtil.java:286-336），浮点累加顺序也须逐处复刻。故 Level B（correlation、expected counts、p-value）以 exact 为目标、CI 同时断言明确定义的容差（数值见架构文档解冻区，M2 首批对拍后定稿）。若未来要证明 p-value bitwise exact，必须单独对拍 Java `Math` 调用，不能由 RNG 一致推出。

**P1-3 数据模型必须保留 per-spot/repeat 序列（第 2 轮精化：是"已标准化"的序列）。** 专家的功能表没有体现：置换检验在基准时间点被换走时，用**已标准化（logratio2 之后）**的 per-spot 数据重算差值并跨 spot/repeat 取中位数（`STEM_DataSet.java:1216-1256`；`genespottimedata` 在 `logratio2` 之后、`averageAndFilterDuplicates` 内填充，`DataSetCore.java:672-703`；重复时经 `generepeatspottimedata`，`DataSetCore.java:772-830`）。浮点上 `(v_c−v_0)−(v_begin−v_0)` 与 `v_c−v_begin` 不等价，存储时点必须照抄 Java，不得用代数等价式替换。因此内部数据结构必须同时携带：标准化后 per-spot 序列、缺失标记矩阵 `pma`、spot→gene 归属、重复文件分组。V1 输入契约相应收紧：只收原始表达值，不提供预标准化入口（见 `03_v1_implementation_spec.md` §1.1）。

---

## 三、P2 清单（按用户指示不过度处理，实现时顺手解决）

1. **默认参数镜像 Java**：专家 API 示例 `n_permutations=1000`、`max_profile_correlation=0.8` 与 Java 默认（50、1.0，defaults.txt:36-37）不符。STEMpy 默认值一律镜像 defaults.txt，保证金标可比；兼容模式之外的"更好默认值"留给用户显式传参。
2. **包名**：专家示例用了 `pystem`，用户已定名 **STEMpy**（PyPI 名 `stempy`）。以用户为准。
3. **FDR 语义警示**：STEM 的 "False Discovery Rate" 选项是自定义 step-down 实现（`STEM_DataSet.java:298-316`），非 BH/Yekutieli。按原样复刻 + 文档注明，不"修正"它。
4. **T=1 边界**：单时间点在原版进入 GO-only 模式（`ST.java:2707-2746`）。V1 不实现 GO，对 numcols<2 直接抛带说明的错误。
5. **浮点复刻**：Java for 循环是朴素顺序累加，NumPy `np.sum` 是成对求和，会有 ulp 级差异，在相关性并列判定处可能翻转 assignment。金标相关路径用顺序累加复刻（详见架构文档 §4）。

---

## 四、风险登记

| 风险 | 等级 | 对策 |
|------|-----|------|
| 浮点求和顺序差异导致并列相关性的 tie-break 翻转 | P1（影响 exact-match） | 复刻 Java 的累加顺序；并列处复刻 `FLOATERROR` 容差逻辑（`compactprofiles2:1671`） |
| `FLOATERROR` 具体数值未在本轮抄录 | P2 | 实现阶段从 `STEM_DataSet.java` 抄录常量并写入文档 |
| Java HashMap/TreeSet 遍历顺序影响输出顺序 | P2 | 输出前均按显式排序（profile ID 升序等，`:1703-1710` 已确认）；实现时逐处核对 |
| K-means reservoir sampling 初始化复刻 | P2 | V1.1 再做（K-means 已定暂缓） |

---

## 五、致专家团队的反馈（可直接转发）

1. 方案整体确认：V1 范围（time-course 核心，GO/比较/绘图后置）、core/adapter 分层、结构化结果对象——全部同意，且经源码逐条验证无误。
2. 修正+确认：三个随机环节固定种子（9873287 / 3733246 / 2211），`java.util.Random` LCG 可复刻；验收标准定为 **Level A（离散 exact，必须）/ Level B（连续量 exact 优先 + 容差兜底）**，不承诺浮点 bitwise。金标 fixtures 对本地 v1.3.14 stem.jar 用 batch 模式生成（12 组配置已入库）。
3. 补充（第 2 轮精化）：T<9 时置换 universe 全物化但默认仍抽 50（精确仅当 T≤4 / T≤5 或 n=0）；抽样是每基因独立、有放回、`Arrays.sort` 后使用，须逐位复刻。置换移动基准点时，用**已标准化**的 per-spot 序列重算差值 + 跨 spot/repeat 取中位数（`genespottimedata` 在 `logratio2` 之后填充，DataSetCore.java:672-703）。数据模型需保留 per-spot 序列与缺失标记；V1 输入契约只收原始数据，不提供预标准化入口。
4. 修正：你 API 示例中的默认参数请改为镜像 Java defaults（n_permutations=50、max_corr=1.0、clustering_corr=0.7、max_profiles=50、max_unit_change=2、alpha=0.05、Bonferroni）。
5. 确认：两条件比较在 batch 链路中完全缺失（GUI-only），V1 排除正确；Pre-filtered 文件的 GO background 说法方向正确，GO 阶段再精确化。
6. 无阻塞性问题。请专家按此更新后，下一轮直接进入实现阶段拆分。

---

## 六、文献事项

本轮所有论断均可对本地源码与手册直接验证，未引用需要外部核实的文献，故未调用 consensus API（本会话也未挂载 consensus MCP 工具）。进入 GO/enrichment 阶段、需要引用 Ernst & Bar-Joseph 原始方法论文时，再通过 consensus 获取并建立引用。

## 七、下一步

第 2 轮评审结论：核心方向收敛，3 个 P1 修正已完成；输入数据契约与验收分层已钉死，升级为 `03_v1_implementation_spec.md`（常温区/解冻区/冷冻区结构）。M1 按 Large 级流程（spec 预审 → implementer → verifier → post-review）启动。
