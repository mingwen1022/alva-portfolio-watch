import json, sys, numpy as np
for f, tag in (('derived/crit_nollm.json', 'offset=0 窗=帖后0-75min'),
               ('derived/crit_conf_off2.json', 'offset=2 窗=帖后30-105min')):
    try:
        d = json.load(open(f))
    except FileNotFoundError:
        continue
    print(f'\n=== {f}  ({tag}) ===')
    for name, v in d.items():
        for asset in ('us_equity', 'crypto'):
            o = [x for x in v['obs'] if x['asset'] == asset]
            if not o:
                continue
            nd = v['null'].get(f'{asset}|day', [])
            npo = v['null'].get(f'{asset}|pos', [])
            pl = [x for x in v['placebo'] if x['asset'] == asset]
            m = lambda a: (np.mean([x['passrate'] for x in a]) if a else float('nan'))
            g = lambda a: (np.percentile([x['passrate'] for x in a], 95) if a else float('nan'))
            pls = " ".join("k={0}:{1:.0%}".format(x['k'], x['passrate']) for x in pl)
            print("{0:26} {1:9} 触发{2:>6.0f} 通过{3:>6.1%} 倍数{4:.3f} | 零-日{5:>6.1%}(P95{6:>5.1%}) 零-位置{7:>6.1%}(P95{8:>5.1%}) | 安慰剂 {9}".format(
                name, asset, np.median([x['n'] for x in o]), np.mean([x['pass_'] for x in o]),
                np.median([x['mult'] for x in o]), m(nd), g(nd), m(npo), g(npo), pls))
