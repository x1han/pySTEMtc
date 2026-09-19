# PySTEMTC M3 结题报告与遗留问题清单（供专家团评审）

- 日期：2026-09-20
- 范围：第 5 轮评审门禁的完整执行（c13/c14 金标扩展、git+CI、B 两层冻结、benchmark、两个 P2 修复）→ 四道闸门（pre-work review GO-with-changes / 实现 / post-work review ACCEPT-with-fixes / 修复回填）
- 评审包：`D:\stem\PySTEMTC_m3_review_20260920_000458.zip`（精选内容，见 §6 导读）
- 关联文档：`docs/06_m3_round5_report.md`（门禁执行记录，本文的事实基础）；`docs/05` §7（第 5 轮裁决附录）
- 本报告所有数字均来自当日本机实测（Python 3.14.3，JRE 1.8.0_451，git `b2b5a92`）

---

## 1. 一段话总结

M3 把第 5 轮门禁全部执行完毕：**M2 仅剩的两个未覆盖算法交叉分支（on-the-fly × 缺失 × masked correlation；log 重参照 −Inf/NaN quirk × universe 路径）已被分支针对式金标覆盖，105/105 测试通过，14/14 配置 Compatibility A 字符串级 exact + B 打印值全等**。benchmark 实测显示 V1 无需优化（3 万基因外推分钟级）；git 仓库 + 跨平台 CI + GPL-3.0 LICENSE 就位。**算法层工作到此全部完成，项目站在 M4（发布工程）门口**，剩余问题集中在接口设计与发布流程（§4 M1–M8）。

## 2. 结果总结

### 2.1 门禁执行清单

| 第 5 轮门禁项 | 状态 | 证据 |
|----|------|------|
| c13/c14 重设计 + 生成 + 分支到达断言（N2，原方案被驳回） | 完成 | 4 张新参照表（Java batch 产出）+ 4 断言全过；spec §1.9 钉死 |
| git + 最小跨平台 CI（N5，升级 P1） | 完成（本地） | 2 提交；`.github/workflows/ci.yml`（Win+Ubuntu × Py3.12/3.14）——push 后生效 |
| Compatibility B 两层冻结（N1） | 完成 | spec §0：B-output canonical exact / B-internal 不得反噬 A / 反冻结声明 |
| N3 benchmark（只测不优化） | 完成 | §2.3 三档实测 |
| 两个 P2 修复 | 完成 | `str(rec.id)`；`legacy_with_replacement = mode != "exact"` |
| LICENSE（N11 部分） | 完成 | gnu.org 正典 GPL-3.0 文本；`.gitattributes` 冻结 golden 字节 |
| N4 JRE 17 characterization | **阻塞** | 本机无 JRE 17，待用户安装 |

### 2.2 c13/c14：分支针对式金标（要点，全设计见 spec §1.9）

| fixture | 覆盖分支 | 设计核心 |
|----|----|----|
| `c13_synth10_missing` | on-the-fly 置换 × 缺失 × 基线合法性检查（:1207）× masked correlation | synth10m.txt（300 spots 新文件）；行 i%3==2 在 0 基索引 (i%9)+1 置空、t0 永不缺；`max_missing=1`（原提案 `max_missing=0` 会在 filterMissing 吞掉全部缺失行——这正是第 5 轮驳回的原因；同时发现既有 12 配置中 masked correlation **从未被触发**：c09 的随机缺失全被过滤） |
| `c14_log_missing` | universe 置换 × log 重参照 vals 只按目标列掩码的 quirk（:1210-1262） | synth6d.txt（100 dup 对 + 40 单 spot，全正值）；缺陷放 **dup 组第二行**（主行序列被合并中位数覆写——§1.2 别名 quirk 的推论）；组 1 空格→log(0)=−Inf→vals 得 +Inf→中位数 +Inf→sqrt(NaN)→dcorr=NaN 跳过；组 2 负值→loader 记缺失保留负值→log(负)=NaN 直接进中位数；`permute_t0=true`（universe=720，50<720 → subsample） |

