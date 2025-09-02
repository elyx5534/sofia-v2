import pathlib
from typing import Dict, List

import pandas as pd
import requests
import yfinance as yf

ARTIFACTS = pathlib.Path("artifacts")
ARTIFACTS.mkdir(exist_ok=True)


def fetch_symbol(symbol: str, period="1y", interval="1d"):
    """Fetch symbol data using yfinance"""
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        raise ValueError("empty yfinance")
    df.index = pd.to_datetime(df.index)
    return df


def fetch_news(symbol: str, limit: int = 8) -> List[Dict]:
    """Fetch news from Yahoo RSS with fallback"""
    try:
        q = symbol.replace(":", "-").replace("/", "-")
        url = f"https://finance.yahoo.com/rss/headline?s={q}"
        r = requests.get(url, timeout=5)
        r.raise_for_status()

        import xml.etree.ElementTree as ET

        root = ET.fromstring(r.text)
        items = []

        for item in root.findall(".//item")[:limit]:
            items.append(
                {
                    "title": (item.findtext("title") or "").strip(),
                    "link": (item.findtext("link") or "").strip(),
                }
            )

        return items or [{"title": "Haber bulunamadı", "link": "#"}]

    except Exception:
        return [{"title": "Haber kaynağı geçici olarak kullanılamıyor.", "link": "#"}]
