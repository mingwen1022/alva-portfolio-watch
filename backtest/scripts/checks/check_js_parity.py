# -*- coding: utf-8 -*-
"""Python 参考实现与交付用的 JS 实现必须给出同一个数。

⚠️ 存在理由：阈值 1.5 / 2.0 / 3.0 和判据是在 `pipeline/*.py` 上验出来的，
   而线上跑的是 `skill/scripts/lib.js`（Alva 只有 V8，没有 Python）。
   两份实现只要有一处口径不同 —— MAD 用样本还是总体、窗口含不含当日、
   简单还是对数收益 —— 就会让「今天该不该响」在边界上换个答案，
   而且不会报错。这个检查是那条边界上唯一的守卫。
"""
import json, os, subprocess, statistics as st, tempfile, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..')
_RAWP = os.path.join(ROOT, 'pipeline/raw/daily.json')
# ⚠️ 原始数据按设计不进 git（54 MB，含第三方帖子全文）。缺它时干净跳过，
#    退出码 2 与「失败」的 1 区分开 —— 交付仓库里跑这条命令曾经直接
#    FileNotFoundError 崩掉，而 README 正让评审跑它。
#    「没跑到」必须和「跑完没发现」长得不一样，崩溃和通过都不是它。
if not os.path.exists(_RAWP):
    print('—  Python/JS 口径检查跳过：缺 pipeline/raw/daily.json（原始数据不进仓库，'
          '按 backtest/data-sources.md 重取后可跑）')
    sys.exit(2)
RAW  = json.load(open(_RAWP))['daily']
LIB  = os.path.join(ROOT, 'skill/scripts/lib.js')
W    = 90
TOL  = 1e-12          # 同一套浮点运算，允许的只有表示误差

def series(sym):
    rows = sorted(tuple(l.split(',')) for l in RAW[sym].splitlines())
    return [float(r[4]) for r in rows], [float(r[5]) for r in rows]

def py_reading(c, v):
    r = [c[i] / c[i - 1] - 1 for i in range(1, len(c))]
    if len(r) < W + 1: return None
    win = r[-1 - W:-1]
    med = st.median(win)
    sig = 1.4826 * st.median([abs(x - med) for x in win])
    vmed = st.median(v[-1 - W:-1])
    if not (sig > 0 and vmed > 0): return None
    return {"move": r[-1], "z": (r[-1] - med) / sig, "rvol": v[-1] / vmed, "sigma": sig}

syms = sorted(RAW)
data = {s: dict(zip(("c", "v"), series(s))) for s in syms}

with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
    json.dump(data, f); dpath = f.name
with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
    f.write(f"""
const L=require({json.dumps(LIB)});
const d=require({json.dumps(dpath)});
const out={{}};
for (const s of Object.keys(d)) {{
  const r=L.reading(d[s].c, d[s].v, {W});
  out[s]= r && {{move:r.move, z:r.z, rvol:r.rvol, sigma:r.sigma}};
}}
console.log(JSON.stringify(out));
"""); jpath = f.name

r = subprocess.run(['node', jpath], capture_output=True, text=True)
os.unlink(dpath); os.unlink(jpath)
if r.returncode:
    print('❌ JS 实现跑不起来：'); print(r.stderr[:600]); raise SystemExit(1)
js = json.loads(r.stdout)

bad = []
for s in syms:
    p, j = py_reading(*series(s)), js.get(s)
    if (p is None) != (j is None):
        bad.append(f'{s}: 一边算得出、一边算不出（py={p is not None} js={j is not None}）'); continue
    if p is None: continue
    for k in ('move', 'z', 'rvol', 'sigma'):
        if abs(p[k] - j[k]) > TOL:
            bad.append(f'{s}.{k}: py={p[k]!r} js={j[k]!r} 差 {abs(p[k]-j[k]):.3e}')

if bad:
    print(f'❌ Python 与 JS 口径不一致（{len(bad)} 处）：')
    [print('  ', b) for b in bad]
    raise SystemExit(1)
print(f'✅ Python / JS 口径一致（{len(syms)} 只标的 × 4 个量，逐位相同）')
