"""
Adaptive Execution Controller
Automatically tunes join/step-in parameters based on fill rate and shadow diff
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import statistics


class AdaptiveController:
    """Adaptive controller for execution parameters"""
    
    def __init__(self):
        self.target_fill_rate = 0.60  # 60% maker fill rate target
        self.target_shadow_diff = 5.0  # 5 bps max shadow diff
        self.history_sessions = 3  # Look at last 3 sessions
        
    def load_recent_metrics(self) -> Tuple[float, float]:
        """Load recent session metrics"""
        fill_rates = []
        shadow_diffs = []
        
        # Load paper metrics
        metrics_file = Path("logs/paper_metrics.json")
        if metrics_file.exists():
            with open(metrics_file, 'r') as f:
                metrics = json.load(f)
                if 'sessions' in metrics:
                    recent_sessions = metrics['sessions'][-self.history_sessions:]
                    for session in recent_sessions:
                        if 'maker_fill_rate' in session:
                            fill_rates.append(session['maker_fill_rate'])
                            
        # Load shadow diffs
        shadow_file = Path("logs/shadow_diff.jsonl")
        if shadow_file.exists():
            recent_diffs = []
            with open(shadow_file, 'r') as f:
                for line in f:
                    try:
                        diff = json.loads(line)
                        recent_diffs.append(diff.get('price_diff_bps', 0))
                    except:
                        continue
                        
            if recent_diffs:
                # Take last N samples
                recent_diffs = recent_diffs[-100:]
                shadow_diffs = [statistics.mean(recent_diffs)]
                
        avg_fill_rate = statistics.mean(fill_rates) if fill_rates else 0
        avg_shadow_diff = statistics.mean(shadow_diffs) if shadow_diffs else 0
        
        return avg_fill_rate, avg_shadow_diff
        
    def calculate_adjustments(self, fill_rate: float, shadow_diff: float) -> Dict:
        """Calculate parameter adjustments"""
        adjustments = {}
        
        # Load current config
        config_file = Path("config/execution.yaml")
        if config_file.exists():
            with open(config_file, 'r') as f:
                current_config = yaml.safe_load(f)
        else:
            current_config = {
                'step_in_k': 1,
                'min_edge_bps': 5
            }
            
        step_in_k = current_config.get('step_in_k', 1)
        min_edge_bps = current_config.get('min_edge_bps', 5)
        
        # Adjust step_in_k based on fill rate and shadow diff
        if fill_rate < 0.55 and shadow_diff < 5:
            # Low fill rate, good price accuracy -> be more aggressive
            step_in_k = min(step_in_k + 1, 3)
            adjustments['step_in_k'] = {
                'old': current_config.get('step_in_k', 1),
                'new': step_in_k,
                'reason': 'Low fill rate with good price accuracy'
            }
            
        elif fill_rate > 0.70 or shadow_diff > 6:
            # High fill rate or poor price accuracy -> be less aggressive
            step_in_k = max(step_in_k - 1, 0)
            adjustments['step_in_k'] = {
                'old': current_config.get('step_in_k', 1),
                'new': step_in_k,
                'reason': 'High fill rate or poor price accuracy'
            }
            
        # Adjust min_edge_bps
        if fill_rate < 0.50:
            # Very low fill rate -> reduce minimum edge requirement
            min_edge_bps = max(min_edge_bps - 1, 3)
            adjustments['min_edge_bps'] = {
                'old': current_config.get('min_edge_bps', 5),
                'new': min_edge_bps,
                'reason': 'Very low fill rate'
            }
            
        elif fill_rate > 0.75 and shadow_diff < 3:
            # High fill rate with excellent accuracy -> can require more edge
            min_edge_bps = min(min_edge_bps + 1, 10)
            adjustments['min_edge_bps'] = {
                'old': current_config.get('min_edge_bps', 5),
                'new': min_edge_bps,
                'reason': 'High fill rate with excellent accuracy'
            }
            
        return adjustments
        
    def apply_adjustments(self, adjustments: Dict) -> bool:
        """Apply adjustments to config file"""
        if not adjustments:
            return False
            
        config_file = Path("config/execution.yaml")
        
        # Load current config
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
        else:
            config = {}
            
        # Apply adjustments
        for param, adjustment in adjustments.items():
            config[param] = adjustment['new']
            
        # Save updated config
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
            
        # Log changes
        self.log_changes(adjustments)
        
        return True
        
    def log_changes(self, adjustments: Dict):
        """Log parameter changes"""
        log_file = Path("logs/adaptive_changes.json")
        log_file.parent.mkdir(exist_ok=True)
        
        # Load existing log
        if log_file.exists():
            with open(log_file, 'r') as f:
                log = json.load(f)
        else:
            log = []
            
        # Add new entry
        entry = {
            'timestamp': datetime.now().isoformat(),
            'adjustments': adjustments
        }
        log.append(entry)
        
        # Keep last 100 entries
        log = log[-100:]
        
        # Save log
        with open(log_file, 'w') as f:
            json.dump(log, f, indent=2)
            
    def run(self) -> Dict:
        """Run adaptive control cycle"""
        print("=" * 60)
        print("ADAPTIVE EXECUTION CONTROLLER")
        print("=" * 60)
        
        # Load metrics
        fill_rate, shadow_diff = self.load_recent_metrics()
        
        print(f"Recent Metrics:")
        print(f"  Avg Fill Rate: {fill_rate:.1%}")
        print(f"  Avg Shadow Diff: {shadow_diff:.2f} bps")
        print(f"\nTargets:")
        print(f"  Fill Rate: ≥{self.target_fill_rate:.1%}")
        print(f"  Shadow Diff: ≤{self.target_shadow_diff:.1f} bps")
        
        # Calculate adjustments
        adjustments = self.calculate_adjustments(fill_rate, shadow_diff)
        
        if adjustments:
            print("\nAdjustments:")
            for param, adj in adjustments.items():
                print(f"  {param}: {adj['old']} → {adj['new']}")
                print(f"    Reason: {adj['reason']}")
                
            # Apply adjustments
            self.apply_adjustments(adjustments)
            print("\n[APPLIED] Configuration updated")
        else:
            print("\n[NO CHANGE] Parameters within acceptable range")
            
        print("=" * 60)
        
        return {
            'metrics': {
                'fill_rate': fill_rate,
                'shadow_diff': shadow_diff
            },
            'adjustments': adjustments
        }