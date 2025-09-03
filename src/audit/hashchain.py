"""
Hash-Chained Audit Logger
Creates tamper-evident logs with SHA256 hash chains
"""

import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class HashChainAudit:
    """Tamper-evident audit logger with hash chains"""

    def __init__(self, chain_file: str = "logs/audit_chain.jsonl"):
        self.chain_file = Path(chain_file)
        self.chain_file.parent.mkdir(exist_ok=True)
        self.chain = []
        self.last_hash = "0" * 64
        self.load_chain()
        self.session_id = hashlib.sha256(
            f"{datetime.now().isoformat()}_{time.time()}".encode()
        ).hexdigest()[:8]

    def load_chain(self):
        """Load existing chain from file"""
        if self.chain_file.exists():
            with open(self.chain_file) as f:
                for line in f:
                    try:
                        block = json.loads(line)
                        self.chain.append(block)
                        self.last_hash = block["hash"]
                    except:
                        logger.error(f"Corrupted block in chain: {line}")

    def calculate_hash(self, block_data: Dict) -> str:
        """Calculate SHA256 hash of block data"""
        data_str = json.dumps(block_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def create_block(
        self, event_type: str, event_data: Dict, metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a new block in the chain"""
        block = {
            "index": len(self.chain),
            "timestamp": datetime.now().isoformat(),
            "timestamp_unix": time.time(),
            "session_id": self.session_id,
            "event_type": event_type,
            "event_data": event_data,
            "metadata": metadata or {},
            "prev_hash": self.last_hash,
            "nonce": 0,
        }
        block["hash"] = self.calculate_hash({"prev_hash": block["prev_hash"], "data": block})
        return block

    def log_event(self, event_type: str, event_data: Dict, metadata: Optional[Dict] = None) -> str:
        """Log an audit event to the chain"""
        block = self.create_block(event_type, event_data, metadata)
        self.chain.append(block)
        self.last_hash = block["hash"]
        with open(self.chain_file, "a") as f:
            f.write(json.dumps(block) + "\n")
        return block["hash"]

    def log_trade(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
        exchange: str,
        strategy: str,
        pnl: Optional[float] = None,
    ) -> str:
        """Log a trade execution"""
        event_data = {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "price": price,
            "quantity": quantity,
            "exchange": exchange,
            "strategy": strategy,
            "pnl": pnl,
        }
        return self.log_event("TRADE", event_data)

    def log_risk_event(self, event_name: str, severity: str, details: Dict) -> str:
        """Log a risk management event"""
        event_data = {"event_name": event_name, "severity": severity, "details": details}
        return self.log_event("RISK", event_data)

    def log_config_change(
        self, parameter: str, old_value: any, new_value: any, changed_by: str
    ) -> str:
        """Log a configuration change"""
        event_data = {
            "parameter": parameter,
            "old_value": old_value,
            "new_value": new_value,
            "changed_by": changed_by,
        }
        return self.log_event("CONFIG", event_data)

    def verify_chain(self) -> tuple[bool, List[str]]:
        """Verify integrity of the entire chain"""
        errors = []
        if not self.chain:
            return (True, [])
        if self.chain[0]["prev_hash"] != "0" * 64:
            errors.append("Block 0: Invalid genesis block")
        for i in range(len(self.chain)):
            block = self.chain[i]
            calculated_hash = self.calculate_hash(
                {
                    "prev_hash": block["prev_hash"],
                    "data": {k: v for k, v in block.items() if k != "hash"},
                }
            )
            if calculated_hash != block["hash"]:
                errors.append(f"Block {i}: Hash mismatch")
            if i > 0:
                if block["prev_hash"] != self.chain[i - 1]["hash"]:
                    errors.append(f"Block {i}: Broken chain link")
        return (len(errors) == 0, errors)

    def get_events_by_type(self, event_type: str) -> List[Dict]:
        """Get all events of a specific type"""
        return [b for b in self.chain if b["event_type"] == event_type]

    def get_events_by_session(self, session_id: str) -> List[Dict]:
        """Get all events from a specific session"""
        return [b for b in self.chain if b["session_id"] == session_id]

    def get_recent_events(self, count: int = 10) -> List[Dict]:
        """Get most recent events"""
        return self.chain[-count:] if len(self.chain) >= count else self.chain

    def export_chain(self, output_file: str):
        """Export entire chain to a file"""
        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(
                {
                    "exported_at": datetime.now().isoformat(),
                    "chain_length": len(self.chain),
                    "last_hash": self.last_hash,
                    "chain": self.chain,
                },
                f,
                indent=2,
            )
        logger.info(f"Chain exported to {output_path}")

    def print_summary(self):
        """Print chain summary"""
        print("\n" + "=" * 60)
        print(" AUDIT CHAIN SUMMARY")
        print("=" * 60)
        print(f"Chain File: {self.chain_file}")
        print(f"Chain Length: {len(self.chain)} blocks")
        print(f"Last Hash: {self.last_hash[:16]}...")
        print(f"Session ID: {self.session_id}")
        valid, errors = self.verify_chain()
        if valid:
            print("Chain Integrity: [OK] VALID")
        else:
            print("Chain Integrity: [FAIL] CORRUPTED")
            for error in errors[:5]:
                print(f"  - {error}")
        event_types = {}
        for block in self.chain:
            event_type = block["event_type"]
            event_types[event_type] = event_types.get(event_type, 0) + 1
        if event_types:
            print("\nEvent Types:")
            for event_type, count in sorted(event_types.items()):
                print(f"  {event_type}: {count}")
        recent = self.get_recent_events(5)
        if recent:
            print("\nRecent Events:")
            for block in recent:
                timestamp = block["timestamp"].split("T")[1].split(".")[0]
                print(
                    f"  [{timestamp}] {block['event_type']}: {block.get('event_data', {}).get('event_name', 'N/A')}"
                )
        print("=" * 60)


class ReconciliationV2:
    """Trade reconciliation with hash verification"""

    def __init__(self, audit: HashChainAudit):
        self.audit = audit
        self.reconciliation_file = Path("reports/reconciliation.json")

    def reconcile_trades(self, exchange_trades: List[Dict], internal_trades: List[Dict]) -> Dict:
        """Reconcile trades at ID level"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "exchange_count": len(exchange_trades),
            "internal_count": len(internal_trades),
            "matched": [],
            "unmatched_exchange": [],
            "unmatched_internal": [],
            "discrepancies": [],
            "status": "PENDING",
        }
        exchange_map = {t["trade_id"]: t for t in exchange_trades}
        internal_map = {t["trade_id"]: t for t in internal_trades}
        for trade_id, internal_trade in internal_map.items():
            if trade_id in exchange_map:
                exchange_trade = exchange_map[trade_id]
                discrepancies = []
                if abs(internal_trade["price"] - exchange_trade["price"]) > 0.01:
                    discrepancies.append(
                        f"Price mismatch: {internal_trade['price']} vs {exchange_trade['price']}"
                    )
                if abs(internal_trade["quantity"] - exchange_trade["quantity"]) > 0.0001:
                    discrepancies.append(
                        f"Quantity mismatch: {internal_trade['quantity']} vs {exchange_trade['quantity']}"
                    )
                if discrepancies:
                    result["discrepancies"].append({"trade_id": trade_id, "issues": discrepancies})
                else:
                    result["matched"].append(trade_id)
                del exchange_map[trade_id]
            else:
                result["unmatched_internal"].append(trade_id)
        result["unmatched_exchange"] = list(exchange_map.keys())
        if result["discrepancies"] or result["unmatched_exchange"] or result["unmatched_internal"]:
            result["status"] = "FAILED"
            self.audit.log_risk_event(
                event_name="RECONCILIATION_FAILED",
                severity="CRITICAL",
                details={
                    "discrepancies": len(result["discrepancies"]),
                    "unmatched_exchange": len(result["unmatched_exchange"]),
                    "unmatched_internal": len(result["unmatched_internal"]),
                },
            )
        else:
            result["status"] = "PASSED"
            self.audit.log_event(
                event_type="RECONCILIATION",
                event_data={"status": "PASSED", "matched_count": len(result["matched"])},
            )
        self.save_reconciliation(result)
        return result

    def save_reconciliation(self, result: Dict):
        """Save reconciliation result"""
        self.reconciliation_file.parent.mkdir(exist_ok=True)
        with open(self.reconciliation_file, "w") as f:
            json.dump(result, f, indent=2)

    def should_pause_trading(self) -> bool:
        """Check if trading should be paused due to reconciliation failures"""
        if not self.reconciliation_file.exists():
            return False
        with open(self.reconciliation_file) as f:
            last_result = json.load(f)
        return last_result.get("status") == "FAILED"


def test_hashchain():
    """Test hash chain audit system"""
    print("=" * 60)
    print(" HASH CHAIN AUDIT TEST")
    print("=" * 60)
    audit = HashChainAudit("logs/test_audit_chain.jsonl")
    print("\nLogging events...")
    trade_hash = audit.log_trade(
        trade_id="test_001",
        symbol="BTCUSDT",
        side="buy",
        price=50000,
        quantity=0.01,
        exchange="binance",
        strategy="grid",
        pnl=10.5,
    )
    print(f"Trade logged: {trade_hash[:16]}...")
    risk_hash = audit.log_risk_event(
        event_name="POSITION_LIMIT_WARNING",
        severity="WARNING",
        details={"current": 8000, "limit": 10000},
    )
    print(f"Risk event logged: {risk_hash[:16]}...")
    config_hash = audit.log_config_change(
        parameter="min_edge_bps", old_value=10, new_value=15, changed_by="auto_calibrator"
    )
    print(f"Config change logged: {config_hash[:16]}...")
    print("\nVerifying chain integrity...")
    valid, errors = audit.verify_chain()
    if valid:
        print("[OK] Chain is valid")
    else:
        print("[FAIL] Chain corrupted:")
        for error in errors:
            print(f"  - {error}")
    audit.print_summary()
    print("\n" + "=" * 60)
    print(" RECONCILIATION TEST")
    print("=" * 60)
    reconciler = ReconciliationV2(audit)
    exchange_trades = [
        {"trade_id": "001", "price": 50000, "quantity": 0.01},
        {"trade_id": "002", "price": 50100, "quantity": 0.02},
        {"trade_id": "003", "price": 50200, "quantity": 0.015},
    ]
    internal_trades = [
        {"trade_id": "001", "price": 50000, "quantity": 0.01},
        {"trade_id": "002", "price": 50101, "quantity": 0.02},
        {"trade_id": "004", "price": 50300, "quantity": 0.01},
    ]
    result = reconciler.reconcile_trades(exchange_trades, internal_trades)
    print(f"Status: {result['status']}")
    print(f"Matched: {len(result['matched'])}")
    print(f"Discrepancies: {len(result['discrepancies'])}")
    print(f"Unmatched Exchange: {len(result['unmatched_exchange'])}")
    print(f"Unmatched Internal: {len(result['unmatched_internal'])}")
    if result["discrepancies"]:
        print("\nDiscrepancies:")
        for disc in result["discrepancies"]:
            print(f"  {disc['trade_id']}: {disc['issues']}")
    print(f"\nShould pause trading: {reconciler.should_pause_trading()}")
    print("=" * 60)


if __name__ == "__main__":
    test_hashchain()
