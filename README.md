# 微博茧房判断器 · Weibo Cocoon Judge

> 你关注了谁，你就暴露了什么。
>
> 一个给自己的微博账号做「茧房判断」的 Agent Skill——基于 @tombkeeper（教主）的「关注列表定律」。

给**自己的**微博账号做一次诚实的信息环境体检：全量拉取关注列表，分析品类成分、高危浓度、信息多样性，最后给出一份**只属于你的个性化判词**。

**只测自己。不测别人，也测不了别人**——这是设计原则，也是 API 的硬边界。

---

## 它能回答什么

- 我的关注列表是「茧房」还是「偏食」还是「平衡」？
- 我有没有在大量聚集军事 / 财经 / 女权 / 动保 / 中医 / 伪科学类账号？（**高危浓度层**——这些信号不属于官方认证分类，靠简介关键词辨别）
- 我的信息多样性到底怎么样？
- 一句话：**我是在看世界，还是在被投喂？**

核心立场：**关注 ≠ 问题，浓度才是信号。** 关注几个军事号、养生号是正常的信息来源，大量聚集才是茧房的墙砖。本工具只描述信息环境，不做价值判断——不说「认知低下」，只说「多样性低」。

## 特性

- 🔍 **全量拉取**：默认拉完整关注列表（非抽样），实测沉淀的分页降级策略（重叠窗口 + 空段跳过 + 二次扫描）
- 🔴 **强制检查点**：拉取不全（缺口 >10%）时必须停下问用户：按已拉取的开跑（标注覆盖率）还是降级重扫全拉完再跑
- ⚖️ **防误判的判档机制**：母档由硬规则判定（极端画像数学上不可能被轻判），分数只决定档内子档
- 🎭 **个性化判词**：母档(3) × 子档(3) × 品类意象(13) × 措辞变体(3) = **351 个不重复出口**——两个茧房里的人几乎不会拿到同一个判词。科技茧房是「奇点前夜」，军事茧房是「开战前夜」，养生茧房是「永远在调理期」
- 🧪 **自带 HTML 自检**：9 项产物自检（charset / 标签配对 / 占位符残留 / 数据注入），FAIL 不交付
- 📦 **零依赖**：纯 Python 标准库（≥3.6），纯 REST + curl，Claude Code / Codex CLI / OpenClaw / Minis / SSH 服务器 / 本地终端，哪儿都能跑

## 判词体系

三个母档，各三个子档，判词由「档位骨架 × 你的主品类意象 × 措辞变体」四层组装：

| 母档 | 子档 | 判词示例 |
|------|------|---------|
| 🔴 茧房 | 深茧 / 回音壁 / 同温层 | 「你的关注列表只剩一种味道：一个永远在开战前夜的世界。三句话不离博弈和棋手——这不是你在看世界，是世界从你这里路过。」 |
| 🟡 偏食 | 重口偏食 / 偏食 / 单一主粮 | 「一个永远在奇点前夜的世界。菜单很厚，你总点这一道。看什么都想优化一遍——好吃，但别的味道正在消失。」 |
| 🟢 平衡 | 有主粮的杂食 / 采样均衡 / 杂食动物 | 「什么都看，什么都不全信——最难被洗脑的类型。」 |

档位判定权重与边界自查表见 [`references/cocoon-detection.md`](references/cocoon-detection.md)；引擎可独立自测：

```bash
python3 scripts/verdict_engine.py
```

## 用户入口：跑一下微博茧房判断器

### 方式一：对 Agent 说人话（推荐）

把本仓库克隆到你的 Agent 的 skills 目录，然后直接说：

```
帮我跑一下微博茧房判断器
```

以下说法都会触发：**「茧房判断」「茧房检测」「茧房判词」「自诊」「关注列表分析」**。

Agent 会按 SKILL.md 自动走完全流程，你只需要参与两个决策点：

1. **提供 Token**——环境里没有 `WEIBO_CLI_TOKEN` 时，Agent 会停下来找你要（微博开放平台 CLI 套餐获取）
2. **🔴 拉取不全时的检查点**——如果关注列表没法全量拉回（注销/私密账号导致缺口 >10%），Agent 必须停下来问你：**A 按已拉取的部分直接出报告（标注覆盖率）**，还是 **B 降级重扫、全拉完再跑**。你不选，它不开工

