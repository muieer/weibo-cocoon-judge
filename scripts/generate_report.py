#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
茧房检测报告 · 正式 HTML 生成器（和纸极简模板，2026-08-29 定稿）
v1.1：跨 Agent 可用 / 路径可配 / 时间戳增量不覆盖 / 零个人数据 / 自带 HTML 自检

用法（所有参数均可省略，默认读当前目录）：
  python3 generate_report.py \
    --result  cocoon_result.json \
    --classified weibo_follows_classified.json \
    --outdir  ./output \
    --name    昵称(可选，缺省读 result JSON 的 screen_name) \
    --uid     微博uid(可选，用于判词措辞变体；缺省由昵称哈希导出)

依赖：verdict_engine.py（同目录）；纯标准库，Python >= 3.6。
"""
import argparse, json, re, sys, os, hashlib
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verdict_engine import judge as _judge

# ---------- 高危旗标（与 cocoon-detection.md Step3 一致）----------
FLAGS = {
    "女权/性别对立": ["女权", "女性主义", "性别对立", "田园女权"],
    "动物保护": ["动保", "动物保护", "流浪动物", "流浪猫", "流浪狗", "领养代替", "TNR"],
    "中医养生": ["中医", "养生", "经络", "艾灸", "药膳", "老中医", "排毒", "祛湿"],
    "伪科学/玄学": ["阴谋论", "玄学", "风水", "占卜", "算命", "星座运势", "量子波动", "磁疗", "保健品", "能量石", "水素"],
}
CATCOL = {"科技/AI": "#2563eb", "影视/媒体": "#db2777", "商业/企业": "#ea580c", "生活/美食": "#16a34a",
          "知识/教育": "#7c3aed", "财经/投资": "#0891b2", "娱乐/游戏": "#be185d", "军事/时政": "#475569", "其他": "#94a3b8"}
ORDER = ["科技/AI", "影视/媒体", "商业/企业", "生活/美食", "知识/教育", "财经/投资", "娱乐/游戏", "军事/时政", "其他"]
_PLATFORM = re.compile(r"^(微博|新浪|超话)")
PLAT_EXTRA = {"粉丝头条官方微博", "头条文章", "大众评议小广播"}

CSS = """*{margin:0;padding:0;box-sizing:border-box}
body{background:#F7F3EA;color:#22252B;font-family:-apple-system,"PingFang SC",sans-serif;line-height:1.8;padding:0}
.wrap{max-width:480px;margin:0 auto;background:#F7F3EA}
.top{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid #C9C2B0;padding:26px 18px 18px}
.titlebox h1{font-family:"Noto Serif SC",serif;font-size:48px;font-weight:600;letter-spacing:8px;line-height:1.2}
.titlebox .en{font-size:10px;letter-spacing:4px;color:#8B8471;text-transform:uppercase;margin-top:4px}
.vertical{writing-mode:vertical-rl;font-family:"Noto Serif SC",serif;font-size:11px;letter-spacing:3px;color:#C94F3C;border-left:1px solid #C9C2B0;padding-left:8px}
.meta{font-size:10px;color:#8B8471;letter-spacing:2px;padding:8px 18px;border-bottom:1px solid #C9C2B0}
.sec{padding:20px 18px;border-bottom:1px solid #C9C2B0}
.sec h2{font-family:"Noto Serif SC",serif;font-size:15px;font-weight:600;letter-spacing:4px;margin-bottom:14px;position:relative;padding-left:12px}
.sec h2::before{content:"";position:absolute;left:0;top:4px;bottom:4px;width:3px;background:#24366B}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:0}
.stat{padding:10px 0;text-align:center}
.stat .n{font-size:24px;font-weight:300;letter-spacing:1px;font-variant-numeric:tabular-nums}
.stat .l{font-size:10px;color:#8B8471;letter-spacing:2px;margin-top:2px}
.pills{display:flex;flex-wrap:wrap;gap:10px}
.pill{font-size:12px;letter-spacing:2px;padding:4px 16px;border:1px solid #24366B;color:#24366B;border-radius:0}
.pill.p0{background:#24366B;color:#F7F3EA}
.pill.p1{color:#C94F3C;border-color:#C94F3C}
.bar{display:flex;align-items:center;margin-bottom:10px;font-size:12px}
.bl{width:84px;flex-shrink:0;color:#5A5444;letter-spacing:1px}
.bt{flex:1;height:4px;background:#DDD6C4;margin:0 10px}
.bt span{display:block;height:100%}
.bar b{font-size:11px;font-variant-numeric:tabular-nums;color:#5A5444}
.kv{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #E3DECF;font-size:12px;letter-spacing:1px}
.kv:last-child{border-bottom:none}
.kv b{font-variant-numeric:tabular-nums;font-weight:400}
.meter{position:relative;height:30px;margin:10px 0 6px}
.meter .line{position:absolute;left:0;right:0;top:14px;height:1px;background:#C9C2B0}
.meter .dot{position:absolute;top:7px;width:16px;height:16px;background:#24366B;transform:translateX(-50%) rotate(45deg)}
.note{font-size:10px;color:#8B8471;margin-top:8px;letter-spacing:1px}
.verdict{border:1px solid #C94F3C;padding:22px 18px;margin:0 18px 20px;position:relative}
.verdict::after{content:"判";position:absolute;top:-1px;right:14px;background:#C94F3C;color:#F7F3EA;font-size:10px;letter-spacing:2px;padding:2px 6px}
.verdict .lab{font-size:10px;color:#C94F3C;letter-spacing:3px;text-transform:uppercase}
.verdict .name{font-family:"Noto Serif SC",serif;font-size:20px;font-weight:600;letter-spacing:5px;margin:6px 0 10px}
.verdict p{font-size:13px;line-height:2;color:#3A362C}
.foot{font-size:10px;color:#8B8471;text-align:center;padding:18px;letter-spacing:3px}
@media (min-width:768px){
  .wrap{max-width:720px}
  .titlebox h1{font-size:72px;letter-spacing:12px}
  .grid{grid-template-columns:repeat(4,1fr)}
  .sec{padding:26px 24px}
  .top,.meta{padding-left:24px;padding-right:24px}
  .verdict{margin:0 24px 24px}
}"""


def _platform_of(u):
    n = u.get("screen_name", "") or ""
    return bool(_PLATFORM.match(n) or n in PLAT_EXTRA)


def html_check(html, result):
    """产物自检（9 项），返回 (ok, problems[])"""
    p = []
    if "charset" not in html[:200].lower():
        p.append("缺少 charset 声明")
    if html.count("<div") != html.count("</div>"):
        p.append(f"div 不配对: {html.count('<div')} vs {html.count('</div>')}")
    if html.count("<section") != html.count("</section>"):
        p.append("section 不配对")
    for pat in (r"\{[a-z_]+\}", r"\{\{", r"None", r"nan", r"undefined", r"NaN"):
        m = re.findall(pat, html)
        if m:
            p.append(f"疑似占位符/异常值残留: {m[:5]}")
    if not html.rstrip().endswith("</html>"):
        p.append("文件未正常收尾")
    if 'class="verdict"' not in html:
        p.append("缺少判词卡")
    if result.get("total_follows_api") and str(result["total_follows_api"]) not in html:
        p.append("关注总数未注入")
    return (len(p) == 0, p)


def build(result_path, classified_path, uid, name_override, outdir):
    R = json.load(open(result_path, encoding="utf-8"))
    DATA = json.load(open(classified_path, encoding="utf-8"))
    name = name_override or R.get("screen_name") or "用户"

    total = R.get("total_follows_api", len(DATA))
    retrievable = R.get("retrievable", len(DATA))
    unretrievable = R.get("unretrievable", total - retrievable)

    # 大V / 平台官号 / 素人：优先用 _cat 标记，缺失则按规则现算
    if DATA and "_cat" in DATA[0]:
        big_all = [u for u in DATA if (u.get("followers_count") or 0) > 10000 or u.get("verified")]
        plat = [u for u in big_all if u.get("_cat") == "平台官方" or _platform_of(u)]
        big_vs = [u for u in big_all if u not in plat]
    else:
        big_all = [u for u in DATA if (u.get("followers_count") or 0) > 10000 or u.get("verified")]
        plat = [u for u in big_all if _platform_of(u)]
        big_vs = [u for u in big_all if u not in plat]
    laypeople = len(DATA) - len(big_all)
    N = len(big_vs)
    if N == 0:
        raise SystemExit("大V 数为 0：数据异常，请检查 classified JSON")

    hits = Counter()
    for u in big_vs:
        t = (u.get("screen_name", "") + " " + (u.get("description") or "") + " " + (u.get("verified_reason") or ""))
        for f, kws in FLAGS.items():
            if any(re.search(k, t) for k in kws):
                hits[f] += 1
    mf = sum(1 for u in big_vs if u.get("_cat", u.get("screen_name")) in ("军事/时政", "财经/投资"))
    risk_pct = (mf + sum(hits.values())) / N
    dist = R["category_distribution"]
    div = R["diversity_score"]

    uid = uid or (int(hashlib.sha256(name.encode()).hexdigest()[:8], 16))
    r = _judge(dist, div, risk_pct, flag_shares={f: 0 for f in FLAGS}, uid=uid)
    VNAME, VTEXT = r["sub_tier"], r["text"]
    VL = r["tier_icon"] + " " + r["tier"] + " · " + r["sub_tier"] + " 第" + str(r["sub_index"]) + "档"

    bars = "".join(f'<div class="bar"><span class="bl">{c}</span><span class="bt"><span style="width:{dist[c]*100:.1f}%;background:{CATCOL.get(c, "#94a3b8")}"></span></span><b>{dist[c]*100:.1f}%</b></div>' for c in ORDER if c in dist)
    risk_rows = f'<div class="kv"><span>军事/时政 + 财经/投资</span><b>{mf} 人（{mf/N*100:.1f}%）</b></div>'
    risk_rows += "".join(f'<div class="kv"><span>{f}</span><b>{n} 人（{n/N*100:.1f}%）</b></div>' for f, n in hits.most_common()) or '<div class="kv"><span>女权/动保/中医/伪科学旗标</span><b>0 命中</b></div>'
    pills = "".join(f'<span class="pill p{i}">{t}</span>' for i, t in enumerate(R.get("tags", [])))
    ver = "".join(f'<div class="kv"><span>{k}</span><b>{v*100:.1f}%</b></div>' for k, v in R.get("verification", {}).items())
    tier_rows = "".join(f'<div class="kv"><span>{k}</span><b>{v} 人</b></div>' for k, v in sorted(R.get("follower_tier", {}).items(), key=lambda x: -x[1]))
    top10 = "".join(f'<div class="kv"><span>{u["screen_name"]}</span><b>{(u.get("followers_count") or 0)//10000}万粉 · {u.get("_cat", "")}</b></div>' for u in sorted([u for u in DATA if not (u.get("_cat") == "平台官方" or _platform_of(u))], key=lambda x: -(x.get("followers_count") or 0))[:10])
    cn_date = datetime.now().strftime("%Y 年 %m 月 %d 日")

    one = R.get("one_liner")
    ending = f'<div class="sec"><h2>结语</h2><p style="font-size:13px;line-height:2;color:#3A362C">{one}</p></div>' if one else ""

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>茧房検測 · {name}</title><style>{CSS}</style></head><body><div class="wrap">
<div class="top"><div class="titlebox"><h1>茧房検測</h1><div class="en">Cocoon Detection</div></div><div class="vertical">情報環境·自診</div></div>
<div class="meta">@{name} · {cn_date} · 全量 {total} 关注 · {N} 大V 入档</div>
<div class="sec"><h2>总览</h2><div class="grid">
<div class="stat"><div class="n">{total}</div><div class="l">关注总数</div></div>
<div class="stat"><div class="n">{N}</div><div class="l">大V</div></div>
<div class="stat"><div class="n">{div}</div><div class="l">多样性</div></div>
<div class="stat"><div class="n">{risk_pct:.0%}</div><div class="l">高危浓度</div></div></div>
<div class="note">API 计 {total}，可取回 {retrievable}（{unretrievable} 注销/私密/不可见）；{laypeople} 素人 + {len(plat)} 平台官号不参评。</div></div>
<div class="sec"><h2>成分</h2><div class="pills">{pills}</div></div>
<div class="sec"><h2>品类</h2>{bars}</div>
<div class="sec"><h2>高危浓度</h2>{risk_rows}<div class="note">浓度 {risk_pct:.1f}%。&lt;10% 噪音，10–30% 偏好，30–50% 偏食，≥50% 茧房信号。关注本身不是问题，浓度失衡才是。</div></div>
<div class="sec"><h2>多样性 {div}</h2><div class="meter"><div class="line"></div><div class="dot" style="left:{min(max(div*100,0),100):.0f}%"></div></div>
<div class="note">信息熵归一化：&gt;0.8 丰富 · 0.5–0.8 中等 · &lt;0.5 风险。</div></div>
<div class="sec"><h2>认证 · 量级</h2>{ver}{tier_rows}</div>
<div class="verdict"><div class="lab">{VL}</div><div class="name">{VNAME}</div><p>{VTEXT}</p>
<div class="note" style="margin-top:10px">闭合度 {r["closure_score"]} ｜ Top2 {r["top2"]*100:.1f}% ｜ 意象源 {r["imagery_source"]}</div></div>
<div class="sec"><h2>最大关注</h2>{top10}</div>
{ending}
<div class="foot">方法论：@tombkeeper 关注列表定律 · 社交行为观察 · 微博茧房判断器</div>
</div></body></html>"""

    ok, problems = html_check(html, R)
    os.makedirs(outdir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = re.sub(r'[\\/:*?"<>|\s]', "_", name)
    out = os.path.join(outdir, f"茧房检测报告_{base}_{ts}.html")
    i = 1
    while os.path.exists(out):          # 绝不覆盖：时间戳到秒仍撞名则追加序号
        out = os.path.join(outdir, f"茧房检测报告_{base}_{ts}_{i}.html")
        i += 1
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out, r, ok, problems


def main():
    ap = argparse.ArgumentParser(description="茧房检测报告生成器（和纸极简模板）")
    ap.add_argument("--result", default="cocoon_result.json", help="检测结果 JSON（默认 ./cocoon_result.json）")
    ap.add_argument("--classified", default="weibo_follows_classified.json", help="已分类关注列表 JSON")
    ap.add_argument("--outdir", default=".", help="输出目录（默认当前目录）")
    ap.add_argument("--name", default=None, help="报告署名昵称（缺省读 result JSON）")
    ap.add_argument("--uid", type=str, default="", help="微博 uid（判词变体种子，缺省由昵称哈希导出）")
    a = ap.parse_args()
    uid = int(a.uid) if str(a.uid).isdigit() else 0
    out, r, ok, problems = build(a.result, a.classified, uid, a.name, a.outdir)
    print(f"已生成: {out} ({os.path.getsize(out)//1024}KB)")
    print(f"判词: {r['verdict_code']} — {r['text']}")
    print("HTML 自检: " + ("PASS" if ok else "FAIL -> " + "; ".join(problems)))
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
