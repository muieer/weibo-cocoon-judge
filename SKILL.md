---
name: weibo-cocoon-judge
description: |
  微博茧房判断器——给自己的微博账号做"茧房判断"。
  唯一功能：茧房检测（关注列表分析 + 高危浓度 + 个性化判词）。
  触发词：茧房判断、茧房检测、茧房判词、自诊、关注列表分析。
metadata:
  version: "1.0.0"
---

# 微博茧房判断器

> 你关注了谁，你就暴露了什么。

给自己的微博账号做"茧房判断"：全量拉取关注列表 → 品类成分 / 高危浓度 / 信息多样性 → 成分标签 + 个性化判词（四层组装引擎，351 个不重复出口）。

## 前置（缺一停下问用户，不要猜）

1. **环境**：Python ≥ 3.6 纯标准库，能跑 curl——Claude Code / Codex / OpenClaw / Minis / 服务器均可，无平台专属依赖。
2. **凭证**：环境变量 `WEIBO_CLI_TOKEN`（微博开放平台 CLI 套餐）。
3. **冒烟测试**（验 Token + 额度，顺带记录 total_number）：见 [`references/data-sources.md`](references/data-sources.md) §0。`401/403/429` 一律红灯停下。

## 硬纪律

- **只测自己**——API 拿不到别人的关注列表，勿尝试。
- **全量拉取是默认**；缺口 >10% 触发 🔴 检查点：A 按已拉取开跑（标覆盖率）/ B 降级重扫全拉完再跑，用户不选不开工（详见 data-sources.md）。
- **判词一律调 `scripts/verdict_engine.py`**，报告一律调 `scripts/generate_report.py`（自带 HTML 自检，FAIL 不交付），不要手写判断链或改版式。
- **路径不写死**：数据/输出由调用方目录决定，报告自动昵称+时间戳命名，绝不覆盖。
- **不做价值判断**：只描述信息环境（"多样性低"），不评判人（"认知低下"）。

## 资源路由

| 文件 | 何时读取 |
|------|---------|
| [`references/data-sources.md`](references/data-sources.md) | 采集前：冒烟测试、分页策略、🔴 检查点、降级兜底 |
| [`references/cocoon-detection.md`](references/cocoon-detection.md) | 分析前：方法论、品类归类、高危浓度、判词引擎 + 边界自查表 |
| [`references/visual-templates.md`](references/visual-templates.md) | 报告前：和纸极简模板规范 |
| [`scripts/verdict_engine.py`](scripts/verdict_engine.py) | 算判词（可独立自测） |
| [`scripts/generate_report.py`](scripts/generate_report.py) | 出报告 |
| `archive/health-indicators.md` | ❌ 已裁撤，勿读 |

## 执行流程（五步）

① 冒烟测试 → ② 全量拉取（重叠窗口）→ ③ 🔴 检查点（如触发）→ ④ 分析 + 判词（verdict_engine）→ ⑤ 出报告（generate_report）。
