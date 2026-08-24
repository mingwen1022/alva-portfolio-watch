"""M18 全量标注 · 本地 codex CLI · 0 Alva credits。

  pass1  全量分批抽取（结构化输出，--output-schema）
  pass2  L6 重试：把逐 id 的具体错误喂回去，重跑一次
  pass3  仍失败 → 降级 rhetorical（保守方向），同时留存 LLM 原始标签

原始输出先落盘（raw/<pass>/<bid>.json），再解析 —— 见 llm-log §四的教训。
"""
import os, sys, json, gzip, time, argparse, subprocess, tempfile, shutil, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m18lib as L

S = os.environ["S"]
ROOT = f"{S}/porun2"
SCH = f"{ROOT}/scripts/schema.json"
CAND = "/Users/ming/project/alva/backtest/data/po-derived/candidates.json.gz"
MODEL = "gpt-5.6-luna"
EFFORT = "low"


def call_codex(prompt, tag, attempt=0):
    d = tempfile.mkdtemp(prefix="cx")
    outf = os.path.join(d, "out.json")
    cmd = ["codex", "exec", "-m", MODEL, "--skip-git-repo-check", "--ephemeral",
           "-s", "read-only", "-C", d, "--output-schema", SCH, "-o", outf,
           "-c", f'model_reasoning_effort="{EFFORT}"', "--color", "never", prompt]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        raw = open(outf).read() if os.path.exists(outf) else ""
        rc = p.returncode
        err = (p.stderr or "")[-400:]
    except subprocess.TimeoutExpired:
        raw, rc, err = "", -9, "TIMEOUT"
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return raw, rc, err


def one_batch(items, bid, passdir, err_note=None):
    """返回 (ok_list, bad_map, rawlab_map, stat)"""
    stat = {"bid": bid, "n": len(items), "calls": 0, "fenced": False,
            "parse_fail": False, "rc": None, "secs": 0.0, "layer_hits": {}}
    t0 = time.time()
    raw = ""
    for attempt in range(3):
        raw, rc, err = call_codex(L.build_prompt(items, err_note), bid, attempt)
        stat["calls"] += 1
        stat["rc"] = rc
        if raw.strip():
            break
        stat.setdefault("retries_transport", 0)
        stat["retries_transport"] += 1
        stat["err"] = err
        time.sleep(5 + 10 * attempt)
    os.makedirs(passdir, exist_ok=True)
    with open(os.path.join(passdir, f"{bid}.json"), "w") as f:
        f.write(raw)
    s, fenced = L.strip_fence(raw)
    stat["fenced"] = fenced
    try:
        obj = json.loads(s)
    except Exception:
        obj = None
        stat["parse_fail"] = True
    arr = L.coerce_array(obj) if obj is not None else None
    if arr is None:
        stat["parse_fail"] = True
        v = {"bad": {it["id"]: {"layer": "L2", "msg": "batch output unparseable"} for it in items},
             "ok": [], "rawlab": {}, "errs": ["L2:*:parse failed"], "layer_hits": {"L2": len(items)}}
    else:
        v = L.validate(items, arr)
    stat["layer_hits"] = v["layer_hits"]
    stat["secs"] = round(time.time() - t0, 1)
    stat["first_pass"] = len(v["ok"])
    return v["ok"], v["bad"], v["rawlab"], stat