跑完后你会得到一份和纸极简风格的 HTML 报告（手机/电脑自适应）+ 结构化 JSON，落在你指定的目录。

各平台安装位置示例：

| 环境 | 克隆到 |
|------|--------|
| Claude Code | 项目 `.claude/skills/` 或全局 skills 目录 |
| Codex CLI / OpenClaw | 对应 skills 目录（读 SKILL.md 即生效） |
| Minis | `/var/minis/skills/` |

### 方式二：不用 Agent，手动跑

token 配好后，把流程当三段脚本跑（采集 → 归类 → 出报告）：

```bash
# 1) 按 references/data-sources.md 的策略拉取关注列表 -> weibo_follows_raw.json
# 2) 按 references/cocoon-detection.md 做品类归类 -> cocoon_result.json + weibo_follows_classified.json
# 3) 出报告（内置 9 项自检）
python3 scripts/generate_report.py --result cocoon_result.json \
  --classified weibo_follows_classified.json --outdir ./output
```

## 快速开始

### 0. 前置

- Python ≥ 3.6（无第三方依赖）
- 微博开放平台 **CLI 套餐** 的 API Token，写入环境变量：

```bash
export WEIBO_CLI_TOKEN="$(weibo-cli auth token --export)"
```

### 1. 冒烟测试（验证 Token + 额度 + 记录关注总数）

```bash
curl -s -X POST "https://open.weibo.com/cli/api/cli/invoke" \
  -H "Authorization: Bearer ${WEIBO_CLI_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"group":"friendships","action":"friends/biz","args":{"count":20,"page":1}}'
```

- 返回 `users` 数组 → 通过，记下 `total_number`
- `401/403` → Token 无效或无权限；`429` → 额度耗尽；`COUNT_EXCEEDS_MAX` → count 降到 20

### 2. 全量拉取关注列表

按 [`references/data-sources.md`](references/data-sources.md) 的策略翻页（重叠窗口、去重、空段跳过），得到 `weibo_follows_raw.json`。缺口 >10% 会触发检查点，由你决定 A 按部分开跑 / B 降级重扫全拉完。

### 3. 品类归类 + 生成报告

```bash
python3 scripts/generate_report.py \
  --result cocoon_result.json \
  --classified weibo_follows_classified.json \
  --outdir ./output
```

产物：`output/茧房检测报告_昵称_时间戳.html`（自动增量命名，绝不覆盖），内置 9 项自检。

> Agent 使用提示：SKILL.md 是完整执行手册——资源路由、每步的红灯与纪律都写在那里。让 Agent 先读它。

## 目录结构

```
weibo-cocoon-judge/
├── SKILL.md                     # Agent 执行手册（入口，保持精瘦）
├── references/
│   ├── data-sources.md          # 采集：冒烟测试 / 分页策略 / 降级兜底 / 强制检查点
│   ├── cocoon-detection.md      # 方法论：品类归类 / 高危浓度 / 判词引擎 + 边界自查表
│   └── visual-templates.md      # 报告视觉规范（和纸极简）
├── scripts/
│   ├── verdict_engine.py        # 判词四层组装引擎（可独立自测）
│   └── generate_report.py       # 报告生成器（内置 HTML 自检）
└── archive/                     # 已裁撤模块的留档
```

## 隐私与边界

- **只分析自己**：`friends/biz` 接口绑定登录者本人，技术上不存在「查他人关注列表」的途径，本工具也不提供。
- **数据不出本地**：关注列表、分析结果、HTML 报告全部落在你自己指定的目录；`.gitignore` 已把 `*.json` 和报告文件挡在版本库外。
- **仓库零个人数据**：skill 文件本身不含任何硬编码 uid / 昵称 / 路径。
- **公开数据 only**：分析基于公开可见的微博资料（昵称、简介、认证信息、粉丝数）。
- **不是人格鉴定**：输出定位为「社交行为模式观察」。你关注什么不代表你是什么人，只代表你的信息长什么样。

## 方法论

理论基础来自 [@tombkeeper](https://weibo.com/tombkeeper) 的「关注列表定律」系列：归纳→演绎→迭代、机械式响应模型、老鼠屎隐喻、粉丝修正算法。本工具是其方法论的一次工程化落地。

## License

[MIT](LICENSE)
