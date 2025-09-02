"""
P&L Consistency Checker
Validates P&L across multiple sources and reports discrepancies
"""

import json
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Dict, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.accounting import FIFOAccounting


class ConsistencyChecker:
    """Check P&L consistency across multiple sources"""
    
    def __init__(self):
        self.tolerances = {
            'equity_pct': 0.05,  # 0.05% tolerance for equity
            'realized_pct': 0.02,  # 0.02% tolerance for realized P&L
        }
        self.results = {}
        
    def check_all_sources(self) -> Tuple[bool, Dict]:
        """Check consistency across all P&L sources"""
        sources = {}
        
        # Source 1: Accounting module
        try:
            accounting = FIFOAccounting()
            # Load from saved state if exists
            state_file = Path("logs/accounting_state.json")
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    sources['accounting'] = {
                        'equity': Decimal(str(state.get('total_equity', 0))),
                        'realized': Decimal(str(state.get('realized_pnl', 0))),
                        'unrealized': Decimal(str(state.get('unrealized_pnl', 0)))
                    }
            else:
                sources['accounting'] = {
                    'equity': Decimal("0"),
                    'realized': Decimal("0"),
                    'unrealized': Decimal("0")
                }
        except Exception as e:
            print(f"Error loading accounting: {e}")
            sources['accounting'] = None
            
        # Source 2: P&L timeseries
        try:
            timeseries_file = Path("logs/pnl_timeseries.json")
            if timeseries_file.exists():
                with open(timeseries_file, 'r') as f:
                    timeseries = json.load(f)
                    if timeseries and isinstance(timeseries, list):
                        last_point = timeseries[-1]
                        sources['timeseries'] = {
                            'equity': Decimal(str(last_point.get('equity', 0))),
                            'realized': Decimal(str(last_point.get('realized', 0))),
                            'unrealized': Decimal(str(last_point.get('unrealized', 0)))
                        }
                    else:
                        sources['timeseries'] = None
            else:
                sources['timeseries'] = None
        except Exception as e:
            print(f"Error loading timeseries: {e}")
            sources['timeseries'] = None
            
        # Source 3: Paper audit log
        try:
            audit_file = Path("logs/paper_audit.jsonl")
            if audit_file.exists():
                realized_sum = Decimal("0")
                with open(audit_file, 'r') as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if entry.get('type') == 'fill' and 'realized_pnl' in entry:
                                realized_sum += Decimal(str(entry['realized_pnl']))
                        except:
                            continue
                            
                sources['audit'] = {
                    'realized': realized_sum
                }
            else:
                sources['audit'] = None
        except Exception as e:
            print(f"Error loading audit: {e}")
            sources['audit'] = None
            
        # Check consistency
        return self._validate_consistency(sources)
        
    def _validate_consistency(self, sources: Dict) -> Tuple[bool, Dict]:
        """Validate consistency between sources"""
        # Convert Decimal to float for JSON serialization
        serializable_sources = {}
        for key, value in sources.items():
            if value is None:
                serializable_sources[key] = None
            elif isinstance(value, dict):
                serializable_sources[key] = {
                    k: float(v) if hasattr(v, '__float__') else v
                    for k, v in value.items()
                }
            else:
                serializable_sources[key] = value
                
        report = {
            'timestamp': datetime.now().isoformat(),
            'sources': serializable_sources,
            'checks': [],
            'overall': 'PASS'
        }
        
        # Skip if not enough valid sources
        valid_sources = [k for k, v in sources.items() if v is not None]
        if len(valid_sources) < 2:
            report['overall'] = 'INSUFFICIENT_DATA'
            report['message'] = f"Only {len(valid_sources)} valid sources found"
            return False, report
            
        # Check equity consistency
        if sources.get('accounting') and sources.get('timeseries'):
            acc_equity = sources['accounting']['equity']
            ts_equity = sources['timeseries']['equity']
            
            if acc_equity > 0 and ts_equity > 0:
                diff_pct = abs((acc_equity - ts_equity) / acc_equity * 100)
                check = {
                    'type': 'equity',
                    'source1': 'accounting',
                    'source2': 'timeseries',
                    'value1': float(acc_equity),
                    'value2': float(ts_equity),
                    'diff_pct': float(diff_pct),
                    'tolerance_pct': self.tolerances['equity_pct'],
                    'status': 'PASS' if diff_pct <= self.tolerances['equity_pct'] else 'FAIL'
                }
                report['checks'].append(check)
                if check['status'] == 'FAIL':
                    report['overall'] = 'FAIL'
                    
        # Check realized P&L consistency
        realized_values = []
        for source_name, data in sources.items():
            if data and 'realized' in data:
                realized_values.append((source_name, data['realized']))
                
        if len(realized_values) >= 2:
            for i in range(len(realized_values) - 1):
                source1, val1 = realized_values[i]
                source2, val2 = realized_values[i + 1]
                
                if val1 > 0 or val2 > 0:
                    base = max(abs(val1), abs(val2))
                    if base > 0:
                        diff_pct = abs((val1 - val2) / base * 100)
                        check = {
                            'type': 'realized_pnl',
                            'source1': source1,
                            'source2': source2,
                            'value1': float(val1),
                            'value2': float(val2),
                            'diff_pct': float(diff_pct),
                            'tolerance_pct': self.tolerances['realized_pct'],
                            'status': 'PASS' if diff_pct <= self.tolerances['realized_pct'] else 'FAIL'
                        }
                        report['checks'].append(check)
                        if check['status'] == 'FAIL':
                            report['overall'] = 'FAIL'
                            
        # Save report
        report_file = Path("logs/consistency_report.json")
        report_file.parent.mkdir(exist_ok=True)
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        return report['overall'] == 'PASS', report
        
    def print_report(self, report: Dict):
        """Print formatted consistency report"""
        print("=" * 60)
        print("P&L CONSISTENCY REPORT")
        print("=" * 60)
        print(f"Timestamp: {report['timestamp']}")
        print(f"Overall Status: {report['overall']}")
        print("-" * 60)
        
        if 'checks' in report:
            for check in report['checks']:
                print(f"\n{check['type'].upper()} Check:")
                print(f"  {check['source1']}: {check['value1']:.2f}")
                print(f"  {check['source2']}: {check['value2']:.2f}")
                print(f"  Difference: {check['diff_pct']:.3f}%")
                print(f"  Tolerance: {check['tolerance_pct']:.3f}%")
                print(f"  Status: {check['status']}")
                
        print("=" * 60)


def main():
    checker = ConsistencyChecker()
    passed, report = checker.check_all_sources()
    checker.print_report(report)
    
    # Exit with appropriate code
    if passed:
        print("\n[PASS] CONSISTENCY CHECK PASSED")
        sys.exit(0)
    else:
        print("\n[FAIL] CONSISTENCY CHECK FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()