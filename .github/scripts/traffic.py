#!/usr/bin/env python3
"""把 GitHub Traffic 的 14 天窗口抄成永久记录。

⚠️ **存在理由：GitHub 的 traffic 数据只保留 14 天，过了就永久没了。**
   实测 2026-09-06 拉到的窗口是 08-23 → 09-05，而 08-24 那天的 51 次 clone
   第二天就掉出窗口。不抄下来，任何超过两周的趋势都无从谈起。

三份产物，各自回答不同的问题：
  traffic/daily.csv       逐日的 clone 与 view —— 唯一需要长期累积的东西
  traffic/snapshots/*.json 每次拉取的原始返回，含 paths 与 referrers
                           （这两个端点给的是 14 天聚合，不是逐日序列，
                            所以只能按拉取日快照，不能合并成时间序列）
  traffic/latest.json      最近一次的四个端点原样，方便直接看

合并规则：**按日期覆盖**。同一天可能被拉到两次，第二次的数更全
（当天还没过完时 GitHub 给的是当日累计），所以后来的覆盖先前的。
已经过完的日子 GitHub 不会再改，覆盖是幂等的。
"""
import json, os, sys, csv, urllib.request, datetime as dt, pathlib

REPO  = os.environ.get("TRAFFIC_REPO") or os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]
ROOT  = pathlib.Path(__file__).resolve().parents[2]
OUT   = ROOT / "traffic"

def api(path):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/traffic/{path}",
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "traffic-recorder"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

try:
    data = {k: api(k) for k in ("clones", "views", "popular/paths", "popular/referrers")}
except urllib.error.HTTPError as e:
    # ⚠️ 只报状态码不够 —— GitHub 的 403 响应体里写着到底是哪种 403
    #    （"Must have push access" / "Resource not accessible by personal access token"
    #     / "Resource not accessible by integration"），三种的修法完全不同。
    #    第一版只打了 403 Forbidden，等于把三种病因折成一句。
    try:
        print(f"::notice::GitHub 说: {e.read().decode()[:300]}", file=sys.stderr)
    except Exception:
        pass
    # ⚠️ token 本身**绝不能打**。只打前缀和长度 —— 足够分辨用的是哪一个:
    #    ghp_=classic PAT · github_pat_=fine-grained · ghs_=Actions 默认 GITHUB_TOKEN
    kind = ("ghs_(Actions 默认 token)" if TOKEN.startswith("ghs_")
            else "ghp_(classic PAT)" if TOKEN.startswith("ghp_")
            else "github_pat_(fine-grained PAT)" if TOKEN.startswith("github_pat_")
            else "未知前缀")
    print(f"::notice::本次用的 token 类型: {kind} · 长度 {len(TOKEN)}", file=sys.stderr)
    # ⚠️ 403 基本只有一个原因：token 没有仓库的 write access。
    #    Traffic API 要 write，而 Actions 默认的 GITHUB_TOKEN 未必够 ——
    #    `permissions:` 块里根本没有 administration 这一档。
    #    真是这样就建一个 PAT（classic 勾 repo，或 fine-grained 给 Administration:read），
    #    存成仓库 secret `TRAFFIC_TOKEN`，workflow 会优先用它。
    print(f"::error::Traffic API {e.code} {e.reason} —— token 权限不足的话，"
          f"建一个 PAT 存成 secret TRAFFIC_TOKEN（见本文件注释）", file=sys.stderr)
    raise

# ── 逐日序列：按日期合并 ──────────────────────────────────────────────
OUT.mkdir(exist_ok=True)
csv_path = OUT / "daily.csv"
rows = {}
if csv_path.exists():
    with csv_path.open() as f:
        for r in csv.DictReader(f):
            rows[r["date"]] = r

for kind, key in (("clones", "clones"), ("views", "views")):
    for x in data[kind][key]:
        d = x["timestamp"][:10]
        r = rows.setdefault(d, {"date": d, "clones": "", "clone_uniques": "",
                                "views": "", "view_uniques": ""})
        if kind == "clones":
            r["clones"], r["clone_uniques"] = x["count"], x["uniques"]
        else:
            r["views"], r["view_uniques"] = x["count"], x["uniques"]

with csv_path.open("w", newline="") as f:
    w = csv.DictWriter(f, ["date", "clones", "clone_uniques", "views", "view_uniques"])
    w.writeheader()
    for d in sorted(rows):
        w.writerow(rows[d])

# ── 快照：paths / referrers 是 14 天聚合，只能按拉取日存 ────────────────
stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
(OUT / "snapshots").mkdir(exist_ok=True)
(OUT / "snapshots" / f"{stamp}.json").write_text(
    json.dumps({"fetchedAt": dt.datetime.now(dt.timezone.utc).isoformat(), **data},
               ensure_ascii=False, indent=1))
(OUT / "latest.json").write_text(
    json.dumps({"fetchedAt": dt.datetime.now(dt.timezone.utc).isoformat(), **data},
               ensure_ascii=False, indent=1))

first, last = min(rows), max(rows)
print(f"daily.csv 现有 {len(rows)} 天（{first} → {last}）")
print(f"本次窗口 clone {data['clones']['count']} 次 / 唯一 {data['clones']['uniques']}"
      f" · 浏览 {data['views']['count']} 次 / 访客 {data['views']['uniques']}")
