# src/signals.py
from typing import Dict, Any, List

def compute_deltas(now: float, p24: float, p7: float):
    def pct(a, b):
        try:
            return (a - b) / b if b else 0.0
        except ZeroDivisionError:
            return 0.0
    return pct(now, p24), pct(now, p7)

def price_spike_signal(hist: Dict[str, float], last_n: List[float], cfg: Dict[str, Any]) -> (bool, Dict[str, Any]):
    p_now = hist.get("now", 0.0)
    p_24h = hist.get("24h_ago", 0.0)
    p_7d  = hist.get("7d_ago",  0.0)
    pct_24h, pct_7d = compute_deltas(p_now, p_24h, p_7d)
    breakout = False
    if last_n:
        breakout = p_now > max(last_n)
    ok = (pct_24h >= cfg["thresholds"]["pct_24h"] and
          pct_7d  >= cfg["thresholds"]["pct_7d"] and
          breakout)
    return ok, {"pct_24h": pct_24h, "pct_7d": pct_7d, "breakout": breakout}
