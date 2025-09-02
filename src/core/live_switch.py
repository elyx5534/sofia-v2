"""
Live Trading Switch with Two-Man Approval
Controls activation of real trading
"""

import yaml
import json
from pathlib import Path
from datetime import datetime, time
from typing import Dict, List, Tuple, Optional
import pytz


class LiveSwitch:
    """Live trading switch with safety controls"""
    
    def __init__(self, config_path: str = "config/live.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.timezone = pytz.timezone('Europe/Istanbul')
        self.reasons = []
        
    def _load_config(self) -> Dict:
        """Load live trading configuration"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            return self._default_config()
    
    def _default_config(self) -> Dict:
        """Default safe configuration"""
        return {
            'enable_real_trading': False,
            'limits': {
                'max_notional_tl': 1000,
                'per_trade_tl_cap': 250
            },
            'whitelisted_symbols': ['BTC/USDT'],
            'live_hours': ['10:00-18:00'],
            'operators': {
                'operator_A': 'emre',
                'operator_B': 'reviewer'
            },
            'approvals': {
                'operator_A': False,
                'operator_B': False
            },
            'requirements': {
                'min_paper_trades': 500,
                'min_fill_rate': 60,
                'max_shadow_diff_bps': 5,
                'min_readiness_score': 80,
                'consistency_check': 'PASS'
            }
        }
    
    def check_approvals(self) -> Tuple[bool, List[str]]:
        """Check if both operators have approved"""
        reasons = []
        
        approvals = self.config.get('approvals', {})
        
        if not approvals.get('operator_A', False):
            reasons.append(f"Operator A ({self.config['operators']['operator_A']}) approval missing")
        
        if not approvals.get('operator_B', False):
            reasons.append(f"Operator B ({self.config['operators']['operator_B']}) approval missing")
        
        both_approved = len(reasons) == 0
        
        return both_approved, reasons
    
    def check_requirements(self) -> Tuple[bool, List[str]]:
        """Check if all requirements are met"""
        reasons = []
        requirements = self.config.get('requirements', {})
        
        # Check paper trades
        paper_trades = self._get_paper_trades()
        min_trades = requirements.get('min_paper_trades', 500)
        if paper_trades < min_trades:
            reasons.append(f"Paper trades ({paper_trades}) < minimum ({min_trades})")
        
        # Check fill rate
        fill_rate = self._get_fill_rate()
        min_fill = requirements.get('min_fill_rate', 60)
        if fill_rate < min_fill:
            reasons.append(f"Fill rate ({fill_rate:.1f}%) < minimum ({min_fill}%)")
        
        # Check shadow diff
        shadow_diff = self._get_shadow_diff()
        max_diff = requirements.get('max_shadow_diff_bps', 5)
        if shadow_diff > max_diff:
            reasons.append(f"Shadow diff ({shadow_diff:.2f} bps) > maximum ({max_diff} bps)")
        
        # Check readiness score
        readiness = self._get_readiness_score()
        min_readiness = requirements.get('min_readiness_score', 80)
        if readiness < min_readiness:
            reasons.append(f"Readiness score ({readiness}) < minimum ({min_readiness})")
        
        # Check consistency
        consistency = self._get_consistency_status()
        required = requirements.get('consistency_check', 'PASS')
        if consistency != required:
            reasons.append(f"Consistency check ({consistency}) != required ({required})")
        
        all_met = len(reasons) == 0
        
        return all_met, reasons
    
    def check_trading_hours(self) -> Tuple[bool, str]:
        """Check if current time is within trading hours"""
        current_time = datetime.now(self.timezone).time()
        live_hours = self.config.get('live_hours', ['10:00-18:00'])
        
        for time_range in live_hours:
            start_str, end_str = time_range.split('-')
            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))
            
            start_time = time(start_hour, start_min)
            end_time = time(end_hour, end_min)
            
            if start_time <= current_time <= end_time:
                return True, f"Within trading hours ({time_range})"
        
        return False, f"Outside trading hours (current: {current_time.strftime('%H:%M')})"
    
    def is_symbol_allowed(self, symbol: str) -> bool:
        """Check if symbol is whitelisted"""
        whitelist = self.config.get('whitelisted_symbols', [])
        return symbol in whitelist
    
    def get_limits(self) -> Dict:
        """Get current trading limits"""
        return self.config.get('limits', {
            'max_notional_tl': 1000,
            'per_trade_tl_cap': 250,
            'max_open_positions': 3,
            'daily_loss_limit_tl': 100
        })
    
    def can_go_live(self) -> Tuple[bool, Dict]:
        """Check if system can go live"""
        self.reasons = []
        status = {}
        
        # Check main switch
        if not self.config.get('enable_real_trading', False):
            self.reasons.append("Main switch (enable_real_trading) is OFF")
            status['main_switch'] = False
        else:
            status['main_switch'] = True
        
        # Check approvals
        approvals_ok, approval_reasons = self.check_approvals()
        status['approvals'] = approvals_ok
        if not approvals_ok:
            self.reasons.extend(approval_reasons)
        
        # Check requirements
        requirements_ok, requirement_reasons = self.check_requirements()
        status['requirements'] = requirements_ok
        if not requirements_ok:
            self.reasons.extend(requirement_reasons)
        
        # Check trading hours
        hours_ok, hours_msg = self.check_trading_hours()
        status['trading_hours'] = hours_ok
        if not hours_ok:
            self.reasons.append(hours_msg)
        
        # Overall decision
        can_trade = all([
            status['main_switch'],
            status['approvals'],
            status['requirements'],
            status['trading_hours']
        ])
        
        return can_trade, {
            'can_trade': can_trade,
            'status': status,
            'reasons': self.reasons,
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_paper_trades(self) -> int:
        """Get number of paper trades executed"""
        report_file = Path("logs/paper_session_report.json")
        if report_file.exists():
            with open(report_file, 'r') as f:
                report = json.load(f)
                return report.get('session', {}).get('trades_executed', 0)
        return 0
    
    def _get_fill_rate(self) -> float:
        """Get average fill rate"""
        report_file = Path("logs/paper_session_report.json")
        if report_file.exists():
            with open(report_file, 'r') as f:
                report = json.load(f)
                return report.get('fill_metrics', {}).get('maker_fill_rate', 0)
        return 0
    
    def _get_shadow_diff(self) -> float:
        """Get average shadow diff"""
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
            return sum(diffs) / len(diffs) if diffs else 0
        return 0
    
    def _get_readiness_score(self) -> int:
        """Get readiness score"""
        try:
            from tools.live_readiness import LiveReadinessChecker
            checker = LiveReadinessChecker()
            checker.run()
            return checker.readiness_score
        except:
            return 0
    
    def _get_consistency_status(self) -> str:
        """Get consistency check status"""
        try:
            from tools.consistency_check import ConsistencyChecker
            checker = ConsistencyChecker()
            passed, report = checker.check_all_sources()
            return report.get('overall', 'UNKNOWN')
        except:
            return 'UNKNOWN'
    
    def get_guard_status(self) -> Dict:
        """Get current guard status for API/dashboard"""
        can_trade, details = self.can_go_live()
        
        guard_status = {
            'live_enabled': can_trade,
            'main_switch': self.config.get('enable_real_trading', False),
            'approvals': self.config.get('approvals', {}),
            'requirements_met': details['status'].get('requirements', False),
            'in_trading_hours': details['status'].get('trading_hours', False),
            'reasons': details['reasons'],
            'limits': self.get_limits(),
            'whitelisted_symbols': self.config.get('whitelisted_symbols', []),
            'timestamp': datetime.now().isoformat()
        }
        
        return guard_status
    
    def log_decision(self, decision: str, details: Dict):
        """Log trading decision for audit"""
        if not self.config.get('audit', {}).get('log_all_decisions', True):
            return
        
        log_file = Path("logs/live_decisions.jsonl")
        log_file.parent.mkdir(exist_ok=True)
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'decision': decision,
            'details': details,
            'guard_status': self.get_guard_status()
        }
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')


# Global instance
live_switch = LiveSwitch()