from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sofia_backtest.engine import sma_cross_backtest
from sofia_datahub.pipeline import fetch_news, fetch_symbol
from sofia_registry.store import add_run, list_recent_runs

BASE = Path(__file__).parent
templates_dir = BASE / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape())

app = FastAPI(title="Sofia V2")
app.mount("/artifacts", StaticFiles(directory="artifacts"), name="artifacts")


def render(tpl, **ctx):
    template = env.get_template(tpl)
    return HTMLResponse(template.render(**ctx))


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return render("index_simple.html", request=request)


@app.get("/showcase/{symbol}", response_class=HTMLResponse)
def showcase(request: Request, symbol: str):
    try:
        df = fetch_symbol(symbol)
        news = fetch_news(symbol)
        return render(
            "showcase_simple.html",
            request=request,
            symbol=symbol,
            news=news,
            last_close=float(df["Close"].iloc[-1]),
        )
    except Exception as e:
        return HTMLResponse(f"<h1>Error: {e!s}</h1><p><a href='/'>Back to Home</a></p>")


@app.get("/cards", response_class=HTMLResponse)
def cards(request: Request):
    runs = list_recent_runs(12)
    return render("cards_simple.html", request=request, runs=runs)


@app.get("/api/backtest/{symbol}")
def api_backtest(symbol: str, fast: int = 10, slow: int = 20):
    df = fetch_symbol(symbol)
    res = sma_cross_backtest(df, fast=fast, slow=slow)
    add_run(
        symbol,
        "sma_cross",
        {"fast": fast, "slow": slow},
        res["pnl"],
        res["sharpe"],
        res["artifact"],
    )
    return res


@app.get("/health")
def health():
    return {"ok": True}
