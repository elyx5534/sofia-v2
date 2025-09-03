"""
Scanner engine for analyzing cryptocurrency signals across multiple symbols
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from loguru import logger

from ..data.pipeline import data_pipeline
from ..metrics.indicators import get_latest_indicators
from .rules import DEFAULT_RULES, ScanRule


class SignalScanner:
    """Main scanner class for analyzing cryptocurrency signals"""

    def __init__(self, rules: List[ScanRule] = None, outputs_dir: str = "./outputs"):
        self.rules = rules or DEFAULT_RULES.copy()
        self.outputs_dir = Path(outputs_dir)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

    def scan_symbol(self, symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
        """Scan a single symbol and return signal information"""
        try:
            df = data_pipeline.get_symbol_data(symbol, timeframe)
            if df.empty or len(df) < 50:
                return {"symbol": symbol, "score": 0, "signals": [], "error": "Insufficient data"}
            indicators = get_latest_indicators(df)
            if not indicators:
                return {
                    "symbol": symbol,
                    "score": 0,
                    "signals": [],
                    "error": "Failed to calculate indicators",
                }
            signals = []
            total_score = 0
            for rule in self.rules:
                try:
                    result = rule.evaluate(df, indicators)
                    if result["signal"] > 0:
                        signals.append(
                            {
                                "rule_name": rule.name,
                                "signal_strength": result["signal"],
                                "message": result["message"],
                                "details": {
                                    k: v
                                    for k, v in result.items()
                                    if k not in ["signal", "message"]
                                },
                            }
                        )
                        total_score += result["signal"]
                except Exception as e:
                    logger.warning(f"Rule {rule.name} failed for {symbol}: {e}")
            return {
                "symbol": symbol,
                "score": round(total_score, 2),
                "signals": signals,
                "indicators": indicators,
                "timestamp": datetime.now().isoformat(),
                "timeframe": timeframe,
            }
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return {"symbol": symbol, "score": 0, "signals": [], "error": str(e)}

    def scan_all_symbols(self, timeframe: str = "1h", max_workers: int = 4) -> List[Dict[str, Any]]:
        """Scan all available symbols"""
        available_symbols = data_pipeline.get_available_symbols()
        if not available_symbols:
            logger.warning("No symbols available for scanning")
            return []
        logger.info(f"Scanning {len(available_symbols)} symbols with {len(self.rules)} rules")
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {
                executor.submit(self.scan_symbol, symbol, timeframe): symbol
                for symbol in available_symbols
            }
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to scan {symbol}: {e}")
                    results.append({"symbol": symbol, "score": 0, "signals": [], "error": str(e)})
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        logger.info(f"Scan completed: {len(results)} symbols processed")
        return results

    def get_top_signals(
        self, results: List[Dict[str, Any]], limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get top signals with scores above threshold"""
        top_signals = []
        for result in results:
            if result.get("score", 0) > 0.5:
                top_signals.append(result)
            if len(top_signals) >= limit:
                break
        return top_signals

    def save_results(self, results: List[Dict[str, Any]], filename: str = None):
        """Save scan results to JSON and CSV files"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"scan_results_{timestamp}"
        json_path = self.outputs_dir / f"{filename}.json"
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        csv_path = self.outputs_dir / f"{filename}.csv"
        csv_data = []
        for result in results:
            row = {
                "symbol": result["symbol"],
                "score": result.get("score", 0),
                "timestamp": result.get("timestamp", ""),
                "timeframe": result.get("timeframe", "1h"),
                "error": result.get("error", ""),
                "signal_count": len(result.get("signals", [])),
                "signal_messages": " | ".join([s["message"] for s in result.get("signals", [])]),
                "current_price": result.get("indicators", {}).get("close", 0),
                "rsi": result.get("indicators", {}).get("rsi", 50),
                "price_change_24h": result.get("indicators", {}).get("price_change_24h", 0),
                "volume": result.get("indicators", {}).get("volume", 0),
            }
            csv_data.append(row)
        df = pd.DataFrame(csv_data)
        df.to_csv(csv_path, index=False)
        logger.info(f"Results saved to {json_path} and {csv_path}")

    def save_signals_json(self, results: List[Dict[str, Any]]):
        """Save top signals to signals.json for web interface"""
        top_signals = self.get_top_signals(results, limit=50)
        signals_path = self.outputs_dir / "signals.json"
        with open(signals_path, "w") as f:
            json.dump(top_signals, f, indent=2, default=str)
        csv_path = self.outputs_dir / "signals.csv"
        if top_signals:
            csv_data = []
            for result in top_signals:
                row = {
                    "symbol": result["symbol"],
                    "score": result.get("score", 0),
                    "signal_count": len(result.get("signals", [])),
                    "messages": " | ".join([s["message"] for s in result.get("signals", [])]),
                    "price": result.get("indicators", {}).get("close", 0),
                    "rsi": result.get("indicators", {}).get("rsi", 50),
                    "change_24h": result.get("indicators", {}).get("price_change_24h", 0),
                    "volume": result.get("indicators", {}).get("volume", 0),
                    "timestamp": result.get("timestamp", ""),
                }
                csv_data.append(row)
            df = pd.DataFrame(csv_data)
            df.to_csv(csv_path, index=False)
        logger.info(f"Signals saved to {signals_path} and {csv_path}")

    def run_scan(self, timeframe: str = "1h", save_results: bool = True) -> List[Dict[str, Any]]:
        """Run complete scan and optionally save results"""
        logger.info(f"Starting crypto scanner with {len(self.rules)} rules")
        results = self.scan_all_symbols(timeframe)
        total_symbols = len(results)
        symbols_with_signals = len([r for r in results if r.get("score", 0) > 0])
        top_score = max([r.get("score", 0) for r in results]) if results else 0
        logger.info(
            f"Scan summary: {total_symbols} symbols, {symbols_with_signals} with signals, top score: {top_score:.2f}"
        )
        if save_results:
            self.save_results(results)
            self.save_signals_json(results)
        return results


scanner = SignalScanner()
