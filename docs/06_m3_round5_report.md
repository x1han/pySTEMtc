# PySTEMTC M3 第 5 轮门禁执行报告

- 日期：2026-09-19
- 范围：第 5 轮评审门禁的执行记录——c13/c14 金标扩展（N2 重设计）、git+CI（N5 P1）、Compatibility B 两层冻结落盘（N1）、N3 benchmark、N4 状态、两个 P2 修复
- 评审包：`D:\stem\PySTEMTC_m3_review_<时间戳>.zip`（精选；实际路径见交付消息）

---

## 1. 门禁执行摘要

| 门禁项（第 5 轮裁决） | 状态 | 证据 |
|----|------|------|
| c13/c14 重设计 + 生成 + 分支到达断言 | **完成** | 4 张新参照表 + `tests/test_golden_branches.py` 4 断言全过 |
| git + 最小跨平台 CI（N5，P1） | **完成**（本地） | git 仓库 2 提交；`.github/workflows/ci.yml`（Win+Ubuntu × Py3.12/3.14）——push 到 GitHub 后生效 |
| Compatibility B 两层冻结（N1） | **完成** | spec §0（B-output canonical exact / B-internal 不得反噬 A；反冻结声明） |
| N3 benchmark（只测不优化） | **完成** | §4 表（3 档实测 wall + peak RSS） |
| N4 JRE 17 characterization | **阻塞** | 本机仅有 JRE 1.8.0_451；待安装后执行 |
| 2 个 P2（str(rec.id) / legacy_with_replacement 语义） | **完成** | diff 见提交；spec §1.7 记录 |
| LICENSE（N11 部分） | **完成** | gnu.org 正典 GPL-3.0 文本落库 |

## 2. c13/c14：M2 仅剩的未覆盖算法交叉分支已补上

**验证结果：105/105 测试通过（96 旧 + 4 新金标 + 4 分支断言 + 1 浮点纪律 AST 守卫）。14/14 配置 Compatibility A 字符串级 exact、B 打印值全等。**

| fixture | 覆盖分支 | 设计要点（钉死于 spec §1.9） |
|----|----|----|
| `c13_synth10_missing` | on-the-fly 置换 × 缺失 × 基线合法性检查（:1223）× masked correlation | synth10m.txt（300 spots，新文件）；确定性缺失：行 i%3==2 在 0 基索引 (i%9)+1 置空，t0 永不缺；`max_missing=1`（原提案被第 5 轮驳回的原因正是 c11 的 `max_missing=0` 会在过滤阶段吞掉全部缺失行） |
| `c14_log_missing` | universe 置换 × log 重参照 quirk（:1221-1275 vals 只按目标列掩码） | synth6d.txt（100 dup 对 + 40 单 spot，全正值）；缺陷放在 **dup 组第二行**（主行序列被合并中位数覆写——§1.2 别名 quirk 的推论，缺失放主行则永远到不了该分支）；组 1 空格→log(0)=−Inf→vals 得 +Inf→中位数 +Inf→sqrt(NaN)→dcorr=NaN 跳过；组 2 负值→loader 记缺失保留负值→log(负)=NaN 直接进中位数；`permute_t0=true`（universe=720 而非 120——120 蕴含 permute_t0=false，基线恒 t0，quirk 永不触发） |

**分支到达证明**（第 5 轮评审要求"不能只靠测试通过"）：`test_golden_branches.py` 断言 c13 幸存基因中 ≥10 个仍带非 t0 缺失（`permutation_mode=="on_the_fly"`）、c14 两组缺陷 dup 各 ≥10 个幸存（`permutation_mode=="subsample_universe"`），外加两个 fixture 确定性模式自检。

**执行中发现并修正的两个设计错误**（pre-work review 之后、实现中暴露）：
1. 单**文件** `-b` 输入会把完整输入路径嵌进输出名（`szcurrentDefaultFile`，ST.java:2947/:2989），写文件静默失败——改用 scratch 目录（只含新配置）走目录模式。
2. c14 缺陷 spot 必须是 dup 组**第二行**：主行 `genespottimedata` 存引用后被合并中位数覆写（:675-679 vs :717-723），缺失放主行时 NaN/±Inf 进不了重参照 vals。此推论第 5 轮评审与 pre-work 均未指出，由实现期对合并代码逐行复核发现。

## 3. c14 挖出的新输出 quirk（M4 的 Compatibility C 输入）

c14 使 genetable 数值列真的出现了 ±Inf——Java `NumberFormat`（DecimalFormatSymbols 文档默认）对非有限数的渲染首次有金标实证：