**执行期三个新发现**（评审两轮都未指出，实现/验证期实证）：
1. **单文件 `-b` 陷阱**：`stem.jar -b <配置文件>` 把完整输入路径嵌进输出名（szcurrentDefaultFile → :2947/:2989），写文件静默失败——正确做法是 scratch 目录走目录模式；已回填 spec §1.9/§3 并加 `--fixtures` 冻结名单守卫。
2. **c14 缺陷行归属**：必须放 dup 组第二行（主行按引用存储后被合并中位数覆写，DataSetCore.java:675-679 vs :717-723）。
3. **新输出 quirk**：c14 使 genetable 数值列真实出现 ±Inf——jjs + 文件字节双重实证 `NumberFormat(+Inf)=∞（U+221E）/ (−Inf)=-∞ / (NaN)=U+FFFD`，且 Java 按**平台默认字符集**（oracle 机 GBK）写表（冻结表中 `-∞` = `2D A1 DE`）。M4 `write_java_tables` 的实现输入，已记 spec §1.7。

### 2.3 N3 benchmark（只测不优化）

Windows 11 / Python 3.14.3 / numpy 2.4.6 / pandas 3.0.3；确定性合成数据（dup 结构、无缺失 = 干净路径上界）；50 置换；50 profile 网格；peak RSS = 全进程峰值（Psapi，含 numpy/pandas 导入）：

```text
spots,T,genes,profiles,wall_s,peak_rss_mib
300,6,267,50,0.3,76.0
3000,10,2700,50,29.3,869.7
10000,10,9000,50,53.5,871.9
```

- 早期粗估（"样例 75s、3 万基因小时级"）**按实测修正为悲观**：10000×10T 全流程 53.5s（≈5.9 ms/幸存基因，3.3× 基因数仅 1.8× 时间）。外推 3 万基因 × 50 置换 × 50 profile ≈ 3 分钟级；× 500 profile ≈ 半小时级。
- peak RSS 在 10T 两档持平于 ~870 MiB——主导项不是 spot 存储，是 profile 候选/置换缓冲；headless/agent 场景 <1GB 可接受。
- 局限：单机单次测量无方差；Windows-only（Linux 数字待 CI）。

### 2.4 工程状态

git main 两提交（`ca312d8` 基线 → `b2b5a92` M3）；CI workflow 就位（**push 到 GitHub 后才真正运行**，Linux 侧证据待首次 push）；`pyproject` 加 `dev` extra；`requires-python>=3.10` 维持（N10 归 M4）。

## 3. 可以得出的结论

1. **V1 范围内的算法移植已完成**：模型 profile 生成/精选、并列分配、三条置换路径、显著性三校正、聚类、引擎串联——在 14 配置 × 覆盖矩阵（3 标准化 × 3 校正 × 3 置换路径 × 2 重复模式 × percentile × 缺失 × log quirk）上 Compatibility A 全 exact、B 打印值全等。**在已识别的分支范围内，没有已知的未覆盖交叉分支。**
2. **浮点纪律与 quirk 复刻经受住了最刁钻路径的考验**：c14 把 ±Inf/NaN 真实注入 Java 的排序/中位数/相关链，Python 的逐行复刻（Arrays.sort 全序 NaN 排最后、vals 掩码不对称、dcorr=NaN 跳过、`Math.sqrt` NaN 语义）与 Java 字符串级一致——这是对 §1.6/§1.7 钉死语义的最强验证。
3. **性能不是 V1 的风险项**：纯 Python 实现 <1GB 内存、万级基因秒-分钟级完成，"先 golden 后优化"的优化空间留给 V1.x 按需启用。
4. **兼容性证据链工程化完成**：金标冻结字节受 git `-text` 保护、增量化生成流程带冻结名单守卫、每条 Java 语义有 file:line 钉死——后续任何回归都可被 105 个测试当场抓获。
5. **诚实的剩余缺口**（不阻塞 M4，但记录在案）：JRE 17 环境（N4）、Linux 平台实测（待 push）、真实大规模数据集（金标仅覆盖样例 + 合成数据）、benchmark 无方差与跨平台数字。

