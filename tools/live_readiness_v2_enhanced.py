"""
Live Readiness v2 - Strict GO/NO-GO Gate
GO only if ALL 3 sessions pass AND p95 shadow < 7 bps
Enhanced version with detailed criteria
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LiveReadinessV2:
    """Strict GO/NO-GO gate for live trading"""
    
    def __init__(self):
        self.criteria = {
            "last_3_sessions_all_pass": False,
            "shadow_avg_below_5bps": False,
            "shadow_p95_below_7bps": False,
            "grid_fill_rate_ok": False,
            "grid_time_to_fill_ok": False,
            "grid_pnl_positive": False,
            "arb_pnl_positive": False,
            "arb_success_rate_ok": False,
            "arb_latency_ok": False,
            "risk_max_dd_ok": False,
            "anomaly_count_zero": False,
            "reconciliation_clean": False
        }
        
        self.why_not = []
        self.decision = "NO-GO"
    
    def load_campaign_data(self) -> Dict:
        """Load campaign results"""
        campaign_file = Path("reports/quick_campaign.json")
        
        if not campaign_file.exists():
            self.why_not.append("No campaign data found (reports/quick_campaign.json missing)")
            return {}
        
        try:
            with open(campaign_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.why_not.append(f"Failed to load campaign data: {e}")
            return {}
    
    def check_sessions(self, campaign_data: Dict) -> Tuple[bool, List[str]]:
        """Check if all 3 sessions passed"""
        sessions = campaign_data.get("sessions", [])
        
        if len(sessions) < 3:
            return False, [f"Only {len(sessions)}/3 sessions found"]
        
        # Get last 3 sessions
        last_3 = sessions[-3:]
        
        failures = []
        all_pass = True
        
        for i, session in enumerate(last_3, 1):
            if session.get("status") != "PASS":
                all_pass = False
                failures.append(f"Session {i} failed: {session.get('status', 'UNKNOWN')}")
        
        return all_pass, failures
    
    def check_shadow_metrics(self, campaign_data: Dict) -> Tuple[bool, bool, List[str]]:
        """Check shadow trading metrics"""
        sessions = campaign_data.get("sessions", [])
        
        if not sessions:
            return False, False, ["No sessions to check shadow metrics"]
        
        issues = []
        avg_ok = True
        p95_ok = True
        
        for session in sessions[-3:]:
            metrics = session.get("metrics", {})
            qa = metrics.get("qa", {})
            
            shadow_avg = qa.get("shadow_avg_diff_bps", 999)
            shadow_p95 = qa.get("shadow_p95_bps", 999)
            
            if shadow_avg >= 5:
                avg_ok = False
                issues.append(f"Session {session.get('session_num', '?')}: shadow_avg={shadow_avg:.1f} bps (≥5)")
            
            if shadow_p95 >= 7:
                p95_ok = False
                issues.append(f"Session {session.get('session_num', '?')}: shadow_p95={shadow_p95:.1f} bps (≥7)")
        
        return avg_ok, p95_ok, issues
    
    def check_grid_criteria(self, campaign_data: Dict) -> Dict[str, Tuple[bool, str]]:
        """Check grid trading criteria"""
        results = {}
        sessions = campaign_data.get("sessions", [])
        
        # Check fill rate ≥ 0.60
        fill_rates = []
        for s in sessions:
            if "grid" in s.get("metrics", {}):
                fill_rates.append(s["metrics"]["grid"].get("maker_fill_rate", 0) / 100)
        
        if fill_rates:
            avg_fill_rate = sum(fill_rates) / len(fill_rates)
            results["fill_rate"] = (
                avg_fill_rate >= 0.60,
                f"Avg fill rate: {avg_fill_rate:.2%} {'✓' if avg_fill_rate >= 0.60 else '✗ (<60%)'}"
            )
        else:
            results["fill_rate"] = (False, "No grid fill rate data")
        
        # Check time to fill < 20s
        fill_times = []
        for s in sessions:
            if "grid" in s.get("metrics", {}):
                fill_times.append(s["metrics"]["grid"].get("avg_fill_time_ms", 99999) / 1000)
        
        if fill_times:
            avg_fill_time = sum(fill_times) / len(fill_times)
            results["time_to_fill"] = (
                avg_fill_time < 20,
                f"Avg fill time: {avg_fill_time:.1f}s {'✓' if avg_fill_time < 20 else '✗ (≥20s)'}"
            )
        else:
            results["time_to_fill"] = (False, "No fill time data")
        
        # Check P&L > 0
        pnls = []
        for s in sessions:
            if "grid" in s.get("metrics", {}):
                pnls.append(s["metrics"]["grid"].get("pnl_pct", -999))
        
        if pnls:
            avg_pnl = sum(pnls) / len(pnls)
            results["pnl"] = (
                avg_pnl > 0,
                f"Avg P&L: {avg_pnl:.2f}% {'✓' if avg_pnl > 0 else '✗ (≤0%)'}"
            )
        else:
            results["pnl"] = (False, "No grid P&L data")
        
        return results
    
    def check_arb_criteria(self, campaign_data: Dict) -> Dict[str, Tuple[bool, str]]:
        """Check arbitrage criteria"""
        results = {}
        sessions = campaign_data.get("sessions", [])
        
        # Check TL P&L ≥ 0
        pnls = []
        for s in sessions:
            if "arbitrage" in s.get("metrics", {}):
                pnls.append(s["metrics"]["arbitrage"].get("pnl_tl", -999))
        
        if pnls:
            total_pnl = sum(pnls)
            results["pnl"] = (
                total_pnl >= 0,
                f"Total P&L: {total_pnl:.2f} TL {'✓' if total_pnl >= 0 else '✗ (<0)'}"
            )
        else:
            results["pnl"] = (False, "No arbitrage P&L data")
        
        # Check success rate ≥ 0.55
        success_rates = []
        for s in sessions:
            if "arbitrage" in s.get("metrics", {}):
                success_rates.append(s["metrics"]["arbitrage"].get("success_rate", 0) / 100)
        
        if success_rates:
            avg_success = sum(success_rates) / len(success_rates)
            results["success_rate"] = (
                avg_success >= 0.55,
                f"Avg success: {avg_success:.2%} {'✓' if avg_success >= 0.55 else '✗ (<55%)'}"
            )
        else:
            results["success_rate"] = (False, "No success rate data")
        
        # Check latency p50 < 250ms
        latencies = []
        for s in sessions:
            if "latency" in s.get("metrics", {}):
                latencies.append(s["metrics"]["latency"].get("p50", 9999))
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            results["latency"] = (
                avg_latency < 250,
                f"Avg latency p50: {avg_latency:.0f}ms {'✓' if avg_latency < 250 else '✗ (≥250ms)'}"
            )
        else:
            results["latency"] = (False, "No latency data")
        
        return results
    
    def check_risk_criteria(self, campaign_data: Dict) -> Tuple[bool, str]:
        """Check risk criteria: max DD ≥ -1.0%"""
        sessions = campaign_data.get("sessions", [])
        
        max_dds = []
        for s in sessions:
            if "risk" in s.get("metrics", {}):
                max_dds.append(s["metrics"]["risk"].get("max_dd_pct", -999))
        
        if max_dds:
            worst_dd = min(max_dds)
            return (
                worst_dd >= -1.0,
                f"Worst DD: {worst_dd:.2f}% {'✓' if worst_dd >= -1.0 else '✗ (<-1%)'}"
            )
        
        return False, "No max drawdown data"
    
    def check_anomalies(self) -> Tuple[bool, str]:
        """Check for anomalies"""
        anomaly_file = Path("logs/anomalies.json")
        
        if not anomaly_file.exists():
            return True, "No anomaly log (assuming clean)"
        
        try:
            with open(anomaly_file, 'r') as f:
                data = json.load(f)
                counts = data.get("counts", {})
                total = sum(counts.values())
                return (total == 0, f"Anomalies: {total}")
        except:
            return False, "Failed to read anomaly data"
    
    def check_reconciliation(self) -> Tuple[bool, str]:
        """Check reconciliation status"""
        recon_file = Path("reports/reconciliation.json")
        
        if not recon_file.exists():
            return False, "No reconciliation report"
        
        try:
            with open(recon_file, 'r') as f:
                data = json.load(f)
                status = data.get("status", "UNKNOWN")
                return (status == "PASSED", f"Reconciliation: {status}")
        except:
            return False, "Failed to read reconciliation"
    
    def evaluate(self) -> Dict:
        """Evaluate all criteria for GO/NO-GO decision"""
        
        # Load campaign data
        campaign_data = self.load_campaign_data()
        
        if not campaign_data:
            self.decision = "NO-GO"
            return self.generate_report()
        
        # 1. Check all 3 sessions pass
        all_pass, session_failures = self.check_sessions(campaign_data)
        self.criteria["last_3_sessions_all_pass"] = all_pass
        if not all_pass:
            self.why_not.extend(session_failures)
        
        # 2. Check shadow metrics
        avg_ok, p95_ok, shadow_issues = self.check_shadow_metrics(campaign_data)
        self.criteria["shadow_avg_below_5bps"] = avg_ok
        self.criteria["shadow_p95_below_7bps"] = p95_ok
        if not avg_ok or not p95_ok:
            self.why_not.extend(shadow_issues)
        
        # 3. Check grid criteria
        grid_results = self.check_grid_criteria(campaign_data)
        self.criteria["grid_fill_rate_ok"] = grid_results.get("fill_rate", (False, ""))[0]
        self.criteria["grid_time_to_fill_ok"] = grid_results.get("time_to_fill", (False, ""))[0]
        self.criteria["grid_pnl_positive"] = grid_results.get("pnl", (False, ""))[0]
        
        for key, (passed, msg) in grid_results.items():
            if not passed:
                self.why_not.append(f"Grid: {msg}")
        
        # 4. Check arbitrage criteria
        arb_results = self.check_arb_criteria(campaign_data)
        self.criteria["arb_pnl_positive"] = arb_results.get("pnl", (False, ""))[0]
        self.criteria["arb_success_rate_ok"] = arb_results.get("success_rate", (False, ""))[0]
        self.criteria["arb_latency_ok"] = arb_results.get("latency", (False, ""))[0]
        
        for key, (passed, msg) in arb_results.items():
            if not passed:
                self.why_not.append(f"Arb: {msg}")
        
        # 5. Check risk criteria
        risk_ok, risk_msg = self.check_risk_criteria(campaign_data)
        self.criteria["risk_max_dd_ok"] = risk_ok
        if not risk_ok:
            self.why_not.append(f"Risk: {risk_msg}")
        
        # 6. Check anomalies
        anomaly_ok, anomaly_msg = self.check_anomalies()
        self.criteria["anomaly_count_zero"] = anomaly_ok
        if not anomaly_ok:
            self.why_not.append(anomaly_msg)
        
        # 7. Check reconciliation
        recon_ok, recon_msg = self.check_reconciliation()
        self.criteria["reconciliation_clean"] = recon_ok
        if not recon_ok:
            self.why_not.append(recon_msg)
        
        # Final decision: GO only if ALL criteria pass
        self.decision = "GO" if all(self.criteria.values()) else "NO-GO"
        
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """Generate readiness report"""
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "decision": self.decision,
            "criteria": self.criteria,
            "why_not": self.why_not,
            "summary": {
                "total_criteria": len(self.criteria),
                "passed": sum(self.criteria.values()),
                "failed": len(self.criteria) - sum(self.criteria.values())
            }
        }
        
        # Save report
        report_file = Path("reports/live_readiness_v2.json")
        report_file.parent.mkdir(exist_ok=True)
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def print_report(self, report: Dict):
        """Print readiness report"""
        
        print("\n" + "="*60)
        print(" LIVE READINESS CHECK V2 - STRICT GATE")
        print("="*60)
        print(f"Timestamp: {report['timestamp']}")
        print(f"Decision: {report['decision']}")
        
        # Show criteria
        print("\nCriteria Status:")
        for criterion, passed in report["criteria"].items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status} | {criterion}")
        
        # Show summary
        summary = report["summary"]
        print(f"\nSummary: {summary['passed']}/{summary['total_criteria']} passed")
        
        # Show why not (if NO-GO)
        if report["decision"] == "NO-GO" and report["why_not"]:
            print("\nDetailed Failures (why_not):")
            for i, reason in enumerate(report["why_not"], 1):
                print(f"  {i}. {reason}")
        
        # Final message
        if report["decision"] == "GO":
            print("\n🟢 GO - System is ready for live trading")
            print("\nApproved Settings:")
            print("  • Strategy: turkish_arbitrage only")
            print("  • Per trade cap: 250 TL") 
            print("  • Max notional: 1000 TL")
            print("  • Trading hours: 10:00-18:00 Istanbul")
        else:
            print("\n🔴 NO-GO - System is NOT ready")
            print("\nRequired Actions:")
            print("  1. Fix all failed criteria")
            print("  2. Ensure ALL 3 sessions PASS")
            print("  3. Shadow p95 must be < 7 bps")
            print("  4. Re-run campaign and check again")
        
        print("="*60)


def main():
    """Run live readiness check"""
    
    checker = LiveReadinessV2()
    report = checker.evaluate()
    checker.print_report(report)
    
    # Exit code: 0 for GO, 1 for NO-GO
    sys.exit(0 if report["decision"] == "GO" else 1)


if __name__ == "__main__":
    main()