"""
Incident Snapshot - Collect evidence on trigger
Captures all relevant data when emergency stop is triggered
"""

import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IncidentSnapshot:
    """Collect incident evidence"""
    
    def __init__(self):
        self.signal_file = Path("logs/incident_signal.json")
        self.timestamp = datetime.now()
        self.snapshot_dir = None
        
    def check_signal(self) -> Optional[Dict]:
        """Check if snapshot signal exists"""
        if not self.signal_file.exists():
            return None
        
        try:
            with open(self.signal_file, 'r') as f:
                signal = json.load(f)
                
                # Check if pending
                if signal.get("status") == "PENDING":
                    return signal
        except Exception as e:
            logger.error(f"Failed to read signal: {e}")
        
        return None
    
    def create_snapshot_dir(self) -> Path:
        """Create timestamped snapshot directory"""
        timestamp_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
        self.snapshot_dir = Path(f"reports/incidents/{timestamp_str}")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Snapshot directory: {self.snapshot_dir}")
        return self.snapshot_dir
    
    def collect_logs(self) -> Dict:
        """Collect logs from last hour"""
        collected = {"files": [], "lines": 0}
        
        # Define log files to collect
        log_patterns = [
            "logs/*.json",
            "logs/*.jsonl",
            "logs/*.log",
            "logs/pilot_*.json",
            "logs/anomalies.json",
            "reports/reconciliation.json"
        ]
        
        logs_dir = self.snapshot_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        for pattern in log_patterns:
            for file_path in Path(".").glob(pattern):
                if file_path.exists():
                    try:
                        # Check if file modified in last 24 hours
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if (self.timestamp - mtime) < timedelta(hours=24):
                            dest = logs_dir / file_path.name
                            shutil.copy2(file_path, dest)
                            collected["files"].append(str(file_path))
                            
                            # Count lines
                            if file_path.suffix in [".json", ".jsonl", ".log"]:
                                with open(file_path, 'r') as f:
                                    collected["lines"] += sum(1 for _ in f)
                    except Exception as e:
                        logger.error(f"Failed to copy {file_path}: {e}")
        
        logger.info(f"Collected {len(collected['files'])} log files")
        return collected
    
    def extract_last_hour_trades(self) -> List[Dict]:
        """Extract trades from last hour"""
        trades = []
        trades_file = Path("logs/pilot_trades.json")
        
        if trades_file.exists():
            try:
                with open(trades_file, 'r') as f:
                    all_trades = json.load(f)
                    
                    # Filter last hour
                    cutoff = self.timestamp - timedelta(hours=1)
                    
                    for trade in all_trades:
                        trade_time = datetime.fromisoformat(trade.get("timestamp", ""))
                        if trade_time > cutoff:
                            trades.append(trade)
                            
            except Exception as e:
                logger.error(f"Failed to extract trades: {e}")
        
        # Save to snapshot
        if trades:
            trades_file = self.snapshot_dir / "last_hour_trades.json"
            with open(trades_file, 'w') as f:
                json.dump(trades, f, indent=2)
        
        logger.info(f"Extracted {len(trades)} trades from last hour")
        return trades
    
    def get_pnl_summary(self) -> Dict:
        """Get current P&L summary"""
        summary = {
            "timestamp": self.timestamp.isoformat(),
            "net_pnl_tl": 0,
            "gross_pnl_tl": 0,
            "fees_tl": 0,
            "tax_tl": 0,
            "trades_count": 0,
            "win_rate": 0
        }
        
        # Read from telemetry
        telemetry_file = Path("logs/pilot_telemetry.json")
        if telemetry_file.exists():
            try:
                with open(telemetry_file, 'r') as f:
                    data = json.load(f)
                    
                    # Get latest P&L
                    if data.get("current"):
                        pnl = data["current"].get("tl_pnl_live", {})
                        summary["net_pnl_tl"] = pnl.get("net_tl", 0)
                        summary["gross_pnl_tl"] = pnl.get("gross_tl", 0)
                        summary["fees_tl"] = pnl.get("fees_tl", 0)
                        summary["tax_tl"] = pnl.get("tax_tl", 0)
                    
                    # Count trades
                    history = data.get("history", [])
                    if history:
                        positions = sum(h.get("active_positions", 0) for h in history)
                        summary["trades_count"] = positions
                        
                        # Calculate win rate (mock)
                        positive = sum(1 for h in history 
                                     if h.get("tl_pnl_live", {}).get("net_tl", 0) > 0)
                        if history:
                            summary["win_rate"] = round((positive / len(history)) * 100, 1)
                            
            except Exception as e:
                logger.error(f"Failed to get P&L summary: {e}")
        
        # Save summary
        summary_file = self.snapshot_dir / "pnl_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary
    
    def get_open_orders(self) -> List[Dict]:
        """Get all open orders"""
        orders = []
        
        # Mock open orders - in production, query exchange
        orders_file = Path("logs/open_orders.json")
        if orders_file.exists():
            try:
                with open(orders_file, 'r') as f:
                    orders = json.load(f)
            except:
                pass
        
        # If no file, create mock data
        if not orders:
            orders = [
                {
                    "order_id": "mock_001",
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "price": 42000,
                    "size": 0.001,
                    "status": "OPEN",
                    "timestamp": self.timestamp.isoformat()
                }
            ]
        
        # Save to snapshot
        orders_file = self.snapshot_dir / "open_orders.json"
        with open(orders_file, 'w') as f:
            json.dump(orders, f, indent=2)
        
        logger.info(f"Found {len(orders)} open orders")
        return orders
    
    def run_network_diagnostics(self) -> Dict:
        """Run network ping tests"""
        diagnostics = {
            "timestamp": self.timestamp.isoformat(),
            "pings": {}
        }
        
        # Endpoints to test
        endpoints = [
            ("8.8.8.8", "Google DNS"),
            ("1.1.1.1", "Cloudflare DNS"),
            ("api.binance.com", "Binance API"),
            ("api.coingecko.com", "CoinGecko API")
        ]
        
        for host, name in endpoints:
            try:
                # Windows ping command
                result = subprocess.run(
                    ["ping", "-n", "4", host],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                # Parse output
                if "Average" in result.stdout:
                    # Extract average time
                    for line in result.stdout.split('\n'):
                        if "Average" in line:
                            avg_time = line.split("Average = ")[-1].strip()
                            diagnostics["pings"][name] = {
                                "host": host,
                                "status": "OK",
                                "avg_time": avg_time
                            }
                            break
                else:
                    diagnostics["pings"][name] = {
                        "host": host,
                        "status": "TIMEOUT",
                        "error": "No response"
                    }
                    
            except Exception as e:
                diagnostics["pings"][name] = {
                    "host": host,
                    "status": "ERROR",
                    "error": str(e)
                }
        
        # Save diagnostics
        diag_file = self.snapshot_dir / "network_diagnostics.json"
        with open(diag_file, 'w') as f:
            json.dump(diagnostics, f, indent=2)
        
        return diagnostics
    
    def capture_config_state(self) -> Dict:
        """Capture current configuration state"""
        configs = {}
        
        config_files = [
            "config/live.yaml",
            "config/approvals.json",
            "api/live_guard.json"
        ]
        
        config_dir = self.snapshot_dir / "config"
        config_dir.mkdir(exist_ok=True)
        
        for config_path in config_files:
            file_path = Path(config_path)
            if file_path.exists():
                try:
                    dest = config_dir / file_path.name
                    shutil.copy2(file_path, dest)
                    configs[config_path] = "Captured"
                except Exception as e:
                    configs[config_path] = f"Error: {e}"
            else:
                configs[config_path] = "Not found"
        
        return configs
    
    def generate_incident_report(self, data: Dict) -> str:
        """Generate incident report"""
        lines = [
            f"# Incident Report - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Trigger Information",
            f"- **Trigger Time**: {data['trigger']['timestamp']}",
            f"- **Trigger Type**: {', '.join(data['trigger'].get('reasons', ['Unknown']))}",
            f"- **Auto-triggered**: Yes",
            "",
            "## System State at Incident",
            "",
            "### P&L Summary",
            f"- Net P&L: {data['pnl']['net_pnl_tl']:.2f} TL",
            f"- Gross P&L: {data['pnl']['gross_pnl_tl']:.2f} TL",
            f"- Fees: {data['pnl']['fees_tl']:.2f} TL",
            f"- Tax: {data['pnl']['tax_tl']:.2f} TL",
            f"- Win Rate: {data['pnl']['win_rate']:.1f}%",
            "",
            "### Open Positions",
            f"- Open Orders: {len(data['open_orders'])}",
            f"- Last Hour Trades: {len(data['last_hour_trades'])}",
            "",
            "### Network Status"
        ]
        
        # Add network diagnostics
        for name, ping in data['network']['pings'].items():
            status = "✅" if ping['status'] == "OK" else "❌"
            lines.append(f"- {name}: {status} {ping.get('avg_time', ping.get('error', 'Unknown'))}")
        
        lines.extend([
            "",
            "## Evidence Collected",
            f"- Log Files: {len(data['logs']['files'])}",
            f"- Log Lines: {data['logs']['lines']}",
            f"- Config Files: {len(data['configs'])}",
            "",
            "## Files in Snapshot",
            f"- `{self.snapshot_dir}/`",
            f"  - `logs/` - All recent log files",
            f"  - `config/` - Configuration state",
            f"  - `pnl_summary.json` - P&L at incident",
            f"  - `open_orders.json` - Open orders",
            f"  - `last_hour_trades.json` - Recent trades",
            f"  - `network_diagnostics.json` - Network state",
            f"  - `incident_data.json` - Complete data",
            "",
            "## Next Steps",
            "1. Review trigger cause in logs",
            "2. Check network diagnostics for connectivity issues",
            "3. Analyze P&L and trades for anomalies",
            "4. Verify all positions are closed",
            "5. Fix root cause before re-enabling",
            "",
            "---",
            "*Generated by incident_snapshot.py*"
        ])
        
        return "\n".join(lines)
    
    def collect_snapshot(self, trigger_data: Optional[Dict] = None) -> Dict:
        """Main snapshot collection"""
        
        # Create snapshot directory
        self.create_snapshot_dir()
        
        logger.info("="*60)
        logger.info(" COLLECTING INCIDENT SNAPSHOT")
        logger.info("="*60)
        
        # Collect all data
        data = {
            "timestamp": self.timestamp.isoformat(),
            "snapshot_dir": str(self.snapshot_dir),
            "trigger": trigger_data or {"reasons": ["Manual"], "timestamp": self.timestamp.isoformat()},
            "logs": self.collect_logs(),
            "pnl": self.get_pnl_summary(),
            "open_orders": self.get_open_orders(),
            "last_hour_trades": self.extract_last_hour_trades(),
            "network": self.run_network_diagnostics(),
            "configs": self.capture_config_state()
        }
        
        # Save complete data
        data_file = self.snapshot_dir / "incident_data.json"
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Generate report
        report = self.generate_incident_report(data)
        report_file = self.snapshot_dir / "incident_report.md"
        report_file.write_text(report)
        
        # Update signal status
        if self.signal_file.exists():
            try:
                with open(self.signal_file, 'r') as f:
                    signal = json.load(f)
                
                signal["status"] = "COMPLETED"
                signal["snapshot_dir"] = str(self.snapshot_dir)
                signal["completed_at"] = datetime.now().isoformat()
                
                with open(self.signal_file, 'w') as f:
                    json.dump(signal, f, indent=2)
            except:
                pass
        
        logger.info("="*60)
        logger.info(" SNAPSHOT COMPLETE")
        logger.info("="*60)
        logger.info(f"Directory: {self.snapshot_dir}")
        logger.info(f"Files collected: {len(data['logs']['files'])}")
        logger.info(f"Open orders: {len(data['open_orders'])}")
        logger.info(f"Last hour trades: {len(data['last_hour_trades'])}")
        logger.info("="*60)
        
        return data
    
    def auto_collect(self) -> Optional[Dict]:
        """Auto-collect if signal exists"""
        signal = self.check_signal()
        
        if signal:
            logger.info("Incident signal detected - collecting snapshot")
            trigger_data = signal.get("triggers", {})
            return self.collect_snapshot(trigger_data)
        else:
            logger.info("No pending incident signal")
            return None


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Incident snapshot collector")
    parser.add_argument("--manual", action="store_true",
                       help="Force manual snapshot")
    parser.add_argument("--auto", action="store_true",
                       help="Check for auto-trigger signal")
    
    args = parser.parse_args()
    
    snapshot = IncidentSnapshot()
    
    if args.manual:
        print("\nManual snapshot collection...")
        data = snapshot.collect_snapshot()
        print(f"\n✅ Snapshot saved to: {snapshot.snapshot_dir}")
        
    elif args.auto:
        print("\nChecking for incident signal...")
        data = snapshot.auto_collect()
        if data:
            print(f"\n✅ Snapshot saved to: {snapshot.snapshot_dir}")
        else:
            print("\n✅ No incident signal found")
    else:
        # Default: check signal
        signal = snapshot.check_signal()
        if signal:
            print("\n⚠️ INCIDENT SIGNAL DETECTED")
            print(f"Triggers: {signal.get('triggers', {}).get('reasons', ['Unknown'])}")
            print("\nCollecting snapshot...")
            data = snapshot.collect_snapshot(signal.get("triggers"))
            print(f"\n✅ Snapshot saved to: {snapshot.snapshot_dir}")
        else:
            print("\nNo incident signal found.")
            print("\nUsage:")
            print("  --manual  : Force manual snapshot")
            print("  --auto    : Check for auto-trigger signal")


if __name__ == "__main__":
    main()