import os, sys, json, gzip, time, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m18lib as L

CAND = "/Users/ming/project/alva/backtest/data/po-derived/candidates.json.gz"
S = os.environ["S"]
SCH = f"{S}/porun2/scripts/schema.json"

cands = json.load(gzip.open(CAND))
n = int(sys.argv[1]); effort = sys.argv[2]; off = int(sys.argv[3]) if len(sys.argv)>3 else 0
items = [{"id": c["cid"], "text": c["text"]} for c in cands[off:off+n]]
prompt = L.build_prompt(items)
d = tempfile.mkdtemp(prefix="cx")
outf = os.path.join(d, "out.json")
t0 = time.time()
cmd = ["codex","exec","-m","gpt-5.6-luna","--skip-git-repo-check","--ephemeral",
       "-s","read-only","-C",d,"--output-schema",SCH,"-o",outf,
       "-c",f'model_reasoning_effort="{effort}"',"--color","never",prompt]
p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
dt = time.time()-t0
raw = open(outf).read() if os.path.exists(outf) else ""
s, fenced = L.strip_fence(raw)
try: obj = json.loads(s)
except Exception as e: obj=None; print("PARSE FAIL", e); print(raw[:800])
arr = L.coerce_array(obj) if obj is not None else None
v = L.validate(items, arr) if arr is not None else None
print(f"n={n} effort={effort} rc={p.returncode} secs={dt:.1f} ({dt/n:.1f}/条) fenced={fenced}")
if v: print("  first-pass ok", len(v["ok"]), "/", n, " layer_hits", v["layer_hits"])
if v and v["errs"]: print("  errs:", v["errs"][:5])
if v: 
    from collections import Counter
    print("  spec", Counter(o["specificity"] for o in v["ok"]), " qmode", Counter(o["quote_mode"] for o in v["ok"]))
print("  stderr tail:", (p.stderr or "")[-300:].replace("\n"," | "))
