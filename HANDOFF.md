# PySTEMTC — Session Handoff

> 按 dictionary-of-ai-coding 的 Handoff 定义编写：本文件把一个会话的上下文移交给下一个会话，**没有回路**。
> 评判标准：一个**零上下文**的新会话拿这份文件应当能 (1) 理解项目是什么、(2) 跑通验证、(3) 不重新翻案已定决策（每条决策都写了为什么）、(4) 知道下一步做什么、(5) 知道什么不能碰。
> 最后更新：2026-09-19（M2 正式 GO + 第 5 轮裁决落盘 + M3 启动：c13/c14 金标扩展、git+CI、LICENSE）。

---

## 1. 这个项目是什么（一段话）

**PySTEMTC**（PyPI/import/CLI = `pystemtc`）是 Java 工具 **STEM v1.3.14**（Short Time-series Expression Miner，Ernst/Patek/Bar-Joseph，GPL-3.0，针对 ~≤8 时间点的时序基因表达聚类）的 **headless Python 兼容实现**——只移植 time-course 计算核心，不做 GO 富集、GUI、绘图、双条件比较。

**最高原则（Compatibility First，冻结）**：本地 STEM v1.3.14 是**唯一行为 oracle**。这不是"受 STEM 启发的重设计算法包"；所有设计争议先问"Java v1.3.14 怎么做"，不问"Python 里通常怎么做"。优先级链：**Java 行为一致性 > 代码简洁 > 运行速度 > Pythonic**。

## 2. 必读顺序（零上下文会话从这里开始）

| 序 | 文件 | 作用 |
|----|------|------|
| 1 | `docs/03_v1_implementation_spec.md` | **现行规范**：§0 冷冻区（原则/范围/验收）+ §1.2 数据模型硬约束 + §1.5 浮点纪律 + §1.6 钉死的 Java 边界语义 + §1.7/§1.8 偏差与命名迁移记录 |
| 2 | `docs/02_core_callgraph_and_v1_architecture.md` | Java v1.3.14 端到端调用图（file:line 级）+ 架构 + 金标方案 |
| 3 | `docs/01_expert_plan_review.md`、`docs/04_m1_report_and_open_questions.md` | 历史评审记录（带迁移注记；只读背景，不承载现行语义） |
| 4 | `HANDOFF.md`（本文件） | 状态 + 决策 + 下一步 |

## 3. 环境与复现（全部实测过）

- 代码：`D:\stem\pySTEMtc`（2026-09-19 由用户自 `D:\stem\STEMpy` 更名，处置见 §5-D8）；包在 `src/pystemtc/`，测试在 `tests/`。
- Python 3.14.3（`python`），numpy 2.4.6 + pandas 3.0.3，已 `pip install -e .`（包名 `pystemtc` 0.1.0）。
- Java：JRE 1.8.0_451（`C:\Program Files\Java\jre1.8.0_451\bin`，含 `jjs.exe`；**无 javac**）；oracle jar = `D:\stem\stem.jar`；Java 源码 = `D:\stem\sourcecode\edu\cmu\cs\sb\{stem,core}`（v1.3.14）。
- 验证命令（当前全绿）：
  ```bash
  cd /d/stem/pySTEMtc
  python -m pytest -q          # 96 passed（52 M1 + 20 M2 单测 + 24 金标）
  grep -rnE "np\.(sum|mean|std|dot|corrcoef|add\.reduce|einsum)\(" src/pystemtc/   # 必须为空
  ```
- 金标重生成（需要 JRE 8，Windows 有显示环境即可）：`python pySTEMtc/tools/gen_fixtures.py`（在 `D:/stem` 下运行）→ `tests/golden/`（12 配置 batch + 24 张表 + RNG/StatUtil 向量）。**fixtures 是冻结证据，不许编辑**（c09/c10/c11 的历史路径前缀见 §5-D8）；CI 不依赖 Java。

## 4. 当前状态（截至 2026-09-19，全部有验证记录）

