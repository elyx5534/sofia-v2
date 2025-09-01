-- Sofia V2 ClickHouse Schema
CREATE DATABASE IF NOT EXISTS sofia;

USE sofia;

-- Market ticks table
CREATE TABLE IF NOT EXISTS market_ticks
(
    ts DateTime64(3),
    symbol String,
    price Float64,
    volume Float64,
    bid Float64,
    ask Float64,
    src String DEFAULT 'binance'
) ENGINE = MergeTree()
ORDER BY (symbol, ts)
PARTITION BY toYYYYMM(ts)
TTL ts + INTERVAL 30 DAY;

-- 1-second OHLCV aggregation
CREATE TABLE IF NOT EXISTS ohlcv_1s
(
    ts DateTime,
    symbol String,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume Float64,
    trades UInt32
) ENGINE = MergeTree()
ORDER BY (symbol, ts)
PARTITION BY toYYYYMM(ts)
TTL ts + INTERVAL 90 DAY;

-- 1-minute OHLCV
CREATE TABLE IF NOT EXISTS ohlcv_1m
(
    ts DateTime,
    symbol String,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume Float64,
    trades UInt32
) ENGINE = MergeTree()
ORDER BY (symbol, ts)
PARTITION BY toYYYYMM(ts);

-- Paper trading orders
CREATE TABLE IF NOT EXISTS paper_orders
(
    order_id String,
    ts DateTime64(3),
    symbol String,
    side String,  -- 'buy' or 'sell'
    price Float64,
    quantity Float64,
    status String,  -- 'pending', 'filled', 'cancelled'
    strategy String,
    pnl Float64 DEFAULT 0
) ENGINE = MergeTree()
ORDER BY (ts, order_id)
PARTITION BY toYYYYMM(ts);

-- Strategy signals
CREATE TABLE IF NOT EXISTS strategy_signals
(
    ts DateTime64(3),
    symbol String,
    strategy String,
    signal String,  -- 'buy', 'sell', 'hold'
    strength Float64,
    meta String  -- JSON metadata
) ENGINE = MergeTree()
ORDER BY (symbol, strategy, ts)
PARTITION BY toYYYYMM(ts)
TTL ts + INTERVAL 7 DAY;

-- Performance metrics
CREATE TABLE IF NOT EXISTS performance_metrics
(
    ts DateTime,
    strategy String,
    symbol String,
    total_trades UInt32,
    win_rate Float64,
    sharpe_ratio Float64,
    max_drawdown Float64,
    total_pnl Float64,
    realized_pnl Float64,
    unrealized_pnl Float64
) ENGINE = MergeTree()
ORDER BY (strategy, symbol, ts)
PARTITION BY toYYYYMM(ts);

-- Materialized view for 1s OHLCV from ticks
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ohlcv_1s
ENGINE = MergeTree()
ORDER BY (symbol, ts)
AS
SELECT
    toStartOfSecond(ts) AS ts,
    symbol,
    argMin(price, ts) AS open,
    max(price) AS high,
    min(price) AS low,
    argMax(price, ts) AS close,
    sum(volume) AS volume,
    count() AS trades
FROM market_ticks
GROUP BY symbol, toStartOfSecond(ts);

-- Materialized view for 1m OHLCV from 1s
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ohlcv_1m
ENGINE = MergeTree()
ORDER BY (symbol, ts)
AS
SELECT
    toStartOfMinute(ts) AS ts,
    symbol,
    argMin(open, ts) AS open,
    max(high) AS high,
    min(low) AS low,
    argMax(close, ts) AS close,
    sum(volume) AS volume,
    sum(trades) AS trades
FROM ohlcv_1s
GROUP BY symbol, toStartOfMinute(ts);