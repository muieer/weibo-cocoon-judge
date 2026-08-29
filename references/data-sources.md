# 数据采集规范（1.0.0 实测校准版）

## 前置：Token 与额度（第 0 步，任何采集前必做）

**唯一凭证**：环境变量 `WEIBO_CLI_TOKEN`（`wb_` 开头，微博开放平台 CLI 套餐签发，长期有效）。变量未设置 → 停下找用户配置，不要猜。

**冒烟测试**（一次性验证 Token 有效性 + 套餐额度 + 记录关注总数）：

```bash
curl -s -X POST "https://open.weibo.com/cli/api/cli/invoke" \
  -H "Authorization: Bearer ${WEIBO_CLI_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"group":"friendships","action":"friends/biz","args":{"count":20,"page":1}}'
```

| 结果 | 判定 | 动作 |
|------|------|------|
| `"users":[...]` 且 `total_number` 有值 | ✅ 可用 | 记下 total_number（全量拉取的核对基准） |
| HTTP 401 / 403 | Token 无效或套餐无此接口权限 | 🔴 停下找用户，不要继续 |
| HTTP 429 `TOO_MANY_REQUESTS` | 额度耗尽 | 🔴 停下找用户（等额度 or 换套餐），不要空转 |
| `COUNT_EXCEEDS_MAX` | 参数超限 | count 降到 20 重试 |

调用走 REST 直调（跨环境最稳）；`weibo` CLI 二进制在部分受限网络下不可用，不作为依赖。**任何环境（Claude Code / Codex / OpenClaw / Minis / 服务器）只要能跑 curl 或 Python 标准库即可。**

## ⚠️ 已实测事实（2026-08-29，与平台公开 schema 冲突时以此为准）

1. **`friends/biz` 服务端强制 `count ≤ 20`**——公开 schema 写"最大200"是错的，count=50 直接报 `COUNT_EXCEEDS_MAX`。
2. **`page` 和 `cursor` 分页都可用，但都不可靠**（2026-08-29 实测）：链式 cursor 翻到 400 处会返回空段（直接跳 420+ 又有数据）；page 参数中途也会给空页/短页，且排序漂移导致页间重叠。**可靠策略：固定步进 10~20、窗口 count=20、逐段去重、空段跳过**。两种策略最终收敛到同一集合（例：total=763，收敛 640，缺的 123 个为注销/私密/不可见账号，属正常，不要死循环硬怼）。
3. **CLI 帮助里 "friends/biz（可用: --uid | --screen_name）" 是死文案**——CLI 会报 Unknown option。且 REST 直调传 uid/screen_name 也查不了别人：该接口绑定登录者本人，**不存在查他人关注列表的接口**。
4. **返回的用户对象字段极全**（90+ 字段）：`followers_count`、`verified`、`verified_type`、`verified_reason`、`description`、`location`、`gender`、`created_at` 等全部内联。**不需要也不应该再调 `users/show_batch/other`**。

## 茧房检测：采集流程

```python
import json, os, time, urllib.request

TOKEN = os.environ["WEIBO_CLI_TOKEN"]
def invoke(group, action, args, retries=3):
    req = urllib.request.Request(
        "https://open.weibo.com/cli/api/cli/invoke",
        data=json.dumps({"group": group, "action": action, "args": args}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method="POST")
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:               # TOO_MANY_REQUESTS：等下一个窗口
                time.sleep(60)
            elif e.code >= 500 and i < retries - 1:
                time.sleep(2)
            else:
                raise

# 翻页拉全量（page 与 cursor 均可，这里用 page）
all_friends, page = [], 1
seen = set()
while True:
    r = invoke("friendships", "friends/biz", {"count": 20, "page": page})
    users = r["result"]["users"]
    if not users:
        break
    for u in users:                          # 去重兜底
        if u["idstr"] not in seen:
            seen.add(u["idstr"])
            all_friends.append(u)
    if page * 20 >= r["result"]["total_number"]:
        break
    page += 1
    time.sleep(0.3)                          # 温和限速

# 原始数据落盘（压缩字段，便于复核与重跑）
# 落盘路径由调用方/当前目录决定，不要写死：
#   Claude Code/Codex -> 项目目录   Minis -> workspace   服务器 -> ~/
keep = ["id","idstr","screen_name","description","followers_count",
        "verified","verified_type","verified_reason","location","gender"]
json.dump([{k: u.get(k) for k in keep} for u in all_friends],
          open("weibo_follows_raw.json", "w"),     # 当前目录
          ensure_ascii=False, indent=1)
```