- **M1（数据入口链）完成**：解析→三模式标准化→重复基因中位数合并→两种重复模式→相关过滤→缺失/阈值过滤 + `JavaRandom` 逐位复刻。5 个配置的 genetable 与 Java 输出**字符串级一致**。
- **M2（核心算法）完成**：candidate profiles（枚举+抽样+compactprofiles2 贪心）、基因分配（并列 1/k）、置换（三条路径：全排列精确 / universe 有放回子抽样 / T≥9 on-the-fly）、binomial tail 显著性 + 三种校正、显著 profile 聚类、engine 串联。**12/12 配置：Compatibility A 全 exact，B（expected/p 值）达到 Java 打印字符串全等（0 mismatch）**。
- 闸门流程（每里程碑）：预审 → implementer → 独立 verifier → post-review → 主会话修 findings。M1/M2 均走完，verifier 均独立复跑并 ALL GREEN。
- **明确不外推**：GO/enrichment、双条件比较、K-means、绘图、`to_csv` 未实现；金标仅覆盖本地样例与合成数据；大规模性能未评估。
- **第 5 轮裁决（2026-09-19）：M2 正式 GO**。N1-N12 处置见 docs/05 §7；Compatibility B 冻结为两层定义（spec §0）；c13/c14 金标扩展设计钉死（spec §1.9）；git+CI 建立并基线提交；LICENSE（GPL-3.0）落库。JRE 17 characterization **阻塞**（本机无 JRE 17）。

## 5. 已冻结的决策（不要重新翻案；每条带为什么）

- **D1 命名 = PySTEMTC / `pystemtc`**。为什么：`stempy` 被 Kitware 4D-STEM 包占用（v3.5.0，活跃发布），`pystem` 也被占；`pystemtc` 经 PyPI JSON API 实证 404（2026-09-19）。**发布前必须再走一次实时接口**（检索不到 ≠ 占坑）。品牌在 `stemtc` 与 `pystemtc` 之间由专家团定夺为后者，不再讨论。
- **D2 Compatibility First**（见 §1）。为什么：本项目的验收定义就是与 Java 的科学结果一致；"基本一致"没有工程含义。
- **D3 100% 一致清单**：过滤后保留/剔除的 gene、model profiles 与 ID 顺序、gene→profile 分配（含并列与顺序）、observed tally（double 允许分数，**不得称整数**）、显著判定、cluster 成员与 ID、genetable Profile 列、**全部 Java legacy quirk**。任一不同 = TEST FAIL——相关系数差 1e-15 导致 assignment 翻转也算失败。为什么：这些差异改变生物学解释。
- **D4 浮点末位豁免仅限** correlation / expected count / p-value，且必须同满足：误差 ≤ 容差、显著性结论不变、assignment 不变、cluster 不变。**浮点末位可以不同，科学结果不能不同**。为什么：sqrt/log/exp 与顺序累加的跨运行时末位差不可避免；但其传播若触碰结构结果即为兼容性失败，必须追查而不是放宽。
- **D5 验收三级 Compatibility A/B/C**（03 §0；取代旧 Level A/B）。A=结构结果 exact；B=数值优先"Java 打印值==Python 打印值"，容差不得反噬 A；C=文件输出逐字段一致（实现物是 M4 `to_csv`）。当前 A 已全 exact、B 已打印值全等。
- **D6 quirk 照抄不修正**：有放回置换子抽样、`FLOATERROR=1e-7`、tie-break 取 max|value| 小者、FDR 全显著时 Java 数组越界崩溃（Python 复刻为等价 IndexError）、`getmedian` 的 NaN 排序、`(expected·numrows)/ntotal` 乘除顺序、genetable 最后一列无条件输出、`NumberFormat(NaN)=U+FFFD`（jjs 实测裁决过两个 reviewer 的争议）等，全集见 03 §1.6/§1.7。为什么：任何"修正"都改变科学结果，违反 D2。
- **D7 浮点纪律**：Java 顺序累加一律显式标量循环；`np.sum/mean/std/dot/corrcoef/add.reduce/einsum` 在 `src/pystemtc/` 数值路径**禁止**（CI grep 清单）。为什么：成对求和等重排会改变 1 ulp，进而可能翻转并列判定。若优化需要改变它：**先有 golden → 优化 → 重新 golden**。
- **D8 项目目录现为 `D:\stem\pySTEMtc`**（2026-09-19 用户自 `D:\stem\STEMpy` 主动更名——用户为主，原"不改名"决策废止）。原决策的动机（保护证据链）仍然有效，处置如下：① c09/c10/c11 金标配置**内容一字不动**，历史 `STEMpy/tests/...` Data_File 前缀保留为生成期证据；② `test_golden.py::_resolve` 增加 basename 兜底，两处根目录失配时回退 `tests/golden/data/` 内置同内容副本；③ `gen_fixtures.py` 按当前目录名动态生成 Data_File 前缀；④ 文档/HANDOFF 路径同步。不要把配置里的旧前缀当 bug 去"修"。
- **D9 异常类名 `STEMTCValueError`**（非 PySTEMTCValueError）。为什么：可读性取舍，已记录于 03 §1.8。
- **D10 V1 范围**：不做 GO/enrichment、annotation、chromosome/GFF、双条件比较、GUI、plotting、K-means（K-means 在 V1.1，seed 2211 + reservoir sampling 复刻）。输入只收**原始表达值**、行=spot；不接受预标准化矩阵、不提供裸 ndarray 入口。
- **D11 Java 源码 > 论文/手册；本地 v1.3.14 > GitHub master**。为什么：行为 oracle 是本地 jar+源码；论文与手册是描述，不是实现。

