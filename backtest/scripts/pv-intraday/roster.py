"""样本名册。抽子集的规则先写死再机械执行，不人工挑标的。"""
import csv, sys
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from load_intraday import symbols as fetched

UNIV = "/Users/ming/project/alva/backtest/universe/universe.csv"

def universe_rows():
    return list(csv.DictReader(open(UNIV)))

def full():
    have = set(fetched())
    us, cr = [], []
    for r in universe_rows():
        if r["symbol"] not in have: continue
        (cr if r["asset_class"] == "crypto" else us).append(r)
    return us, cr

def grid_subset(step_us=4, step_cr=3):
    """阈值扫描子集：按 universe.csv 原始行序（已按 部门 × 波动档 × 市值档 分层排列）
    每 step 只取一只。规则机械，不看结果。"""
    us, cr = full()
    return us[::step_us], cr[::step_cr]

if __name__ == "__main__":
    us, cr = full()
    gu, gc = grid_subset()
    print(f"已取数 美股 {len(us)}  加密 {len(cr)}")
    print(f"扫描子集 美股 {len(gu)}  加密 {len(gc)}")
    print("美股子集", ",".join(r["symbol"] for r in gu))
    print("加密子集", ",".join(r["symbol"] for r in gc))
