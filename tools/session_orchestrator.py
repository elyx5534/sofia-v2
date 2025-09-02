"""
Daily Session Orchestrator
Runs grid and arbitrage sessions sequentially, generates scorecard
"""

import sys
import json
import asyncio
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))


class SessionOrchestrator:
    """Orchestrate daily trading sessions"""
    
    def __init__(self, grid_mins: int = 60, arb_mins: int = 30):
        self.grid_mins = grid_mins
        self.arb_mins = arb_mins
        self.results = {}
        self.start_time = None
        
    def run_grid_session(self) -> Dict:
        """Run grid trading session"""
        print("=" * 60)
        print(f"STARTING GRID SESSION ({self.grid_mins} minutes)")
        print("=" * 60)
        
        try:
            # Run paper trading session
            result = subprocess.run(
                [sys.executable, "run_paper_session.py", str(self.grid_mins)],
                capture_output=True,
                text=True,
                timeout=self.grid_mins * 60 + 60  # Extra minute for cleanup
            )
            
            # Parse results from logs
            report_file = Path("logs/paper_session_report.json")
            if report_file.exists():
                with open(report_file, 'r') as f:
                    report = json.load(f)
                    
                metrics = report.get('fill_metrics', {})
                session = report.get('session', {})
                
                return {
                    'trades': session.get('trades_executed', 0),
                    'pnl_pct': (session.get('total_pnl', 0) / 10000) * 100,  # Assume $10k capital
                    'maker_fill_rate': metrics.get('maker_fill_rate', 0),
                    'avg_time_to_fill': metrics.get('avg_time_to_fill_ms', 0)
                }
            else:
                print("Warning: No grid session report found")
                return {'trades': 0, 'pnl_pct': 0, 'maker_fill_rate': 0, 'avg_time_to_fill': 0}
                
        except subprocess.TimeoutExpired:
            print("Grid session timed out")
            return {'trades': 0, 'pnl_pct': 0, 'maker_fill_rate': 0, 'avg_time_to_fill': 0}
        except Exception as e:
            print(f"Grid session error: {e}")
            return {'trades': 0, 'pnl_pct': 0, 'maker_fill_rate': 0, 'avg_time_to_fill': 0}
            
    def run_arbitrage_session(self) -> Dict:
        """Run Turkish arbitrage session"""
        print("\n" + "=" * 60)
        print(f"STARTING ARBITRAGE SESSION ({self.arb_mins} minutes)")
        print("=" * 60)
        
        try:
            # Run arbitrage session
            result = subprocess.run(
                [sys.executable, "tools/run_tr_arbitrage_session.py", str(self.arb_mins)],
                capture_output=True,
                text=True,
                timeout=self.arb_mins * 60 + 60
            )
            
            # Parse results
            report_file = Path("logs/tr_arb_session_report.json")
            if report_file.exists():
                with open(report_file, 'r') as f:
                    report = json.load(f)
                    
                metrics = report.get('metrics', {})
                latency = report.get('latency', {})
                
                return {
                    'trades': metrics.get('trades_executed', 0),
                    'pnl_tl': metrics.get('total_profit_tl', 0),
                    'success_rate': metrics.get('success_rate', 0),
                    'avg_latency_ms': (latency.get('binance_avg_ms', 0) + 
                                      latency.get('btcturk_avg_ms', 0)) / 2
                }
            else:
                print("Warning: No arbitrage report found")
                return {'trades': 0, 'pnl_tl': 0, 'success_rate': 0, 'avg_latency_ms': 0}
                
        except subprocess.TimeoutExpired:
            print("Arbitrage session timed out")
            return {'trades': 0, 'pnl_tl': 0, 'success_rate': 0, 'avg_latency_ms': 0}
        except Exception as e:
            print(f"Arbitrage session error: {e}")
            return {'trades': 0, 'pnl_tl': 0, 'success_rate': 0, 'avg_latency_ms': 0}
            
    def run_qa_checks(self) -> Dict:
        """Run QA checks"""
        print("\n" + "=" * 60)
        print("RUNNING QA CHECKS")
        print("=" * 60)
        
        qa_results = {}
        
        # Run consistency check
        try:
            result = subprocess.run(
                [sys.executable, "tools/consistency_check.py"],
                capture_output=True,
                text=True,
                timeout=30
            )
            qa_results['consistency'] = "PASS" if result.returncode == 0 else "FAIL"
        except:
            qa_results['consistency'] = "ERROR"
            
        # Get shadow diff if available
        shadow_file = Path("logs/shadow_diff.jsonl")
        if shadow_file.exists():
            diffs = []
            with open(shadow_file, 'r') as f:
                for line in f:
                    try:
                        diff = json.loads(line)
                        diffs.append(diff.get('price_diff_bps', 0))
                    except:
                        continue
                        
            qa_results['shadow_avg_diff_bps'] = sum(diffs) / len(diffs) if diffs else 0
        else:
            qa_results['shadow_avg_diff_bps'] = 0
            
        return qa_results
        
    def calculate_risk_metrics(self) -> Dict:
        """Calculate risk metrics"""
        # Simple max drawdown calculation from P&L history
        pnl_file = Path("logs/pnl_timeseries.json")
        
        if pnl_file.exists():
            with open(pnl_file, 'r') as f:
                timeseries = json.load(f)
                
            if timeseries:
                equities = [point.get('equity', 10000) for point in timeseries]
                
                # Calculate max drawdown
                peak = equities[0]
                max_dd = 0
                
                for equity in equities:
                    if equity > peak:
                        peak = equity
                    dd = (equity - peak) / peak * 100
                    if dd < max_dd:
                        max_dd = dd
                        
                return {'max_dd_pct': max_dd}
        
        return {'max_dd_pct': 0}
        
    def generate_scorecard(self) -> Dict:
        """Generate daily scorecard"""
        scorecard = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
            'grid': self.results.get('grid', {}),
            'arb': self.results.get('arb', {}),
            'risk': self.results.get('risk', {}),
            'qa': self.results.get('qa', {})
        }
        
        # Save scorecard
        scorecard_file = Path("reports/daily_score.json")
        scorecard_file.parent.mkdir(exist_ok=True)
        
        with open(scorecard_file, 'w') as f:
            json.dump(scorecard, f, indent=2)
            
        return scorecard
        
    def print_scorecard(self, scorecard: Dict):
        """Print formatted scorecard"""
        print("\n" + "=" * 60)
        print("DAILY SCORECARD")
        print("=" * 60)
        print(f"Date: {scorecard['date']}")
        print("-" * 60)
        
        print("\nGRID TRADING:")
        grid = scorecard['grid']
        print(f"  Trades: {grid.get('trades', 0)}")
        print(f"  P&L: {grid.get('pnl_pct', 0):.2f}%")
        print(f"  Maker Fill Rate: {grid.get('maker_fill_rate', 0):.1f}%")
        print(f"  Avg Fill Time: {grid.get('avg_time_to_fill', 0):.0f}ms")
        
        print("\nARBITRAGE:")
        arb = scorecard['arb']
        print(f"  Trades: {arb.get('trades', 0)}")
        print(f"  P&L (TL): {arb.get('pnl_tl', 0):.2f}")
        print(f"  Success Rate: {arb.get('success_rate', 0):.1f}%")
        print(f"  Avg Latency: {arb.get('avg_latency_ms', 0):.0f}ms")
        
        print("\nRISK:")
        risk = scorecard['risk']
        print(f"  Max Drawdown: {risk.get('max_dd_pct', 0):.2f}%")
        
        print("\nQA:")
        qa = scorecard['qa']
        print(f"  Consistency: {qa.get('consistency', 'N/A')}")
        print(f"  Shadow Avg Diff: {qa.get('shadow_avg_diff_bps', 0):.2f} bps")
        
        print("=" * 60)
        
    def run(self):
        """Run complete orchestration"""
        self.start_time = datetime.now()
        
        print("\n" + "=" * 70)
        print(" DAILY SESSION ORCHESTRATOR")
        print("=" * 70)
        print(f"Start Time: {self.start_time}")
        print(f"Grid Duration: {self.grid_mins} minutes")
        print(f"Arbitrage Duration: {self.arb_mins} minutes")
        print("-" * 70)
        
        # Run sessions
        self.results['grid'] = self.run_grid_session()
        self.results['arb'] = self.run_arbitrage_session()
        
        # Calculate risk metrics
        self.results['risk'] = self.calculate_risk_metrics()
        
        # Run QA checks
        self.results['qa'] = self.run_qa_checks()
        
        # Generate and print scorecard
        scorecard = self.generate_scorecard()
        self.print_scorecard(scorecard)
        
        # Calculate total time
        total_time = (datetime.now() - self.start_time).total_seconds() / 60
        print(f"\nTotal Time: {total_time:.1f} minutes")
        print(f"Scorecard saved to: reports/daily_score.json")
        
        return scorecard


def main():
    parser = argparse.ArgumentParser(description='Daily Session Orchestrator')
    parser.add_argument('--grid-mins', type=int, default=60, help='Grid session duration (minutes)')
    parser.add_argument('--arb-mins', type=int, default=30, help='Arbitrage session duration (minutes)')
    
    args = parser.parse_args()
    
    orchestrator = SessionOrchestrator(args.grid_mins, args.arb_mins)
    orchestrator.run()


if __name__ == "__main__":
    main()