import sqlite3
import pathlib
import json
import time

DB = pathlib.Path("artifacts") / "runs.db"
DB.parent.mkdir(exist_ok=True)

def _init():
    """Initialize database schema"""
    with sqlite3.connect(DB) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            strategy TEXT,
            params TEXT,
            pnl REAL,
            sharpe REAL,
            artifact TEXT,
            created_at INTEGER
        )""")

_init()

def add_run(symbol, strategy, params, pnl, sharpe, artifact):
    """Add a new backtest run to the database"""
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO runs(symbol,strategy,params,pnl,sharpe,artifact,created_at) VALUES (?,?,?,?,?,?,?)",
            (symbol, strategy, json.dumps(params), pnl, sharpe, artifact, int(time.time()))
        )

def list_recent_runs(n=12):
    """List recent backtest runs"""
    with sqlite3.connect(DB) as con:
        cur = con.execute(
            "SELECT id,symbol,strategy,params,pnl,sharpe,artifact,created_at FROM runs ORDER BY created_at DESC LIMIT ?",
            (n,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]