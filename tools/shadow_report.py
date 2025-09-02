"""
Shadow vs Paper Deviation Analysis
Automatic report generation
"""

import json
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple


class ShadowReporter:
    """Generate shadow vs paper comparison reports"""
    
    def __init__(self):
        self.shadow_file = Path("logs/shadow_diff.jsonl")
        self.paper_file = Path("logs/paper_session_report.json")
        self.metrics = {}
        
    def load_shadow_diffs(self) -> List[Dict]:
        """Load shadow diff data"""
        diffs = []
        
        if self.shadow_file.exists():
            with open(self.shadow_file, 'r') as f:
                for line in f:
                    try:
                        diff = json.loads(line)
                        diffs.append(diff)
                    except:
                        continue
        
        return diffs
    
    def calculate_metrics(self, diffs: List[Dict]) -> Dict:
        """Calculate shadow metrics"""
        if not diffs:
            return {
                'avg_price_diff_bps': 0,
                'p95_price_diff_bps': 0,
                'p99_price_diff_bps': 0,
                'max_price_diff_bps': 0,
                'min_price_diff_bps': 0,
                'std_price_diff_bps': 0,
                'avg_fill_prob': 0,
                'shadow_fills': 0,
                'paper_fills': 0,
                'fill_alignment_rate': 0,
                'samples': 0
            }
        
        # Extract price differences
        price_diffs = [d.get('price_diff_bps', 0) for d in diffs]
        
        # Calculate percentiles
        sorted_diffs = sorted(price_diffs)
        p95_index = int(len(sorted_diffs) * 0.95)
        p99_index = int(len(sorted_diffs) * 0.99)
        
        # Count fills
        shadow_fills = sum(1 for d in diffs if d.get('shadow_filled', False))
        paper_fills = sum(1 for d in diffs if d.get('paper_filled', False))
        both_filled = sum(1 for d in diffs 
                         if d.get('shadow_filled', False) and d.get('paper_filled', False))
        
        # Calculate alignment
        alignment_rate = (both_filled / max(shadow_fills, paper_fills, 1)) * 100
        
        # Calculate fill probability
        fill_probs = [d.get('fill_probability', 0) for d in diffs if 'fill_probability' in d]
        avg_fill_prob = statistics.mean(fill_probs) if fill_probs else 0
        
        return {
            'avg_price_diff_bps': statistics.mean(price_diffs),
            'p95_price_diff_bps': sorted_diffs[p95_index] if p95_index < len(sorted_diffs) else 0,
            'p99_price_diff_bps': sorted_diffs[p99_index] if p99_index < len(sorted_diffs) else 0,
            'max_price_diff_bps': max(price_diffs),
            'min_price_diff_bps': min(price_diffs),
            'std_price_diff_bps': statistics.stdev(price_diffs) if len(price_diffs) > 1 else 0,
            'avg_fill_prob': avg_fill_prob,
            'shadow_fills': shadow_fills,
            'paper_fills': paper_fills,
            'fill_alignment_rate': alignment_rate,
            'samples': len(diffs)
        }
    
    def analyze_pnl_diff(self, diffs: List[Dict]) -> Dict:
        """Analyze P&L differences"""
        if not diffs:
            return {
                'shadow_pnl': 0,
                'paper_pnl': 0,
                'pnl_diff': 0,
                'pnl_diff_pct': 0
            }
        
        # Calculate cumulative P&L
        shadow_pnl = sum(d.get('shadow_pnl', 0) for d in diffs)
        paper_pnl = sum(d.get('paper_pnl', 0) for d in diffs)
        
        pnl_diff = shadow_pnl - paper_pnl
        pnl_diff_pct = (pnl_diff / abs(paper_pnl) * 100) if paper_pnl != 0 else 0
        
        return {
            'shadow_pnl': shadow_pnl,
            'paper_pnl': paper_pnl,
            'pnl_diff': pnl_diff,
            'pnl_diff_pct': pnl_diff_pct
        }
    
    def generate_time_analysis(self, diffs: List[Dict]) -> Dict:
        """Analyze metrics over time"""
        if not diffs:
            return {'hourly_metrics': []}
        
        # Group by hour
        hourly = {}
        for diff in diffs:
            if 'timestamp' in diff:
                try:
                    dt = datetime.fromisoformat(diff['timestamp'])
                    hour = dt.strftime('%Y-%m-%d %H:00')
                    
                    if hour not in hourly:
                        hourly[hour] = []
                    hourly[hour].append(diff.get('price_diff_bps', 0))
                except:
                    continue
        
        # Calculate hourly averages
        hourly_metrics = []
        for hour, values in sorted(hourly.items()):
            hourly_metrics.append({
                'hour': hour,
                'avg_diff_bps': statistics.mean(values),
                'max_diff_bps': max(values),
                'samples': len(values)
            })
        
        return {'hourly_metrics': hourly_metrics}
    
    def generate_report(self) -> Dict:
        """Generate complete shadow report"""
        # Load data
        diffs = self.load_shadow_diffs()
        
        # Calculate metrics
        metrics = self.calculate_metrics(diffs)
        pnl_analysis = self.analyze_pnl_diff(diffs)
        time_analysis = self.generate_time_analysis(diffs)
        
        # Load paper session data if available
        paper_metrics = {}
        if self.paper_file.exists():
            with open(self.paper_file, 'r') as f:
                paper_data = json.load(f)
                paper_metrics = paper_data.get('fill_metrics', {})
        
        # Generate report
        report = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'shadow_metrics': metrics,
            'pnl_analysis': pnl_analysis,
            'time_analysis': time_analysis,
            'paper_metrics': paper_metrics,
            'summary': self._generate_summary(metrics, pnl_analysis)
        }
        
        return report
    
    def _generate_summary(self, metrics: Dict, pnl: Dict) -> Dict:
        """Generate summary assessment"""
        # Assess quality
        quality = 'EXCELLENT' if metrics['avg_price_diff_bps'] < 3 else \
                 'GOOD' if metrics['avg_price_diff_bps'] < 5 else \
                 'ACCEPTABLE' if metrics['avg_price_diff_bps'] < 10 else 'POOR'
        
        # Assess alignment
        alignment = 'HIGH' if metrics['fill_alignment_rate'] > 90 else \
                   'MODERATE' if metrics['fill_alignment_rate'] > 70 else 'LOW'
        
        # Generate recommendations
        recommendations = []
        
        if metrics['avg_price_diff_bps'] > 5:
            recommendations.append("Consider reducing latency or improving price feeds")
        
        if metrics['fill_alignment_rate'] < 80:
            recommendations.append("Review fill simulation logic for accuracy")
        
        if abs(pnl['pnl_diff_pct']) > 5:
            recommendations.append("Investigate P&L calculation differences")
        
        if metrics['p95_price_diff_bps'] > 10:
            recommendations.append("Address tail latency issues causing price spikes")
        
        return {
            'quality': quality,
            'alignment': alignment,
            'recommendations': recommendations,
            'ready_for_live': quality in ['EXCELLENT', 'GOOD'] and alignment in ['HIGH', 'MODERATE']
        }
    
    def save_report(self, report: Dict):
        """Save report to files"""
        # Save JSON
        date_str = datetime.now().strftime('%Y%m%d')
        json_file = Path(f"reports/shadow_report_{date_str}.json")
        json_file.parent.mkdir(exist_ok=True)
        
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"[SAVED] Shadow report: {json_file}")
        
        # Save markdown
        self.save_markdown_report(report, date_str)
    
    def save_markdown_report(self, report: Dict, date_str: str):
        """Save markdown report"""
        md_file = Path(f"reports/shadow_report_{date_str}.md")
        
        with open(md_file, 'w') as f:
            f.write(f"# Shadow vs Paper Report\n\n")
            f.write(f"**Date:** {report['date']}\n")
            f.write(f"**Generated:** {report['timestamp']}\n\n")
            
            # Metrics section
            m = report['shadow_metrics']
            f.write("## Price Deviation Metrics\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Average Diff | {m['avg_price_diff_bps']:.2f} bps |\n")
            f.write(f"| P95 Diff | {m['p95_price_diff_bps']:.2f} bps |\n")
            f.write(f"| P99 Diff | {m['p99_price_diff_bps']:.2f} bps |\n")
            f.write(f"| Max Diff | {m['max_price_diff_bps']:.2f} bps |\n")
            f.write(f"| Std Dev | {m['std_price_diff_bps']:.2f} bps |\n")
            f.write(f"| Samples | {m['samples']} |\n\n")
            
            # Fill analysis
            f.write("## Fill Analysis\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Shadow Fills | {m['shadow_fills']} |\n")
            f.write(f"| Paper Fills | {m['paper_fills']} |\n")
            f.write(f"| Alignment Rate | {m['fill_alignment_rate']:.1f}% |\n")
            f.write(f"| Avg Fill Prob | {m['avg_fill_prob']:.1f}% |\n\n")
            
            # P&L analysis
            p = report['pnl_analysis']
            f.write("## P&L Analysis\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Shadow P&L | ${p['shadow_pnl']:.2f} |\n")
            f.write(f"| Paper P&L | ${p['paper_pnl']:.2f} |\n")
            f.write(f"| Difference | ${p['pnl_diff']:.2f} ({p['pnl_diff_pct']:.1f}%) |\n\n")
            
            # Summary
            s = report['summary']
            f.write("## Summary Assessment\n\n")
            f.write(f"- **Quality:** {s['quality']}\n")
            f.write(f"- **Alignment:** {s['alignment']}\n")
            f.write(f"- **Ready for Live:** {'YES' if s['ready_for_live'] else 'NO'}\n\n")
            
            if s['recommendations']:
                f.write("### Recommendations\n\n")
                for rec in s['recommendations']:
                    f.write(f"- {rec}\n")
    
    def print_summary(self, report: Dict):
        """Print report summary"""
        print("\n" + "=" * 60)
        print("SHADOW vs PAPER REPORT")
        print("=" * 60)
        print(f"Date: {report['date']}")
        print("-" * 60)
        
        m = report['shadow_metrics']
        print("\nPRICE DEVIATION:")
        print(f"  Average: {m['avg_price_diff_bps']:.2f} bps")
        print(f"  P95: {m['p95_price_diff_bps']:.2f} bps")
        print(f"  Max: {m['max_price_diff_bps']:.2f} bps")
        
        print("\nFILL ALIGNMENT:")
        print(f"  Shadow Fills: {m['shadow_fills']}")
        print(f"  Paper Fills: {m['paper_fills']}")
        print(f"  Alignment: {m['fill_alignment_rate']:.1f}%")
        
        s = report['summary']
        print("\nASSESSMENT:")
        print(f"  Quality: {s['quality']}")
        print(f"  Ready for Live: {'YES' if s['ready_for_live'] else 'NO'}")
        
        if s['recommendations']:
            print("\nRECOMMENDATIONS:")
            for rec in s['recommendations']:
                print(f"  - {rec}")
        
        print("\nREPORTS SAVED:")
        date_str = datetime.now().strftime('%Y%m%d')
        print(f"  - reports/shadow_report_{date_str}.json")
        print(f"  - reports/shadow_report_{date_str}.md")
        print("=" * 60)


def main():
    reporter = ShadowReporter()
    report = reporter.generate_report()
    reporter.save_report(report)
    reporter.print_summary(report)


if __name__ == "__main__":
    main()