## 6. 关键路径速查（file:line 级证据都在 02/03 文档里）

- 置换循环与 RNG（`Random(9873287)`，每基因独立有放回抽样）：`STEM_DataSet.java:1038-1375`，钉死版 §1.6。
- `binomialtail` 边界（count=0 → p≡1；dp≥1 → p=1；严格尾 P(X>x)）：`StatUtil.java:286-336`；真 JRE 向量在 `tests/golden/java_statutil/vectors.txt`（`jjs -cp stem.jar` 生成）。
- profile 精选贪心：`STEM_DataSet.java:1561-1711`；重参照消费的数据布局硬约束：03 §1.2（`genespottimedata` 引用别名语义——dup 组主行=合并后中位数、其余行=合并前标准化值）。
- 输出格式：`ST.java:2923-3036`（`Double.toString` + `Util.doubleToSz`；Python 复刻在 `src/pystemtc/javaformat.py`）。

## 7. 下一步（按序；验收判据已写明）

1. **M3 验证收尾（第 5 轮裁决顺序）**：① c13/c14 金标扩展（spec §1.9 钉死设计；`gen_fixtures.py --fixtures` 增量 + 单配置 `stem.jar -b`，禁止整目录重跑）；② git + 最小跨平台 CI（**已完成**，Windows+Ubuntu matrix + 浮点纪律 AST 测试）；③ B 两层冻结（**已完成**，spec §0）；④ N3 benchmark 三档（只测不优化，`tools/bench.py`）；⑤ JRE 17 characterization（**阻塞**：本机无 JRE 17，待安装）。
2. **M4 发布工程**：`pystemtc run`+`batch` CLI（N6）；`write_java_tables`（N7，不叫 to_csv）；`to_dict` schema **实现前送审**（N8：schema_version/reference_version/非有限值→null）；metadata timestamp；warning 仅 `none_add0×permute_t0=True`（N9）；Python 版本矩阵（N10，注意 numpy 2.4.6 要求 ≥3.11）；PyPI 实时复检后以 `pystemtc` 发布。
3. **V1.1**：K-means（`Random(2211)` + reservoir sampling）、plot adapter、`STEMInput.from_gene_matrix` 便利构造器。
4. 每步继续既有闸门流程（预审→实现→独立验证→post-review）。

## 8. 新会话的红线（容易踩的坑）

1. 不改 `tests/golden/` 既有文件（c01–c12 配置、全部参照表、vectors、synth6/synth10 数据均为冻结证据）；新增 fixture 只走 §7 流程（设计钉入 spec §1.9 → `gen_fixtures.py --fixtures` 增量生成 → 单配置 batch）。c09/c10/c11 里的 `STEMpy/` 历史前缀是有意保留的证据，不是 bug。
2. 不"修"任何 D6 所列 quirk；看到"Java 的行为在统计上不合理"时，先查 03 §1.6——大概率已记录且有意复刻。
3. 不在 `src/pystemtc/` 数值路径引入被禁的 numpy 规约（见 §3 的 grep）。
4. 不用 `stempy`/`STEMpy` 命名任何新代码或目录（历史文档与冻结 fixture 配置中的称谓除外，见 D8）。
5. 不因为测试慢就把金标断言改成容差或抽样——96 个测试里 24 个金标测试是本项目的存在理由。
6. 不实现 D10 范围外的功能，即使"顺手"。
7. 引用 Java 行为时给 file:line；引用测试结果时跑一遍再写。旧会话的结论若与磁盘现状冲突，以磁盘为准。

## 9. 一页速览

```text
项目     PySTEMTC (pystemtc) — STEM v1.3.14 time-course 核心的 Python 兼容实现
状态     M2 GO（第5轮）；M3 进行中：105/105 测试；14 金标配置 A exact + B 两层定义
oracle   D:\stem\stem.jar + D:\stem\sourcecode (v1.3.14, JRE 1.8.0_451)
代码     D:\stem\pySTEMtc（git 仓库，main 分支）  规范 docs/03（§1.9=c13/c14 设计）
验证     cd /d/stem/pySTEMtc && python -m pytest -q
下一步   M3 收尾 (benchmark→N4 JRE17阻塞) → M4 (CLI/write_java_tables/schema/发布) → V1.1
红线     不修 quirk、不碰冻结 fixtures、不换浮点顺序、不做范围外功能、禁宣称全平台逐位一致
```
