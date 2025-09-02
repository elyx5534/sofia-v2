"""
3-Day Auto Campaign Runner
Full automation with daily archiving
"""

import sys
import json
import time
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))


class PaperCampaign:
    """Run multi-day paper trading campaign"""
    
    def __init__(self, days: int = 3, grid_mins: int = 60, arb_mins: int = 30):
        self.days = days
        self.grid_mins = grid_mins
        self.arb_mins = arb_mins
        self.campaign_start = datetime.now()
        self.daily_results = []
        
    def run_daily_session(self, day_num: int) -> Dict:
        """Run one day's sessions"""
        print("=" * 70)
        print(f" DAY {day_num}/{self.days} - {datetime.now().strftime('%Y-%m-%d')}")
        print("=" * 70)
        
        # Run daily validation (grid + arb + QA)
        print(f"\n[{datetime.now().strftime('%H:%M')}] Starting daily validation...")
        result = subprocess.run(
            [sys.executable, "tools/session_orchestrator.py",
             "--grid-mins", str(self.grid_mins),
             "--arb-mins", str(self.arb_mins)],
            capture_output=True,
            text=True
        )
        
        # Wait for completion
        time.sleep(2)
        
        # Apply adaptive parameters
        print(f"\n[{datetime.now().strftime('%H:%M')}] Applying adaptive tuning...")
        adapt_result = subprocess.run(
            [sys.executable, "tools/apply_adaptive_params.py"],
            capture_output=True,
            text=True
        )
        
        # Load daily score
        score_file = Path("reports/daily_score.json")
        if score_file.exists():
            with open(score_file, 'r') as f:
                daily_score = json.load(f)
                
            # Archive the daily score
            archive_dir = Path("reports/archive")
            archive_dir.mkdir(exist_ok=True)
            
            archive_name = f"daily_{datetime.now().strftime('%Y%m%d')}.json"
            archive_path = archive_dir / archive_name
            
            with open(archive_path, 'w') as f:
                json.dump(daily_score, f, indent=2)
                
            print(f"[ARCHIVED] Daily score saved to {archive_path}")
            
            return daily_score
        else:
            print("[WARNING] No daily score file found")
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'grid': {'trades': 0, 'pnl_pct': 0, 'maker_fill_rate': 0},
                'arb': {'trades': 0, 'pnl_tl': 0, 'success_rate': 0},
                'qa': {'consistency': 'UNKNOWN', 'shadow_avg_diff_bps': 0},
                'risk': {'max_dd_pct': 0}
            }
    
    def generate_campaign_summary(self) -> Dict:
        """Generate campaign summary"""
        summary = {
            'campaign_id': self.campaign_start.strftime('%Y%m%d_%H%M'),
            'start_time': self.campaign_start.isoformat(),
            'end_time': datetime.now().isoformat(),
            'days': self.days,
            'grid_mins_per_day': self.grid_mins,
            'arb_mins_per_day': self.arb_mins,
            'daily_results': self.daily_results
        }
        
        # Calculate aggregates
        if self.daily_results:
            # Grid metrics
            grid_pnls = [d['grid']['pnl_pct'] for d in self.daily_results]
            grid_fill_rates = [d['grid']['maker_fill_rate'] for d in self.daily_results]
            grid_trades = [d['grid']['trades'] for d in self.daily_results]
            
            summary['grid'] = {
                'avg_pnl_pct': sum(grid_pnls) / len(grid_pnls) if grid_pnls else 0,
                'total_pnl_pct': sum(grid_pnls),
                'avg_fill_rate': sum(grid_fill_rates) / len(grid_fill_rates) if grid_fill_rates else 0,
                'total_trades': sum(grid_trades)
            }
            
            # Arbitrage metrics
            arb_pnls = [d['arb']['pnl_tl'] for d in self.daily_results]
            arb_success = [d['arb']['success_rate'] for d in self.daily_results]
            arb_trades = [d['arb']['trades'] for d in self.daily_results]
            
            summary['arb'] = {
                'sum_pnl_tl': sum(arb_pnls),
                'avg_success_rate': sum(arb_success) / len(arb_success) if arb_success else 0,
                'total_trades': sum(arb_trades)
            }
            
            # QA metrics
            consistency_passes = sum(1 for d in self.daily_results 
                                   if d['qa'].get('consistency') == 'PASS')
            shadow_diffs = [d['qa']['shadow_avg_diff_bps'] for d in self.daily_results]
            
            summary['qa'] = {
                'consistency_pass_rate': (consistency_passes / len(self.daily_results)) * 100,
                'shadow_avg_bps': sum(shadow_diffs) / len(shadow_diffs) if shadow_diffs else 0
            }
            
            # Risk metrics
            max_dds = [d['risk']['max_dd_pct'] for d in self.daily_results]
            
            summary['risk'] = {
                'max_dd_min': min(max_dds) if max_dds else 0,
                'max_dd_max': max(max_dds) if max_dds else 0,
                'max_dd_avg': sum(max_dds) / len(max_dds) if max_dds else 0
            }
        else:
            summary['grid'] = {'avg_pnl_pct': 0, 'total_pnl_pct': 0, 'avg_fill_rate': 0, 'total_trades': 0}
            summary['arb'] = {'sum_pnl_tl': 0, 'avg_success_rate': 0, 'total_trades': 0}
            summary['qa'] = {'consistency_pass_rate': 0, 'shadow_avg_bps': 0}
            summary['risk'] = {'max_dd_min': 0, 'max_dd_max': 0, 'max_dd_avg': 0}
        
        return summary
    
    def save_campaign_summary(self, summary: Dict):
        """Save campaign summary"""
        summary_file = Path("reports/campaign_summary.json")
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
            
        print(f"\n[SAVED] Campaign summary: {summary_file}")
        
        # Also create markdown report
        self.save_markdown_summary(summary)
    
    def save_markdown_summary(self, summary: Dict):
        """Save campaign summary as markdown"""
        md_file = Path("reports/CAMPAIGN_SUMMARY.md")
        
        with open(md_file, 'w') as f:
            f.write("# Paper Trading Campaign Summary\n\n")
            f.write(f"**Campaign ID:** {summary['campaign_id']}\n")
            f.write(f"**Duration:** {summary['days']} days\n")
            f.write(f"**Sessions:** {summary['grid_mins_per_day']}min grid + {summary['arb_mins_per_day']}min arbitrage daily\n\n")
            
            f.write("## Grid Trading Results\n")
            f.write(f"- Total Trades: {summary['grid']['total_trades']}\n")
            f.write(f"- Total P&L: {summary['grid']['total_pnl_pct']:.2f}%\n")
            f.write(f"- Avg Daily P&L: {summary['grid']['avg_pnl_pct']:.2f}%\n")
            f.write(f"- Avg Fill Rate: {summary['grid']['avg_fill_rate']:.1f}%\n\n")
            
            f.write("## Arbitrage Results\n")
            f.write(f"- Total Trades: {summary['arb']['total_trades']}\n")
            f.write(f"- Total P&L (TL): {summary['arb']['sum_pnl_tl']:.2f}\n")
            f.write(f"- Avg Success Rate: {summary['arb']['avg_success_rate']:.1f}%\n\n")
            
            f.write("## Quality Metrics\n")
            f.write(f"- Consistency Pass Rate: {summary['qa']['consistency_pass_rate']:.1f}%\n")
            f.write(f"- Avg Shadow Diff: {summary['qa']['shadow_avg_bps']:.2f} bps\n\n")
            
            f.write("## Risk Metrics\n")
            f.write(f"- Min Drawdown: {summary['risk']['max_dd_min']:.2f}%\n")
            f.write(f"- Max Drawdown: {summary['risk']['max_dd_max']:.2f}%\n")
            f.write(f"- Avg Drawdown: {summary['risk']['max_dd_avg']:.2f}%\n\n")
            
            f.write("## Daily Breakdown\n\n")
            f.write("| Day | Grid P&L | Grid Fill | Arb P&L | Arb Success | Consistency | Shadow Diff |\n")
            f.write("|-----|----------|-----------|---------|-------------|-------------|-------------|\n")
            
            for i, day in enumerate(summary['daily_results'], 1):
                f.write(f"| {i} | {day['grid']['pnl_pct']:.2f}% | {day['grid']['maker_fill_rate']:.1f}% | ")
                f.write(f"{day['arb']['pnl_tl']:.0f} TL | {day['arb']['success_rate']:.1f}% | ")
                f.write(f"{day['qa']['consistency']} | {day['qa']['shadow_avg_diff_bps']:.2f} bps |\n")
    
    def print_summary(self, summary: Dict):
        """Print campaign summary"""
        print("\n" + "=" * 70)
        print(" CAMPAIGN SUMMARY")
        print("=" * 70)
        print(f"Campaign ID: {summary['campaign_id']}")
        print(f"Duration: {summary['days']} days")
        print("-" * 70)
        
        print("\nGRID TRADING:")
        print(f"  Total Trades: {summary['grid']['total_trades']}")
        print(f"  Total P&L: {summary['grid']['total_pnl_pct']:.2f}%")
        print(f"  Avg Fill Rate: {summary['grid']['avg_fill_rate']:.1f}%")
        
        print("\nARBITRAGE:")
        print(f"  Total Trades: {summary['arb']['total_trades']}")
        print(f"  Total P&L: {summary['arb']['sum_pnl_tl']:.2f} TL")
        print(f"  Avg Success: {summary['arb']['avg_success_rate']:.1f}%")
        
        print("\nQUALITY:")
        print(f"  Consistency Pass: {summary['qa']['consistency_pass_rate']:.1f}%")
        print(f"  Shadow Diff: {summary['qa']['shadow_avg_bps']:.2f} bps")
        
        print("\nRISK:")
        print(f"  Max Drawdown: {summary['risk']['max_dd_max']:.2f}%")
        print("=" * 70)
    
    def run(self):
        """Run the full campaign"""
        print("\n" + "=" * 80)
        print(f" STARTING {self.days}-DAY PAPER TRADING CAMPAIGN")
        print("=" * 80)
        print(f"Start Time: {self.campaign_start}")
        print(f"Daily Sessions: {self.grid_mins}min grid + {self.arb_mins}min arbitrage")
        print("-" * 80)
        
        # Run daily sessions
        for day in range(1, self.days + 1):
            daily_result = self.run_daily_session(day)
            self.daily_results.append(daily_result)
            
            # Wait between days (simulate overnight)
            if day < self.days:
                print(f"\n[WAITING] Simulating overnight break (10 seconds)...")
                time.sleep(10)
        
        # Generate and save summary
        summary = self.generate_campaign_summary()
        self.save_campaign_summary(summary)
        self.print_summary(summary)
        
        print("\nCAMPAIGN COMPLETE!")
        print("Reports saved to:")
        print("  - reports/campaign_summary.json")
        print("  - reports/CAMPAIGN_SUMMARY.md")
        print("  - reports/archive/daily_*.json")
        
        return summary


def main():
    parser = argparse.ArgumentParser(description='3-Day Paper Campaign Runner')
    parser.add_argument('--days', type=int, default=3, help='Number of days')
    parser.add_argument('--grid-mins', type=int, default=60, help='Grid session minutes per day')
    parser.add_argument('--arb-mins', type=int, default=30, help='Arbitrage session minutes per day')
    
    args = parser.parse_args()
    
    campaign = PaperCampaign(args.days, args.grid_mins, args.arb_mins)
    campaign.run()


if __name__ == "__main__":
    main()