## 大V筛选（直接用内联字段）

```python
big_vs = [u for u in all_friends
          if (u.get("followers_count") or 0) > 10000 or u.get("verified")]
```

品类归类、成分标签、多样性评分、一句话总结：见 [cocoon-detection.md](cocoon-detection.md)。

## 调用量参考

**默认深度 = 全量拉取**（关注列表定律的前提是看完整列表）。调用量参考：

| 深度 | 拉取范围 | 调用量 |
|------|---------|:--:|
| 快扫（仅用户主动要求时） | 前 100 个关注 | ~10 |
| 标准（仅用户主动要求时） | 前 200 个关注 | ~20 |
| **全量（默认）** | 全部关注 | total_number ÷ 10（重叠窗口步进） |

## 错误处理（三段式：触发条件 → 一线修复 → 仍失败兜底）

| 触发条件 | 一线修复 | 仍失败 → 兜底 |
|---------|---------|--------------|
| HTTP 401 / 403 | 核对 `WEIBO_CLI_TOKEN` 是否过期、套餐是否含 friendships 接口 | 🔴 停下找用户重新签发或升级套餐，禁止带病继续 |
| HTTP 429（额度尽） | 等 60s 重试 1 次 | 仍 429 → 等下一个整点窗口；连续两个窗口 429 → 🔴 停下找用户（等额度或换套餐） |
| `COUNT_EXCEEDS_MAX` | count 降到 20 重试（20 是服务端硬上限） | 仍报错 → 停下报给用户，接口行为异常 |
| HTTP 5xx | 退避 2s 重试，最多 3 次 | 仍失败 → 已拉取部分先落盘，转入 🔴 强制检查点 |
| 单段返回空 `users` | 步进跳过该段继续拉 | 连续 3 个整窗口无新增 → 视为到底，正常收敛停止 |
| 取回数 < total 且缺口 >10% | ——（这不是错误，是状态） | 🔴 强制检查点：交用户选 A / B，见下节 |

## 降级兜底与 🔴 强制检查点

### 兜底策略（自动执行，不问用户）

> 阻塞模式（缺口 / cursor 断裂 / 排序漂移）的实测细节见上文「已实测事实」第 2 条，此处只写对策。

1. **重叠窗口**：count=20 + 步进 10，消除排序漂移缝隙。
2. **空段跳过**：单段空则步进继续，绝不在单段死磕。
3. **二次扫描**：首轮结束后，对 0~total 内首轮为空的段以 50% 重叠重扫一遍（捕捉中途解封/恢复的账号）。
4. **收敛判定**：连续 3 个整窗口无新增，或扫描越界 total+40 → 停止。

### 🔴 强制检查点（必须停下问用户）

**触发条件**：采集结束且 `缺口 = total_number − 取回去重数 > total_number × 10%`。

触发后**必须停止并询问**，展示实际数字，例如：

```
⚠️ 关注列表拉取不完整
API 报告关注 763 人，实际取回 640 人（缺口 123，约 16%）。
缺口通常为注销/私密/被封账号，但也可能包含未拉到的活跃账号。

请选择：
A. 按当前已拉取的 640 人直接开跑 —— 报告标注覆盖率 83.9%，结论注明"基于部分样本"
B. 降级重扫、全拉完再跑 —— 对空段做二次重叠扫描（多花约 2 分钟），能捞回多少算多少，捞完回到本检查点复检
（附加项）C. 缩小深度 —— 只分析确定性最高的前 200 个关注（快扫口径，缺口影响最小）
```

**纪律**：
- 用户不选择，不得进入分析阶段。
- 选 A/C 时，报告标题下必须标注 `样本覆盖率 xx%`，且判词卡注明"基于部分关注样本"。
- 缺口 ≤ 10% 视为正常损耗，不触发检查点，报告备注缺口数即可。