def run_pool(batches, passdir, notes=None, workers=10):
    ok_all, bad_all, rawlab_all, stats = [], {}, {}, []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {}
        for bid, items in batches:
            note = notes.get(bid) if notes else None
            futs[ex.submit(one_batch, items, bid, passdir, note)] = bid
        done = 0
        for fu in as_completed(futs):
            ok, bad, rawlab, st = fu.result()
            ok_all += ok; bad_all.update(bad); rawlab_all.update(rawlab); stats.append(st)
            done += 1
            if done % 10 == 0 or done == len(futs):
                print(f"  [{done}/{len(futs)}] ok so far {len(ok_all)}", flush=True)
    return ok_all, bad_all, rawlab_all, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    cands = json.load(gzip.open(CAND))
    if a.limit: cands = cands[:a.limit]
    items = [{"id": c["cid"], "text": c["text"]} for c in cands]
    print(f"候选 {len(items)} 条 · 批大小 {a.batch} · 并发 {a.workers}", flush=True)

    batches = [(f"b{i//a.batch:04d}", items[i:i+a.batch]) for i in range(0, len(items), a.batch)]
    print(f"pass1 {len(batches)} 批", flush=True)
    t0 = time.time()
    ok1, bad1, rawlab1, st1 = run_pool(batches, f"{ROOT}/raw/pass1", workers=a.workers)
    print(f"pass1 完成 {len(ok1)}/{len(items)} 用时 {time.time()-t0:.0f}s", flush=True)

    done = {o["id"] for o in ok1}
    missing = [it for it in items if it["id"] not in done]
    print(f"pass2 待重试 {len(missing)} 条", flush=True)
    ok2, bad2, rawlab2, st2 = [], {}, {}, []
    if missing:
        rb, notes = [], {}
        for i in range(0, len(missing), a.batch):
            chunk = missing[i:i+a.batch]
            bid = f"r{i//a.batch:04d}"
            rb.append((bid, chunk))
            notes[bid] = " | ".join(
                f"id={it['id']} -> " + (f"{bad1[it['id']]['layer']} {bad1[it['id']]['msg']}"
                                        if it["id"] in bad1 else "missing from your output")
                for it in chunk)[:12000]
        ok2, bad2, rawlab2, st2 = run_pool(rb, f"{ROOT}/raw/pass2", notes=notes, workers=a.workers)
        print(f"pass2 取回 {len(ok2)}/{len(missing)}", flush=True)

    out = {o["id"]: o for o in ok1}
    for o in ok2: out[o["id"]] = o
    for o in out.values(): o.setdefault("downgraded", False)

    rawlab = dict(rawlab1); rawlab.update(rawlab2)
    down = 0
    for it in items:
        if it["id"] in out: continue
        rl = rawlab.get(it["id"])
        b = bad2.get(it["id"]) or bad1.get(it["id"]) or {"layer": "L2", "msg": "no output"}
        out[it["id"]] = {"id": it["id"], "event_type": (rl or {}).get("event_type") or "other",
                         "direction": (rl or {}).get("direction") or "neutral",
                         "specificity": "rhetorical", "spec_raw": (rl or {}).get("specificity"),
                         "raw_evidence": (rl or {}).get("ev"), "fail_layer": b["layer"],
                         "fail_msg": b["msg"], "specificity_evidence": "", "tickers": [],
                         "countries": [], "sectors": [],
                         "dedup_key": {"topic": "unparsed", "direction": "neutral", "object": "unparsed"},
                         "quote_mode": "downgraded", "l5_strict": False, "l5_full": False,
                         "downgraded": True}
        down += 1
    print(f"pass3 降级 {down} 条", flush=True)

    os.makedirs(f"{ROOT}/out", exist_ok=True)
    with gzip.open(f"{ROOT}/out/m18_luna_full.json.gz", "wt") as f:
        json.dump([out[it["id"]] for it in items], f, ensure_ascii=False)
    meta = {"model": MODEL, "effort": EFFORT, "batch": a.batch, "workers": a.workers,
            "n": len(items), "pass1_ok": len(ok1), "pass2_ok": len(ok2), "downgraded": down,
            "secs": round(time.time()-t0, 1), "stats1": st1, "stats2": st2,
            "bad1_layers": {}, "bad2_layers": {}}
    from collections import Counter
    meta["bad1_layers"] = dict(Counter(v["layer"] for v in bad1.values()))
    meta["bad2_layers"] = dict(Counter(v["layer"] for v in bad2.values()))
    with open(f"{ROOT}/out/run_meta.json", "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("写出 out/m18_luna_full.json.gz", flush=True)


if __name__ == "__main__":
    main()
