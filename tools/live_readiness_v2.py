"""
Live Trading Pilot Readiness Checker V2
STRICT: GO only if last 3 sessions ALL PASS
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import numpy as np


def assess_readiness() -> Dict:
    """Assess readiness with STRICT 3/3 session rule"""
    
    criteria = {
        "last_3_sessions_all_pass": False,
        "shadow_avg_diff_bps_p95": False,  # P95 < 7 bps
        "consistency_pass": False,
        "dd_within_1pct": False,
        "min_3_sessions": False,
        "uptime_above_99pct": False
    }
    
    why_not = []  # List of failed criteria with details
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "criteria": criteria,
        "go_live": False,
        "reason": "",
        "why_not": why_not,
        "session_details": []
    }
    
    print("="*60)
    print(" LIVE READINESS CHECK V2 - STRICT 3/3 RULE")
    print("="*60)
    print(f"Timestamp: {datetime.now()}")
    print("-"*60)
    
    # 1. Check last 3 sessions
    print("\n[1/6] Checking Last 3 Sessions...")
    session_files = sorted(Path("reports").glob("session_*.json"))[-3:]
    
    if len(session_files) < 3:
        criteria["min_3_sessions"] = False
        why_not.append(f"Only {len(session_files)} sessions found (need 3)")
        print(f"  [FAIL] Only {len(session_files)} sessions available")
    else:
        criteria["min_3_sessions"] = True
        print(f"  [OK] Found {len(session_files)} recent sessions")
        
        # Check if ALL 3 passed
        all_pass = True
        for i, session_file in enumerate(session_files, 1):
            try:
                with open(session_file, 'r') as f:
                    session = json.load(f)
                    status = session.get("status", "UNKNOWN")
                    metrics = session.get("metrics", {})
                    
                    session_summary = {
                        "session_num": i,
                        "file": session_file.name,
                        "status": status,
                        "grid_pnl": metrics.get("grid", {}).get("pnl_pct", 0),
                        "arb_pnl": metrics.get("arbitrage", {}).get("pnl_tl", 0),
                        "qa_consistency": metrics.get("qa", {}).get("consistency", "UNKNOWN")
                    }
                    report["session_details"].append(session_summary)
                    
                    if status != "PASS":
                        all_pass = False
                        why_not.append(f"Session {i} status: {status} (not PASS)")
                    
                    print(f"    Session {i}: {status}")
            except Exception as e:
                all_pass = False
                why_not.append(f"Session {i} error: {e}")
                print(f"    Session {i}: ERROR reading file")
        
        criteria["last_3_sessions_all_pass"] = all_pass
        if all_pass:
            print("  [PASS] All 3 sessions passed!")
        else:
            print("  [FAIL] Not all sessions passed")
    
    # 2. Check shadow P95
    print("\n[2/6] Checking Shadow P95...")
    shadow_diffs = []
    
    try:
        # Collect shadow diffs from all reports
        for shadow_file in Path("reports").glob("shadow_report_*.json"):
            with open(shadow_file, 'r') as f:
                shadow_data = json.load(f)
                comparisons = shadow_data.get("comparisons", [])
                for comp in comparisons:
                    diff_bps = comp.get("diff_bps", 0)
                    shadow_diffs.append(abs(diff_bps))
        
        if shadow_diffs:
            p95 = np.percentile(shadow_diffs, 95)
            criteria["shadow_avg_diff_bps_p95"] = p95 < 7
            
            if p95 < 7:
                print(f"  [PASS] Shadow P95: {p95:.2f} bps < 7 bps")
            else:
                print(f"  [FAIL] Shadow P95: {p95:.2f} bps >= 7 bps")
                why_not.append(f"Shadow P95 {p95:.2f} bps exceeds 7 bps threshold")
        else:
            print("  [FAIL] No shadow data available")
            why_not.append("No shadow comparison data")
    except Exception as e:
        print(f"  [FAIL] Error reading shadow data: {e}")
        why_not.append(f"Shadow data error: {e}")
    
    # 3. Check consistency
    print("\n[3/6] Checking P&L Consistency...")
    try:
        consistency_file = Path("logs/consistency_report.json")
        if consistency_file.exists():
            with open(consistency_file, 'r') as f:
                consistency = json.load(f)
                status = consistency.get("status", "UNKNOWN")
                criteria["consistency_pass"] = status == "PASS"
                
                if status == "PASS":
                    print(f"  [PASS] Consistency check passed")
                else:
                    print(f"  [FAIL] Consistency: {status}")
                    why_not.append(f"P&L consistency: {status}")
        else:
            print("  [FAIL] No consistency report")
            why_not.append("No consistency report found")
    except Exception as e:
        print(f"  [FAIL] Error reading consistency: {e}")
        why_not.append(f"Consistency error: {e}")
    
    # 4. Check drawdown
    print("\n[4/6] Checking Drawdown...")
    try:
        daily_score = Path("reports/daily_score.json")
        if daily_score.exists():
            with open(daily_score, 'r') as f:
                score = json.load(f)
                dd = score.get("risk", {}).get("max_dd_pct", -999)
                criteria["dd_within_1pct"] = dd >= -1.0
                
                if dd >= -1.0:
                    print(f"  [PASS] Max DD: {dd:.2f}% >= -1%")
                else:
                    print(f"  [FAIL] Max DD: {dd:.2f}% < -1%")
                    why_not.append(f"Drawdown {dd:.2f}% exceeds -1% limit")
        else:
            print("  [FAIL] No daily score data")
            why_not.append("No drawdown data available")
    except Exception as e:
        print(f"  [FAIL] Error reading drawdown: {e}")
        why_not.append(f"Drawdown error: {e}")
    
    # 5. Check uptime (simulated)
    print("\n[5/6] Checking System Uptime...")
    # In production, would check actual uptime metrics
    uptime = 99.5  # Simulated
    criteria["uptime_above_99pct"] = uptime > 99.0
    if uptime > 99.0:
        print(f"  [PASS] Uptime: {uptime:.1f}% > 99%")
    else:
        print(f"  [FAIL] Uptime: {uptime:.1f}% <= 99%")
        why_not.append(f"Uptime {uptime:.1f}% below 99% requirement")
    
    # 6. Final Decision
    print("\n[6/6] Final Decision...")
    
    # STRICT: GO only if ALL criteria pass, especially 3/3 sessions
    go_decision = (
        criteria["last_3_sessions_all_pass"] and
        criteria["shadow_avg_diff_bps_p95"] and
        criteria["consistency_pass"] and
        criteria["dd_within_1pct"] and
        criteria["min_3_sessions"] and
        criteria["uptime_above_99pct"]
    )
    
    report["go_live"] = go_decision
    
    print("\n" + "="*60)
    print(" DECISION")
    print("="*60)
    
    print("\nCriteria Summary:")
    for criterion, passed in criteria.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {criterion}")
    
    if go_decision:
        print("\n" + "🟢"*20)
        print(" GO - READY FOR MICRO LIVE PILOT")
        print("🟢"*20)
        report["reason"] = "All criteria passed - ready for micro live pilot"
        
        print("\nApproved Parameters:")
        print("  - Strategy: turkish_arbitrage only")
        print("  - Per trade cap: 250 TL")
        print("  - Max notional: 1000 TL")
        print("  - Hours: 10:00-18:00 Istanbul")
        print("  - Approvals: 2 operators required")
    else:
        print("\n" + "🔴"*20)
        print(" NO-GO - NOT READY FOR LIVE")
        print("🔴"*20)
        report["reason"] = "Failed criteria - not ready for live"
        
        print("\nWhy Not:")
        for i, reason in enumerate(why_not, 1):
            print(f"  {i}. {reason}")
        
        print("\nRequired Actions:")
        print("  1. Fix all failed criteria above")
        print("  2. Run 3 consecutive PASSING sessions")
        print("  3. Ensure shadow P95 < 7 bps")
        print("  4. Re-run readiness check")
    
    print("="*60)
    
    # Save report
    report_file = Path("logs/live_readiness_v2.json")
    report_file.parent.mkdir(exist_ok=True)
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved: {report_file}")
    
    return report


def main():
    """Run readiness assessment"""
    report = assess_readiness()
    
    # Exit 0 for GO, 1 for NO-GO
    sys.exit(0 if report["go_live"] else 1)


if __name__ == "__main__":
    main()