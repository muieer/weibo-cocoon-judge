#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
判词引擎 · verdict_engine（v1.1）
四层组装：闭合度分数 → 母档(3) × 子档(3) → 品类血肉(13) → 措辞变体(3)
= 9 × 13 × 3 = 351 个不重复判词出口

v1.1 变更：
- 母档改「硬规则优先 + 分数定子档」混合判定，杜绝边界误判（如 90% 单一品类落在平衡档）
- 每个子档措辞变体 2 → 3，变体选择混入次品类，进一步压低撞词率
- 移除测试中的个人 uid，仅用中性示例

纯标准库，Python >= 3.6，任意 Agent 环境可用。
"""

# ---------- 品类血肉表（意象 A = 那个人的世界；意象 B = 那个人的腔调）----------
IMAGERY = {
    "科技/AI":   ("一个永远在奇点前夜的世界", "看什么都想优化一遍"),
    "军事/时政": ("一个永远在开战前夜的世界", "三句话不离博弈和棋手"),
    "财经/投资": ("一个永远在崩盘前夜的世界", "把一切都看成仓位"),
    "影视/媒体": ("一个永远亮着监视器的世界", "把生活当素材库"),
    "知识/教育": ("一个永远在上课的世界", "什么都能引经据典"),
    "生活/美食": ("一个永远在饭桌旁的世界", "日子过成了菜谱"),
    "娱乐/游戏": ("一个永远在应援席的世界", "热搜即史书"),
    "商业/企业": ("一个永远在开会的世界", "见面先递名片"),
    "女权/性别对立": ("一个永远在辩论席的世界", "万事皆可归因于立场"),
    "动物保护":   ("一个永远在救助站的世界", "万物皆有亲缘"),
    "中医养生":   ("一个永远在调理期的世界", "先祛湿，再说别的"),
    "伪科学/玄学": ("一个永远在渡劫中的世界", "水逆背下所有的锅"),
    "其他":      ("一个说不清道不明的世界", "无法归类本身成了类别"),
}

# ---------- 9 个子档骨架（每个 3 个措辞变体，{A}{B} 由品类血肉填充）----------
FRAMES = {
    # 🔴 茧房
    "深茧": [
        "你的关注列表只剩一种味道：{A}。{B}——这不是你在看世界，是世界从你这里路过。",
        "{A}，是你列表里唯一的天气。{B}，久了就忘了还有别的季节。",
        "整面墙都是{A}。{B}——你不是在挑信息，是信息在替你挑，你只负责点头。",
    ],
    "回音壁": [
        "{A}。你听到的每一个声音，都是自己的回声——{B}，是这场回声的口音。",
        "整张列表在替你说同一句话：{B}。{A}，没有第二个声部。",
        "{A}，墙内一片和谐。{B}——你以为是世界在附和你，其实是你在删世界。",
    ],
    "同温层": [
        "{A}——温度恒定、无人反驳。{B}，在这里不是观点，是空气。",
        "你把{A}当成了常识。{B}只是大家的呼吸，没人觉得它需要论证。",
        "{A}。同温层最舒服的地方，是它从不告诉你外面几度——{B}也一样。",
    ],
    # 🟡 偏食
    "重口偏食": [
        "{A}，主菜堆到冒尖，配菜基本没动。{B}——胃口偏得很诚实。",
        "你的信息食谱里，{B}占了大头。{A}吃太急，别的味道来不及尝。",
        "{A}几乎是全部——{B}。盘子还端得稳，但已经看不出这是一张桌子。",
    ],
    "偏食": [
        "{A}。菜单很厚，你总点这一道。{B}——好吃，但别的味道正在消失。",
        "{B}，是你列表的主导节奏。{A}不算糟，只是太常坐同一个位子。",
        "一半以上的座位留给了{A}。{B}——你的信息餐桌开始偏科了。",
    ],
    "单一主粮": [
        "{A}是你的主粮，这没问题；只是{B}久了，会误以为别人也这么吃。",
        "你有明确的偏好：{B}。{A}够扎实，就是杂粮碟有点空。",
        "{A}打底，{B}添味。主粮明确的人有主心骨——记得偶尔换换筷子。",
    ],
    # 🟢 平衡
    "有主粮的杂食": [
        "{A}是你的主粮，但你还在吃杂粮。偏好清晰，胃口不偏。",
        "{B}是你的常座，不是你的牢房——{A}之外，你还留着别的入口。",
        "{A}占的比重不小，但杂粮咽得更勤。有偏好的人多，不偏的人少。",
    ],
    "采样均衡": [
        "{A}只是你的一碟，不是你的全部。你的列表像自助餐，不是定食。",
        "你{B}，但没停在这儿。{A}之外，声音是杂的——杂是好事。",
        "{A}在列，但压不住场。你的信息渠道像撒开的网，不是一根线。",
    ],
    "杂食动物": [
        "什么都看，什么都不全信。{A}是你的一碟小菜，不是你的全世界。",
        "{B}？当然。但你的列表里没有哪一类能独占话筒——最难被洗脑的类型。",
        "连{A}都只占一小格。你的列表几乎没有主色——这在今天是一种稀缺。",
    ],
}

TIERS = {"茧房": ["深茧", "回音壁", "同温层"],
         "偏食": ["重口偏食", "偏食", "单一主粮"],
         "平衡": ["有主粮的杂食", "采样均衡", "杂食动物"]}
TIER_ICON = {"茧房": "🔴", "偏食": "🟡", "平衡": "🟢"}

# ---------- 闭合度分数（0~1，越高越封闭）----------
def closure_score(top1, top2, diversity, risk_pct):
    s_top1 = min(top1 / 0.60, 1.0)
    s_top2 = min(top2 / 0.85, 1.0)
    s_div = min(max((0.75 - diversity) / 0.75, 0), 1.0)
    s_risk = min(risk_pct / 0.50, 1.0)
    return 0.35 * s_top1 + 0.25 * s_top2 + 0.25 * s_div + 0.15 * s_risk

# ---------- 母档：硬规则优先（防误判），与分数无关 ----------
def tier_of(top1, top2, diversity, risk_pct):
    """任一硬规则命中即定档，保证极端画像永远不会被轻判。"""
    if (top1 >= 0.55 or diversity < 0.35 or risk_pct >= 0.50
            or (top2 >= 0.75 and diversity < 0.50)):
        return "茧房"
    if (top2 >= 0.50 or diversity < 0.60 or risk_pct >= 0.25 or top1 >= 0.35):
        return "偏食"
    return "平衡"

# ---------- 子档：档内分数分带 + 极端覆盖 ----------
SUB_BANDS = {
    "茧房": [(0.74, 0), (0.66, 1), (0.00, 2)],
    "偏食": [(0.56, 0), (0.46, 1), (0.00, 2)],
    "平衡": [(0.26, 0), (0.14, 1), (0.00, 2)],
}

def _variant(top_cat, second_cat, uid, n):
    """确定性选变体：混入主品类与次品类，同档同主品类也能错开。"""
    h = (int(uid) * 31 + sum(ord(c) for c in top_cat) * 7
         + sum(ord(c) for c in (second_cat or ""))) & 0xFFFFFFFF
    return h % n

def judge(dist, diversity, risk_pct, dominant_cat=None, dominant_share=None,
          flag_shares=None, uid=0):
    """
    dist: {品类: 占比}；diversity: 0~1；risk_pct: 0~1
    flag_shares: {高危旗标: 占比}，某旗标超过主品类时判词改口指向旗标
    uid: 任意稳定整数/字符串（微博 uid 最佳），用于确定性选措辞变体
    """
    shares = {k: v for k, v in dist.items() if k != "其他"} or dict(dist)
    ordered_cats = sorted(shares, key=lambda k: -shares[k])
    top_cat = dominant_cat or ordered_cats[0]
    top1 = dominant_share if dominant_share is not None else shares[top_cat]
    second_cat = next((c for c in ordered_cats if c != top_cat), None)
    vals = sorted(shares.values(), reverse=True)
    top2 = sum(vals[:2])

    imagery_key = top_cat
    if flag_shares:
        f_cat, f_val = max(flag_shares.items(), key=lambda x: x[1])
        if f_val > top1 and f_cat in IMAGERY:
            imagery_key, top1 = f_cat, f_val

    score = closure_score(top1, top2, diversity, risk_pct)
    tier = tier_of(top1, top2, diversity, risk_pct)

    if tier == "茧房" and top1 >= 0.70:
        idx = 0                                  # 单品类 ≥70% 直接深茧
    else:
        idx = next(i for lb, i in SUB_BANDS[tier] if score >= lb)

    sub = TIERS[tier][idx]
    A, B = IMAGERY.get(imagery_key, IMAGERY["其他"])
    variants = FRAMES[sub]
    text = variants[_variant(top_cat, second_cat, uid, len(variants))].format(A=A, B=B)

    return {
        "closure_score": round(score, 3),
        "tier": tier, "tier_icon": TIER_ICON[tier],
        "sub_tier": sub, "sub_index": idx + 1,
        "verdict_code": f"{TIER_ICON[tier]} {tier}·{sub} 第{idx+1}档",
        "imagery_source": imagery_key,
        "dominant_category": top_cat, "top1": round(top1, 3),
        "top2": round(top2, 3), "diversity": round(diversity, 3),
        "risk_pct": round(risk_pct, 3),
        "text": text,
    }


if __name__ == "__main__":
    # 自测：覆盖四类典型画像 + 边界（无个人数据，uid 均为中性示例）
    cases = {
        "军事茧房":   ({"军事/时政": .55, "财经/投资": .25, "科技/AI": .05, "其他": .15}, 0.30, 0.62, 10001),
        "单一垄断":   ({"军事/时政": .90, "其他": .10}, 0.28, 0.10, 10002),
        "科技偏食":   ({"科技/AI": .544, "影视/媒体": .148, "商业/企业": .09, "其他": .22}, 0.692, 0.056, 20002),
        "养生茧房":   ({"中医养生": .40, "伪科学/玄学": .20, "生活/美食": .25, "其他": .15}, 0.42, 0.55, 10003),
        "健康杂食":   ({"知识/教育": .18, "科技/AI": .17, "生活/美食": .16, "娱乐/游戏": .15, "其他": .34}, 0.88, 0.04, 10004),
    }
    for name, (dist, div, risk, uid) in cases.items():
        flags = {"中医养生": dist.get("中医养生", 0), "伪科学/玄学": dist.get("伪科学/玄学", 0)}
        r = judge(dist, div, risk, flag_shares=flags, uid=uid)
        print(f"\n【{name}】{r['verdict_code']}  闭合度 {r['closure_score']}")
        print("  ", r["text"])
    # 撞词率说明：同(子档,主品类)内 1/3；全表 351 出口
