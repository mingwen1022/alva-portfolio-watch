# M24 宏观传导词表 · 三组。写法：(模式, 是否大小写敏感)
# 大小写敏感用于缩写，防止 QE/QT/Fed 命中普通词
MONETARY = [
    (r"rate hikes?", 0), (r"rate cuts?", 0), (r"raise rates?", 0), (r"cut rates?", 0),
    (r"lower rates?", 0), (r"hiking rates?", 0), (r"rate decision", 0), (r"interest rates?", 0),
    (r"basis points?", 0), (r"\bbps\b", 0), (r"quantitative (easing|tightening)", 0),
    (r"\bQE\b", 1), (r"\bQT\b", 1), (r"balance sheet runoff", 0), (r"\bFOMC\b", 1),
    (r"\bFed\b", 1), (r"Federal Reserve", 0), (r"Powell", 0), (r"central bank", 0),
    (r"\bECB\b", 1), (r"\bBOJ\b", 1), (r"\bPBOC\b", 1),
    (r"reverse repo", 0), (r"repo (market|rates?|operations?|facility)", 0), (r"\bRRP\b", 1), (r"discount window", 0), (r"\bSOFR\b", 1),
    (r"yield curve", 0), (r"curve inversion", 0), (r"monetary (policy|easing|tightening)", 0),
    (r"liquidity (injection|crunch|squeeze|drain)", 0), (r"dot plot", 0),
]
GEOPOLITICAL = [
    (r"Strait of Hormuz", 0), (r"\bHormuz\b", 0), (r"Suez", 0), (r"Panama Canal", 0),
    (r"Taiwan Strait", 0), (r"Red Sea", 0), (r"Bab el-?Mandeb", 0), (r"Malacca", 0),
    (r"choke ?point", 0), (r"blockade", 0), (r"embargo", 0),
    (r"rare earths?", 0), (r"critical minerals?", 0),
    (r"\bwar\b", 0), (r"warfare", 0), (r"invasion", 0), (r"invade", 0),
    (r"military strike", 0), (r"air ?strike", 0), (r"missile", 0),
    (r"sanctions?", 0), (r"\bOPEC\b", 1), (r"oil embargo", 0),
    (r"export ban", 0), (r"import ban", 0), (r"shipping (rates?|disruption)", 0),
    (r"freight rates?", 0), (r"supply chain (disruption|shock)", 0),
]
FISCAL = [
    (r"debt ceiling", 0), (r"government shutdown", 0), (r"continuing resolution", 0),
    (r"stimulus", 0), (r"fiscal (package|stimulus|policy)", 0), (r"spending bill", 0),
    (r"(budget|fiscal|trade) deficit", 0), (r"deficit spending", 0),
    (r"bond auction", 0), (r"Treasury (buyback|issuance|refunding|auction)", 0),
    (r"debt (downgrade|rating)", 0), (r"credit rating", 0),
    (r"Moody'?s", 0), (r"\bFitch\b", 0),
    (r"tax (cuts?|hikes?|increase)", 0),
]
GROUPS = {"货币流动性": MONETARY, "地缘供应链": GEOPOLITICAL, "财政": FISCAL}
