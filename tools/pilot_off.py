"""
Pilot Off - Emergency shutdown
Automatically triggered on anomaly/reconciliation fail/DD breach
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import logging
import sys

logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger(__name__)


class PilotOff:
    """Emergency pilot trading shutdown"""
    
    def __init__(self):
        self.config_file = Path("config/live.yaml")
        self.guard_file = Path("api/live_guard.json")
        self.anomaly_file = Path("logs/anomalies.json")
        self.telemetry_file = Path("logs/pilot_telemetry.json")
        self.trigger_log = Path("logs/pilot_triggers.json")
        
    def check_triggers(self) -> Dict:
        """Check for auto-shutdown triggers"""
        triggers = {
            "anomaly": False,
            "reconciliation": False,
            "drawdown": False,
            "manual": False
        }
        
        reasons = []
        
        # Check anomalies
        if self.check_anomaly_trigger():
            triggers["anomaly"] = True
            reasons.append("Anomaly detected")
        
        # Check reconciliation
        if self.check_reconciliation_fail():
            triggers["reconciliation"] = True
            reasons.append("Reconciliation failed")
        
        # Check drawdown breach
        dd_breach = self.check_dd_breach()
        if dd_breach:
            triggers["drawdown"] = True
            reasons.append(f"Drawdown breach: {dd_breach:.2f}%")
        
        return {
            "triggers": triggers,
            "any_triggered": any(triggers.values()),
            "reasons": reasons,
            "timestamp": datetime.now().isoformat()
        }
    
    def check_anomaly_trigger(self) -> bool:
        """Check if anomaly count exceeds threshold"""
        if not self.anomaly_file.exists():
            return False
        
        try:
            with open(self.anomaly_file, 'r') as f:
                data = json.load(f)
                counts = data.get("counts", {})
                total = sum(counts.values())
                
                # Trigger if any anomalies detected
                if total > 0:
                    logger.critical(f"ANOMALY TRIGGER: {total} anomalies detected")
                    return True
        except Exception as e:
            logger.error(f"Failed to check anomalies: {e}")
        
        return False
    
    def check_reconciliation_fail(self) -> bool:
        """Check if reconciliation failed"""
        recon_file = Path("reports/reconciliation.json")
        
        if not recon_file.exists():
            return False
        
        try:
            with open(recon_file, 'r') as f:
                data = json.load(f)
                status = data.get("status", "UNKNOWN")
                
                if status != "PASSED":
                    logger.critical(f"RECONCILIATION TRIGGER: Status={status}")
                    return True
        except Exception as e:
            logger.error(f"Failed to check reconciliation: {e}")
        
        return False
    
    def check_dd_breach(self) -> Optional[float]:
        """Check if max drawdown breached -1%"""
        if not self.telemetry_file.exists():
            return None
        
        try:
            with open(self.telemetry_file, 'r') as f:
                data = json.load(f)
                history = data.get("history", [])
                
                if not history:
                    return None
                
                # Calculate max drawdown
                pnls = []
                for entry in history:
                    pnl = entry.get("tl_pnl_live", {}).get("net_tl", 0)
                    pnls.append(pnl)
                
                if not pnls:
                    return None
                
                # Calculate running maximum and drawdown
                running_max = pnls[0]
                max_dd = 0
                
                for pnl in pnls:
                    running_max = max(running_max, pnl)
                    if running_max != 0:
                        drawdown = ((pnl - running_max) / abs(running_max)) * 100
                        max_dd = min(max_dd, drawdown)
                
                # Trigger if DD worse than -1%
                if max_dd < -1.0:
                    logger.critical(f"DRAWDOWN TRIGGER: {max_dd:.2f}% (< -1%)")
                    return max_dd
                    
        except Exception as e:
            logger.error(f"Failed to check drawdown: {e}")
        
        return None
    
    def shutdown_pilot(self, reason: str = "Manual") -> Dict:
        """Shutdown pilot trading immediately"""
        
        logger.critical(f"PILOT SHUTDOWN INITIATED: {reason}")
        
        # 1. Disable live trading config
        shutdown_result = {"config": False, "guard": False, "logged": False}
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = yaml.safe_load(f)
                
                # Force disable
                config["enable_real_trading"] = False
                config["shutdown_at"] = datetime.now().isoformat()
                config["shutdown_reason"] = reason
                config["emergency_stop"] = True
                
                with open(self.config_file, 'w') as f:
                    yaml.dump(config, f)
                
                shutdown_result["config"] = True
                logger.critical("Live config DISABLED")
                
            except Exception as e:
                logger.error(f"Failed to update config: {e}")
        
        # 2. Update live guard
        try:
            self.guard_file.parent.mkdir(exist_ok=True)
            guard_status = {
                "mode": "EMERGENCY_STOP",
                "enabled": False,
                "blockers": [f"PILOT OFF: {reason}"],
                "shutdown_at": datetime.now().isoformat(),
                "shutdown_reason": reason
            }
            
            with open(self.guard_file, 'w') as f:
                json.dump(guard_status, f, indent=2)
            
            shutdown_result["guard"] = True
            logger.critical("Live guard BLOCKED")
            
        except Exception as e:
            logger.error(f"Failed to update guard: {e}")
        
        # 3. Log trigger
        try:
            self.trigger_log.parent.mkdir(exist_ok=True)
            
            # Load existing or create new
            if self.trigger_log.exists():
                with open(self.trigger_log, 'r') as f:
                    triggers = json.load(f)
            else:
                triggers = {"history": []}
            
            # Add this trigger
            triggers["history"].append({
                "timestamp": datetime.now().isoformat(),
                "reason": reason,
                "action": "PILOT_OFF",
                "result": shutdown_result
            })
            
            # Keep last 100 triggers
            triggers["history"] = triggers["history"][-100:]
            
            with open(self.trigger_log, 'w') as f:
                json.dump(triggers, f, indent=2)
            
            shutdown_result["logged"] = True
            
        except Exception as e:
            logger.error(f"Failed to log trigger: {e}")
        
        return shutdown_result
    
    def emergency_stop(self, manual: bool = False) -> Dict:
        """Main emergency stop function"""
        
        if manual:
            # Manual trigger
            result = self.shutdown_pilot("Manual emergency stop")
            print("\n" + "="*60)
            print(" EMERGENCY STOP - MANUAL")
            print("="*60)
            print("Pilot trading has been STOPPED")
            print(f"Config disabled: {result['config']}")
            print(f"Guard blocked: {result['guard']}")
            print(f"Trigger logged: {result['logged']}")
            print("="*60)
            
        else:
            # Check auto triggers
            trigger_check = self.check_triggers()
            
            if trigger_check["any_triggered"]:
                reason = " | ".join(trigger_check["reasons"])
                result = self.shutdown_pilot(reason)
                
                print("\n" + "🚨"*30)
                print(" EMERGENCY STOP - AUTO TRIGGERED")
                print("🚨"*30)
                print(f"Triggers: {trigger_check['reasons']}")
                print(f"Timestamp: {trigger_check['timestamp']}")
                print("\nShutdown Results:")
                print(f"  Config disabled: {result['config']}")
                print(f"  Guard blocked: {result['guard']}")
                print(f"  Trigger logged: {result['logged']}")
                print("🚨"*30)
                
                # Signal to incident snapshot
                self.signal_incident_snapshot(trigger_check)
                
                return {
                    "triggered": True,
                    "triggers": trigger_check,
                    "shutdown": result
                }
            else:
                return {
                    "triggered": False,
                    "message": "No triggers detected"
                }
    
    def signal_incident_snapshot(self, trigger_data: Dict):
        """Signal incident snapshot to collect evidence"""
        signal_file = Path("logs/incident_signal.json")
        
        try:
            signal_file.parent.mkdir(exist_ok=True)
            
            signal = {
                "timestamp": datetime.now().isoformat(),
                "triggers": trigger_data,
                "action": "COLLECT_SNAPSHOT",
                "status": "PENDING"
            }
            
            with open(signal_file, 'w') as f:
                json.dump(signal, f, indent=2)
            
            logger.info(f"Incident snapshot signaled: {signal_file}")
            
        except Exception as e:
            logger.error(f"Failed to signal snapshot: {e}")
    
    def status(self) -> Dict:
        """Check pilot status"""
        status = {
            "pilot_enabled": False,
            "triggers_active": {},
            "last_shutdown": None
        }
        
        # Check if pilot is enabled
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = yaml.safe_load(f)
                    status["pilot_enabled"] = config.get("enable_real_trading", False)
                    
                    if config.get("shutdown_at"):
                        status["last_shutdown"] = {
                            "time": config["shutdown_at"],
                            "reason": config.get("shutdown_reason", "Unknown")
                        }
            except:
                pass
        
        # Check current triggers
        trigger_check = self.check_triggers()
        status["triggers_active"] = trigger_check["triggers"]
        
        return status


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pilot emergency shutdown")
    parser.add_argument("action", choices=["stop", "check", "status"],
                       help="Action to perform")
    parser.add_argument("--manual", action="store_true",
                       help="Manual emergency stop")
    
    args = parser.parse_args()
    
    pilot_off = PilotOff()
    
    if args.action == "stop":
        result = pilot_off.emergency_stop(manual=args.manual)
        if not args.manual and not result.get("triggered"):
            print("No auto-triggers detected. Use --manual for manual stop.")
            
    elif args.action == "check":
        trigger_check = pilot_off.check_triggers()
        print("\n" + "="*60)
        print(" TRIGGER CHECK")
        print("="*60)
        for trigger, active in trigger_check["triggers"].items():
            status = "⚠️ ACTIVE" if active else "✅ Clear"
            print(f"  {trigger}: {status}")
        
        if trigger_check["any_triggered"]:
            print("\n⚠️ WARNING: Auto-shutdown would trigger!")
            print(f"Reasons: {', '.join(trigger_check['reasons'])}")
        else:
            print("\n✅ All triggers clear")
        print("="*60)
        
    else:  # status
        status = pilot_off.status()
        print("\n" + "="*60)
        print(" PILOT STATUS")
        print("="*60)
        print(f"Pilot Enabled: {'YES' if status['pilot_enabled'] else 'NO'}")
        
        print("\nTrigger Status:")
        for trigger, active in status["triggers_active"].items():
            indicator = "⚠️" if active else "✅"
            print(f"  {trigger}: {indicator}")
        
        if status["last_shutdown"]:
            print("\nLast Shutdown:")
            print(f"  Time: {status['last_shutdown']['time']}")
            print(f"  Reason: {status['last_shutdown']['reason']}")
        
        print("="*60)


if __name__ == "__main__":
    main()