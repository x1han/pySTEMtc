# Round-8 Plan Cleanup Diff（v2 → v3；user 团 GO-WITH-FINAL-CLEANUP）

| # | 项 | 旧 | 新 |
|---|---|---|---|
| 1 | "5-column" 残留 3 处 | line 26 / 383 / 491 | 全改 "6-column" + `len(header_cols)==6` assert |
| 2 | c14 NaN→? 残留 3 处 | line 386 / 660 / 730 | 改为"±Inf→U+221E GBK 可编 / NaN→U+FFFD GBK 不可编" + c14 不能证 NaN→? |
| 3 | "不受 encoding 影响" 残留 2 处 | line 107 / 108 | 改 "C1 必须同 target encoding + replacement policy" 引用 §6.1 |
| 4 | W2/W3 假 30 cases | ALL_CASES 实际 14 个 | W2/W3 拆 14（c01-c14 parametrize）+ 2（custom_header 单独）= 30 |
| 5 | W2 写阶段编码未 pin | 默认 UTF-8 | W2 显式 `encoding="gbk", newline="\n"`；CRLF 留给 C2 |
| 6 | large finite 只证不崩 | assert "not NaN/Inf" | 必 JRE8 probe 抓 4 个 expected 实字符串 + 字节对比 |
| 7 | custom_header 入仓后未复现 | 入仓即可 | 入仓 + 用入仓 config 跑 JRE8 STEM v2 重产 oracle byte-exact |
| 8 | W1 展示 `errors=` 参数 | "write_java_tables(..., errors=\"replace\")" | API 不暴露；只传 `encoding/newline`；结果反证 |
| 9 | `git_dirty` 字符串塞字段 | `git_dirty: "clean"|"dirty"|"unknown"` | 改名 `git_state: "clean"|"dirty"|"unknown"` + 三态 |
| 10 | 返回类型漏掉 | `def write_java_tables(...)` | `def write_java_tables(...) -> list[str]: return [str(gene_path), str(prof_path)]` |

**实施门槛**：实施前必须完成 JRE8 probe 抓 4 个 large-finite expected；custom_header 入仓 config 必须用 JRE8 重产 oracle 通过 byte-exact。

10 项校正自动验证（`grep` 全部 FOUND），无需 round-8 v4 plan。