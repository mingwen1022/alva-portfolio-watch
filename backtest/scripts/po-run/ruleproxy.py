"""纯规则的 specificity 代理 —— 用来回答「LLM 有没有增量」。

两个版本：
  rule_loose   registry M18 的四条判据直接套在全文上（数值/日期 · 生效时点 · 点名持仓公司 · 已完成动作）
  rule_tight   results-phase3-po §1.2 试过的那条：数值与政策工具词在 ±60 字符内共现
"""
import re

RE_NUM = re.compile(r"\d")
RE_PCT = re.compile(r"\d+(\.\d+)?\s?(%|percent|bps|basis points?)", re.I)
RE_MON = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I)
RE_EFF = re.compile(r"\b(effective|effective immediately|starting|begins|beginning|as of|takes effect|deadline|no later than|by the end of)\b", re.I)
RE_CO = re.compile(r"\b(NVDA|AMD|MSFT|Nvidia|Microsoft)\b")
RE_DONE = re.compile(r"\b(signed|approved|revoked|imposed|sanctioned|banned|enacted|issued|announced|filed|published|passed|ratified|terminated|suspended|lifted|granted|denied|finalized|rescinded)\b", re.I)
RE_TOOL = re.compile(r"\b(tariffs?|duty|duties|quota|export controls?|sanctions?|rates?|tax|levy|ban|licen[cs]e|subsid(y|ies)|price cap)\b", re.I)
RE_INTENT = re.compile(r"\b(considering|may|might|could|plans? to|will (be )?(consider|look|seek)|intends?|proposes?|urges?|calls? for|should)\b", re.I)


def rule_loose(t):
    return bool(RE_NUM.search(t) or RE_MON.search(t) or RE_EFF.search(t)
                or RE_CO.search(t) or RE_DONE.search(t))


def rule_tight(t, win=60):
    for m in RE_PCT.finditer(t):
        a, b = max(0, m.start() - win), min(len(t), m.end() + win)
        if RE_TOOL.search(t[a:b]):
            return True
    for m in re.finditer(r"\$\s?\d[\d,\.]*\s?(billion|million|trillion|bn|mn)?", t, re.I):
        a, b = max(0, m.start() - win), min(len(t), m.end() + win)
        if RE_TOOL.search(t[a:b]):
            return True
    return False


RE_ANCHOR = re.compile(r"\b(tariffs?|duty|duties|quota|export controls?|sanctions?|rate|rates|tax|taxes|levy|ban|licen[cs]e|subsid(y|ies)|price cap|deal|agreement|order|rule|regulation|bill|act|investment|fund(ing)?|contract|GDP|inflation|deficit|budget)\b", re.I)
RE_UNIT = re.compile(r"(\d+(\.\d+)?\s?(%|percent|bps|basis points?)|\$\s?\d[\d,\.]*|\b\d[\d,\.]*\s?(billion|million|trillion|bn|mn)\b|\b(19|20)\d{2}\b|\b\d{1,2}\s?(st|nd|rd|th)?\s?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b)", re.I)


def rule_mid(t, win=80):
    """中间档：数量/金额/日期 与 政策名词 在 ±win 字符内共现，或含生效时点，或点名持仓公司。
    比 rule_tight 宽（锚词表更大），比 rule3 严（要求共现，不是全文任意有数字）。"""
    if RE_EFF.search(t) or RE_CO.search(t):
        return True
    for m in RE_UNIT.finditer(t):
        a, b = max(0, m.start() - win), min(len(t), m.end() + win)
        if RE_ANCHOR.search(t[a:b]):
            return True
    return False
