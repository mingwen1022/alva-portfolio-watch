# -*- coding: utf-8 -*-
"""把某个 profile 写成一次性配置里的 default。
被 newrun.sh 调用 —— 从前它是内联 heredoc，而 newrun.sh 自己也用 <<'PY'，
两层终止符撞在一起，外层 shell 解析都过不了。拆出来当文件。"""
import json, os, sys
cfg, want = sys.argv[1], sys.argv[2]
src = json.load(open(os.path.expanduser("~/.config/alva/config.json")))
acct = (src.get("profiles") or {}).get(want)
if not acct:
    sys.exit(f"\u274c ~/.config/alva/config.json 里没有 {want} profile")
json.dump({"profiles": {"default": acct}}, open(cfg, "w"))
os.chmod(cfg, 0o600)