## 4. 遗留问题清单（请专家团给意见）

### 设计裁决类

| # | 级别 | 问题 | 我的提案 | 请专家裁决 |
|---|------|------|---------|-----------|
| M1 | P1 | **`to_dict()` schema（N8 升 P2 的实现前送审）**——agent 消费接口，M4 写码前定稿 | 见下方 §4.1 提案：`schema_version=1`、`reference_version="STEM 1.3.14"`、非有限值→JSON `null`、`present[]` 为权威在场掩码 | 逐字段过一遍：字段名/类型/缺失语义是否认可？还需哪些字段？ |
| M2 | P2 | **`write_java_tables` 字符集**（Compatibility C） | 默认 = 运行平台默认字符集（逐机镜像 Java 行为），提供 `encoding=` 参数允许显式固定（如复现 oracle 机 GBK 输出）；∞/U+FFFD 形式无条件复刻 | "默认跟平台"是否认可？还是默认固定 UTF-8？ |
| M3 | P2 | **CLI 细节定稿**（N6 方向已定：run+batch 双入口） | `pystemtc run --config <defaults.txt> --output <dir>`（数据文件从 config 读）；`pystemtc batch --config-dir <dir> --output <dir>`；退出码 0/1；stdout 只打进度摘要（镜像 Java batch 打印行数） | flag 命名/退出码/stdout 契约是否认可？ |
| M4 | P2 | **Python 版本下限**（N10）：numpy 2.4.6 要求 ≥3.11（专家引 PyPI），pandas 3.0.3 下限待核 | `requires-python` 提到 `>=3.11`，CI matrix 改 3.11/3.12/3.14（发布前以 PyPI 实测为准） | 是否同意 3.11 下限？还是发布时放宽 numpy 下限换 3.10 支持？ |
| M5 | P3 | **warning 文案**（N9 已定组合：仅 `none_add0×permute_t0=True`） | 一条 warning，说明"置换会把合成 0 列当真实数据移动，结果可能无统计意义；Java 同样照算"，指向文档 | 文案措辞 |

### 流程/环境类

| # | 级别 | 问题 | 我的提案 | 请专家/用户裁决 |
|---|------|------|---------|-----------|
| M6 | P2 | **CI 未激活**：workflow 只有 push 到 GitHub 才运行；本机无 Linux | 用户提供 GitHub 仓库（或授权我准备 remote 配置）后 push，首次 CI 绿灯 = Linux 侧 A-exact 证据闭环 | 是否 push？推到哪个仓库？ |
| M7 | P3 | **N4 解除阻塞**：本机无 JRE 17 | 用户安装任意 JRE/JDK 17 后我跑 14 配置 characterization（只记录，JRE 8 仍是唯一 oracle） | 安装哪个发行版由用户定 |
| M8 | P3 | **V1.0 是否带"未优化"声明发布**（N3 数据已齐） | 按 §2.3 数据，性能对目标场景无压力，V1.0 如实标注性能特征 + 不做优化 | 确认后 M4 收尾直接发布流程 |

### 4.1 `to_dict()` schema 提案（M1 详细版）

```jsonc
{
  "schema_version": 1,
  "reference_version": "STEM 1.3.14",       // 行为 oracle 版本，与 package 版本解耦
  "generator": {"package": "pystemtc", "version": "0.1.0"},
  "config": { /* 输入参数平面 dict（可 hash 的字段子集，不含时间戳） */ },
  "metadata": {
    "permutation_mode": "exact | subsample_universe | on_the_fly",
    "legacy_with_replacement": true,
    "n_permutations_requested": 50,
    "num_time_points": 10,
    "timestamp": "..."                       // 只进 to_dict，不进 config（保持 config 可 hash）
  },
  "profiles": [ // 与 Java profiletable 行一一对应
    {"id": 0, "model": [0.0, 1.0], "cluster": -1, "n_assigned": 8.0,
     "n_expected": 5.307, "p_value": 0.17, "significant": false}
  ],
  "gene_assignments": [ // 与 Java genetable 行一一对应（顺序一致）
    {"gene": "X", "probe": "1", "profile": "3",
     "values": [0.0, -0.9, null], "present": [true, true, false]}
    // values/p_value/n_expected 中的 ±Inf/NaN → null；present[] 是 pma 权威镜像
  ],
  "filtered_genes": [ {"gene": "Y", "probe": "2", "reason": "..."} ], // reason 无 Java 对应物，不进 write_java_tables
  "clusters": [[0, 1], [2]]
}
```

