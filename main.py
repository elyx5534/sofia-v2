from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import pandas as pd
import yfinance as yf
from pathlib import Path

app = FastAPI(title="Sofia V2 API")

# templates klasörü
BASE_DIR = Path(__file__).parent
templates_dir = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/data")
def data(symbol: str = Query("BTC-USD")):
    """
    Son kapanış verisini ve son 30 kapanış listesini döndürür.
    İnternet yoksa temiz bir hata mesajı verir.
    """
    try:
        df = yf.download(symbol, period="31d", interval="1d", progress=False)
        if df.empty:
            return JSONResponse(status_code=404, content={"error": f"No data for {symbol}"})
        closes = df["Close"].dropna().tolist()
        return {
            "symbol": symbol,
            "last_close": float(closes[-1]),
            "closes": [float(x) for x in closes[-30:]],
            "count": len(closes)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/strategy")
def strategy(symbol: str = Query("BTC-USD"), short: int = 5, long: int = 20):
    """
    Basit SMA kesişimi sinyali (son bar için): buy/sell/hold
    """
    try:
        df = yf.download(symbol, period="120d", interval="1d", progress=False)
        if df.empty:
            return JSONResponse(status_code=404, content={"error": f"No data for {symbol}"})
        close = df["Close"].dropna()
        s = close.rolling(short).mean()
        l = close.rolling(long).mean()
        signal = "hold"
        if len(close) >= max(short, long):
            if s.iloc[-1] > l.iloc[-1] and s.iloc[-2] <= l.iloc[-2]:
                signal = "buy"
            elif s.iloc[-1] < l.iloc[-1] and s.iloc[-2] >= l.iloc[-2]:
                signal = "sell"
        return {"symbol": symbol, "short": short, "long": long, "signal": signal}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, symbol: str = "BTC-USD"):
    return templates.TemplateResponse("dashboard.html", {"request": request, "symbol": symbol})