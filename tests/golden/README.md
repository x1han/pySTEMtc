# Golden fixtures

由本机 JRE 8 的 `stem.jar -b` 批处理模式生成，是 PySTEMTC 的分层验收基准（Level A 离散 exact / Level B 连续量容差，见 `docs/03_v1_implementation_spec.md` §1.5）。

## 目录

- `java_configs/` — 12 组 batch defaults 文件（参数网格：3 种标准化 × permute_t0 × 3 种校正 × 重复模式 × percentile × 合成数据）。
- `data/` — 合成输入 `synth6.txt`（6 时间点，触发 universe 物化 + 子抽样路径）、`synth10.txt`（10 时间点，触发 on-the-fly 置换路径），以及样例数据副本 `g27_1.txt`/`g27_2.txt`（取自 `D:\stem`，使集成测试不依赖仓库外文件）。冻结的 c09/c10/c11 配置中 `Data_File` 仍带更名前的历史前缀 `STEMpy/tests/golden/data/...`（证据不动），测试解析器按 basename 回退到本目录副本。
- `java_reference/` — 24 张输出表（每配置 `*_profiletable.txt` + `*_genetable.txt`）+ `_batch_stdout.log`。
- `java_rng/` — `vectors.txt`：本机 JRE 8 `jjs` 从真实 `java.util.Random` 导出的向量（seeds 9873287 / 3733246 / 2211 / 42，含流交错顺序）。

## 再生成

```bash
python pySTEMtc/tools/gen_fixtures.py
```

要求：JRE 8 位于 `C:\Program Files\Java\jre1.8.0_451\bin`（java + jjs），工作目录可访问 `D:/stem/stem.jar` 与样例数据。CI 不依赖 Java——fixtures 提交入库。

## 精确检验边界备忘

样例数据为 5 个时间点：默认 `n_permutations=50`、`permute_t0=true` 时 universe=120 → 每基因有放回抽 50（确定性子抽样，非精确）；`permute_t0=false` 时 universe=24 ≤ 50 → 全排列精确路径。`n_permutations=0`（c10）恒为精确。