非有限值处理按第 5 轮 N8 倾向：**JSON 层一律 `null`**（严格 JSON 不接受 `NaN`/`Infinity` 字面量），在场性由 `present[]` 与 `significant` 承载；Java 渲染形式（∞/-∞/U+FFFD）只属于 `write_java_tables`（Compatibility C），不进 dict。c14 类路径中"present=True 但值非有限"若出现，同样输出 null 并在文档注明（present 反映 pma，不承诺有限性）。

## 5. 下一步计划（M4 发布工程；依 §4 裁决启动）

1. `to_dict` 按 §4.1 定稿实现（含 metadata timestamp、config 可 hash 保持）。
2. `write_java_tables`：batch 两表逐字段复刻（最后一列无条件输出、∞/U+FFFD、字符集按 M2 裁决、`filtered_genes` reason 不导出）。
3. CLI `run` + `batch`（M3 裁决细节）；warning（M5 文案）。
4. N10：`requires-python>=3.11` + CI matrix 扩展（PyPI 实测下限）；PyPI `pystemtc` 实时复检；README/发布清单。
5. push 后首次 CI 绿灯（M6）→ N4 解除后补 JRE 17 characterization（M7）→ V1.0 发布（M8）。
6. V1.1（发布后）：K-means（`Random(2211)` + reservoir sampling）、plot adapter、`STEMInput.from_gene_matrix`。
7. 每步继续 light-rip 闸门（M4 接口面大，预计 Large 级：planner→reviewer→implementer→verifier→reviewer）。

## 6. 评审包导读

包内只含本轮新增/变更且需专家过目的内容；完整工程 `D:\stem\pySTEMtc`（git `b2b5a92`，105 测试可独立复跑）。

| 文件 | 焦点问题（每文件一个） |
|------|----------------------|
| `docs/07_...md`（本报告） | §4 的 M1–M8 裁决项；§4.1 schema 提案逐字段 |
| `docs/06_m3_round5_report.md` | 门禁执行记录：§2 两个执行期修正与 §3 新 quirk 的证据链 |
| `docs/03_v1_implementation_spec.md` | §1.9（c13/c14 设计钉死 + 执行期修正回填）、§1.7（新 quirk）、§0（B 两层冻结） |
| `verification/pytest_full_*.log` | 105 passed 全量原始输出（当日本机全新复跑） |
| `golden/java_reference/c13_*`、`c14_*` + `java_configs/` 同名配置 + `data/synth10m.txt|synth6d.txt` | 新分支的 Java oracle 输出与确定性输入（c14 genetable 的 `-∞` = GBK `2D A1 DE`） |
| `tests/test_golden_branches.py` | 分支到达断言是否充分 |
| `tools/gen_fixtures.py` | `--fixtures` 增量 + 冻结名单守卫 + scratch 批跑 |
| `tools/bench.py` + `verification/bench_results.csv` | N3 数据来源与可复跑性 |
| `src-meta/ci.yml`、`src-meta/.gitattributes`、`tests/test_float_discipline.py` | N5 工程设施 |
| `verification/git_state.txt` | 提交历史与干净工作树 |

**可跳过**：M1/M2 已评审的 src 模块（本轮 src 仅 2 处 P2 级小改）、docs/01/02/04/05、HANDOFF.md、既有 c01–c12 全套 fixture（本轮零触碰，git diff 为空）。
