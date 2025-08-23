from typing import List, Dict

def run_dummy_backtest(prices: List[float]) -> Dict[str, float]:
    """Basit ve deterministik metrikler: toplam getiri, işlem sayısı, kazanma oranı."""
    if not prices or len(prices) < 2:
        return {"trades": 0, "win_rate": 0.0, "total_return": 0.0}
    changes = []
    for i in range(1, len(prices)):
        changes.append((prices[i] - prices[i-1]) / prices[i-1])
    wins = sum(1 for c in changes if c > 0)
    total_ret = 1.0
    for c in changes:
        total_ret *= (1 + c)
    total_ret -= 1.0
    return {
        "trades": len(changes),
        "win_rate": wins / len(changes),
        "total_return": total_ret
    }

def sma_signals(prices: List[float], short: int = 3, long: int = 5) -> List[str]:
    """SMA kesişimi tabanlı sinyal listesi: buy/sell/hold."""
    n = len(prices)
    if n == 0:
        return []
    signals = ["hold"] * n
    def ma(seq, w, i):
        if i+1 < w: return None
        return sum(seq[i-w+1:i+1]) / w
    for i in range(n):
        s = ma(prices, short, i)
        l = ma(prices, long, i)
        if s is None or l is None:
            continue
        if s > l and ma(prices, short, i-1) <= ma(prices, long, i-1):
            signals[i] = "buy"
        elif s < l and ma(prices, short, i-1) >= ma(prices, long, i-1):
            signals[i] = "sell"
    return signals