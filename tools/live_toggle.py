"""
Live Trading Toggle
Enable/disable micro-live trading with strict controls
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LiveToggle:
    """Control live trading activation"""

    def __init__(self):
        self.config_file = Path("config/live.yaml")
        self.readiness_file = Path("reports/live_readiness_v2.json")
        self.approval_file = Path("config/approvals.json")

    def check_readiness(self) -> bool:
        """Check if GO decision exists"""
        if not self.readiness_file.exists():
            logger.error("No readiness report found - run live_readiness_v2.py first")
            return False

        try:
            with open(self.readiness_file) as f:
                report = json.load(f)
                decision = report.get("decision", "NO-GO")

                if decision != "GO":
                    logger.error(f"Readiness check: {decision}")
                    logger.error("System is not ready for live trading")

                    # Show why not
                    why_not = report.get("why_not", [])
                    if why_not:
                        logger.error("Reasons:")
                        for reason in why_not:
                            logger.error(f"  - {reason}")

                    return False

                logger.info("Readiness check: GO ✓")
                return True
        except Exception as e:
            logger.error(f"Failed to check readiness: {e}")
            return False

    def check_approvals(self) -> bool:
        """Check two-man approval"""
        if not self.approval_file.exists():
            logger.warning("No approvals file - creating template")
            self.create_approval_template()
            return False

        try:
            with open(self.approval_file) as f:
                approvals = json.load(f)

                operator_a = approvals.get("operator_A", {})
                operator_b = approvals.get("operator_B", {})

                # Check both operators approved
                if not operator_a.get("approved", False):
                    logger.error("Operator A has not approved")
                    return False

                if not operator_b.get("approved", False):
                    logger.error("Operator B has not approved")
                    return False

                # Check approval timestamps (within 24 hours)
                now = datetime.now()

                for operator in ["operator_A", "operator_B"]:
                    timestamp_str = approvals[operator].get("timestamp", "")
                    if timestamp_str:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        age_hours = (now - timestamp).total_seconds() / 3600

                        if age_hours > 24:
                            logger.error(f"{operator} approval expired ({age_hours:.1f} hours old)")
                            return False

                logger.info("Two-man approval: Valid ✓")
                return True

        except Exception as e:
            logger.error(f"Failed to check approvals: {e}")
            return False

    def create_approval_template(self):
        """Create approval template file"""
        template = {
            "operator_A": {
                "approved": False,
                "name": "",
                "timestamp": "",
                "comment": "Set approved=true and add your name",
            },
            "operator_B": {
                "approved": False,
                "name": "",
                "timestamp": "",
                "comment": "Set approved=true and add your name",
            },
        }

        self.approval_file.parent.mkdir(exist_ok=True)
        with open(self.approval_file, "w") as f:
            json.dump(template, f, indent=2)

        logger.info(f"Created approval template: {self.approval_file}")
        logger.info("Both operators must set approved=true")

    def enable_live(self, warmup: bool = False):
        """Enable live trading"""

        # Check prerequisites
        if not self.check_readiness():
            logger.error("Cannot enable live - readiness check failed")
            sys.exit(1)

        if not self.check_approvals():
            logger.error("Cannot enable live - approvals missing")
            sys.exit(1)

        # Create live configuration
        config = {
            "enable_real_trading": True,
            "whitelisted_strategies": ["turkish_arbitrage"],
            "per_trade_tl_cap": 100 if warmup else 250,
            "max_notional_tl": 500 if warmup else 1000,
            "live_hours": ["10:00-18:00 Europe/Istanbul"],
            "approvals": {"operator_A": True, "operator_B": True},
            "warmup_mode": warmup,
            "enabled_at": datetime.now().isoformat(),
            "pilot_mode": True,
            "safety": {
                "auto_pause_on_anomaly": True,
                "auto_pause_on_dd_breach": True,
                "max_dd_threshold": -1.0,
                "require_reconciliation": True,
            },
        }

        # Save configuration
        self.config_file.parent.mkdir(exist_ok=True)
        with open(self.config_file, "w") as f:
            yaml.dump(config, f)

        logger.info("=" * 60)
        logger.info(" LIVE TRADING ENABLED")
        logger.info("=" * 60)
        logger.info(f"Mode: {'WARMUP' if warmup else 'NORMAL'}")
        logger.info(f"Per trade cap: {config['per_trade_tl_cap']} TL")
        logger.info(f"Max notional: {config['max_notional_tl']} TL")
        logger.info(f"Strategy: {config['whitelisted_strategies']}")
        logger.info(f"Hours: {config['live_hours']}")
        logger.info("=" * 60)

        # Create live guard status
        self.update_live_guard(config)

        return config

    def disable_live(self):
        """Disable live trading"""

        if not self.config_file.exists():
            logger.info("Live trading already disabled")
            return

        # Load current config
        with open(self.config_file) as f:
            config = yaml.safe_load(f)

        # Disable
        config["enable_real_trading"] = False
        config["disabled_at"] = datetime.now().isoformat()

        # Save
        with open(self.config_file, "w") as f:
            yaml.dump(config, f)

        logger.info("Live trading DISABLED")

        # Update live guard
        self.update_live_guard(config)

    def update_live_guard(self, config: Dict):
        """Update live guard status for UI"""

        guard_file = Path("api/live_guard.json")
        guard_file.parent.mkdir(exist_ok=True)

        guard_status = {
            "mode": "PILOT" if config.get("enable_real_trading") else "OFF",
            "enabled": config.get("enable_real_trading", False),
            "warmup": config.get("warmup_mode", False),
            "blockers": [],
            "caps": {
                "per_trade_tl": config.get("per_trade_tl_cap", 0),
                "max_notional_tl": config.get("max_notional_tl", 0),
            },
            "hours": config.get("live_hours", []),
            "strategies": config.get("whitelisted_strategies", []),
            "timestamp": datetime.now().isoformat(),
        }

        # Check for blockers
        if not config.get("enable_real_trading"):
            guard_status["blockers"].append("Trading disabled")

        # Check time window
        now = datetime.now()
        hour = now.hour
        if hour < 10 or hour >= 18:
            guard_status["blockers"].append(f"Outside trading hours (current: {hour}:00)")

        with open(guard_file, "w") as f:
            json.dump(guard_status, f, indent=2)

        logger.info(f"Live guard updated: {guard_file}")

    def status(self):
        """Show current live trading status"""

        print("\n" + "=" * 60)
        print(" LIVE TRADING STATUS")
        print("=" * 60)

        # Check config
        if self.config_file.exists():
            with open(self.config_file) as f:
                config = yaml.safe_load(f)

                enabled = config.get("enable_real_trading", False)
                print(f"Status: {'ENABLED' if enabled else 'DISABLED'}")

                if enabled:
                    print(f"Mode: {'WARMUP' if config.get('warmup_mode') else 'NORMAL'}")
                    print(f"Per trade cap: {config.get('per_trade_tl_cap')} TL")
                    print(f"Max notional: {config.get('max_notional_tl')} TL")
                    print(f"Strategies: {config.get('whitelisted_strategies')}")
                    print(f"Hours: {config.get('live_hours')}")
                    print(f"Enabled at: {config.get('enabled_at')}")
        else:
            print("Status: DISABLED (no config)")

        # Check readiness
        print("\nReadiness:")
        if self.readiness_file.exists():
            with open(self.readiness_file) as f:
                report = json.load(f)
                decision = report.get("decision", "NO-GO")
                print(f"  Last check: {decision}")

                if decision == "NO-GO":
                    print("  Failed criteria:")
                    for reason in report.get("why_not", [])[:3]:
                        print(f"    - {reason}")
        else:
            print("  No readiness check performed")

        # Check approvals
        print("\nApprovals:")
        if self.approval_file.exists():
            with open(self.approval_file) as f:
                approvals = json.load(f)

                for operator in ["operator_A", "operator_B"]:
                    approved = approvals[operator].get("approved", False)
                    name = approvals[operator].get("name", "Unknown")
                    status = "✓" if approved else "✗"
                    print(f"  {operator}: {status} {name if approved else 'Not approved'}")
        else:
            print("  No approvals file")

        print("=" * 60)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Control live trading")
    parser.add_argument("action", choices=["on", "off", "status"], help="Action to perform")
    parser.add_argument("--warmup", action="store_true", help="Enable warmup mode (lower caps)")

    args = parser.parse_args()

    toggle = LiveToggle()

    if args.action == "on":
        toggle.enable_live(warmup=args.warmup)
    elif args.action == "off":
        toggle.disable_live()
    else:
        toggle.status()


if __name__ == "__main__":
    main()