- `+Inf` → `∞`（U+221E）、`-Inf` → `-∞`、`NaN` → U+FFFD（M2 已钉，长度 1；jjs 实测一致）。
- Java 以**平台默认字符集**写表（oracle 机 = GBK）：c14 冻结参照表中 `-∞` = 字节 `2D A1 DE`。金标 reader 改为 GBK 确定性解码（ASCII 表两种解码等价；`tests/golden/**` 在 git 中 `-text`，行尾永不转换）。
- **M4 `write_java_tables` 必须复刻 ∞/U+FFFD 形式并按运行平台默认字符集写文件**（已写入 spec §1.7）。

## 4. N3 benchmark（只测不优化，第 5 轮裁决）

环境：Windows 11（win32 10.0.26200），Python 3.14.3，numpy 2.4.6，pandas 3.0.3；确定性合成数据（dup 结构同 fixture 生成器，无缺失格 = 干净路径上界）；50 置换；50 profile 网格；normalize 模式。peak RSS = 全进程峰值（Psapi PeakWorkingSetSize，含 numpy/pandas 导入）。

```text
spots,T,genes,profiles,wall_s,peak_rss_mib
300,6,267,50,0.3,76.0
3000,10,2700,50,29.3,869.7
10000,10,9000,50,53.5,871.9
```

（genes = 阈值过滤后幸存数，约 90%；wall 为单次 `STEM.fit` 全流程；CSV 原始输出 `build/bench_results.csv`，脚本 `tools/bench.py` 可复跑。）

解读：
- 早期 M2 的粗估（"样例 75s、3 万基因小时级"）**明显悲观**：实测 3000×10T 全流程仅 29.3s、10000×10T 仅 53.5s（约 5.9 ms/幸存基因——3.3× 基因数只花 1.8× 时间，大基因数下单位成本摊薄）。此前 HANDOFF 里的 75s 数字应是早期未优化中间版或含 JVM 的对拍口径，以本次实测为准修正记录。
- 外推（线性、按 profile 相关计算占比）：3 万基因 × 50 置换 × **50** profile ≈ 3 分钟级；× **500** profile（用户放大参数网格时）≈ 半小时级——远好于此前"小时级"的担忧。**V1 不需要为此优化**（与第 5 轮"不要现在换 Numba/vectorization"一致）。
- 内存：peak RSS ~870 MiB 在 10T 两档持平，说明主导项不是 spot 级存储（3000→10000 spots 仅 3.3×数据），而是 profile 候选/置换工作缓冲；对 headless/agent 场景 <1GB 可接受。
- 局限：单机单线程单次测量，无重复试验取方差；Windows-only（Linux 侧数字待 CI/首次 push 后补）。优化决策推迟到专家/用户看过本表之后。

## 5. N4：JRE 17 characterization——阻塞

本机仅有 `C:\Program Files\Java\jre1.8.0_451`（java + jjs，无 javac），无 JRE 17/JDK 17。**需要用户安装一个 JRE/JDK 17**（任意发行版）后执行 characterization 脚本（对 14 配置跑 `java -version` + batch 对拍，结果只作附加证据，JRE 8 仍是唯一 oracle）。

## 6. 工程状态

- git 仓库（main）：`ca312d8` 基线（M2 + 第 5 轮裁决文档 + LICENSE + CI + 浮点守卫）→ 第二提交（c13/c14 + 修复 + benchmark）。
- CI（`.github/workflows/ci.yml`）：ubuntu-latest/windows-latest × Python 3.12/3.14，`pip install -e ".[dev]"` + `pytest -q`；fixtures 入库无需 Java；浮点禁运为 AST 扫描测试（`tests/test_float_discipline.py`，跨平台无 shell 依赖）。**workflow 只有 push 到 GitHub 后才真正运行**——本机无法自证 Ubuntu 侧结果，第 5 轮评审要求的"Linux 下 A 必须 exact"证据待首次 push 后闭环。
- `pyproject.toml` 增加 `dev` extra（pytest）；`requires-python>=3.10` 维持不动（N10 的下限复核归 M4）。

## 7. 下一步（待第 6 轮专家意见）

1. **M4 发布工程**（按 N6-N11 已定向）：`run`+`batch` CLI；`write_java_tables`（复刻 batch 两表 + ∞/U+FFFD + 平台字符集）；`to_dict` schema **实现前送审**（schema_version / reference_version="STEM 1.3.14" / 非有限值→null）；metadata timestamp；warning 仅 `none_add0×permute_t0=True`；Python 版本矩阵（注意 numpy 2.4.6 要求 ≥3.11）；PyPI 实时复检后以 `pystemtc` 发布。
2. N4 解除阻塞后补 JRE 17 characterization。
3. V1.1：K-means（`Random(2211)` + reservoir sampling）、plot adapter、`STEMInput.from_gene_matrix`。
