"""
Database models for Sofia V2 real-data trading system.
"""

import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import os

logger = logging.getLogger(__name__)

class SofiaDatabase:
    """SQLite database for Sofia V2 trading system."""
    
    def __init__(self, db_path: str = "sofia.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Account state table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_balance REAL NOT NULL,
                total_equity REAL NOT NULL,
                total_pnl REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity REAL NOT NULL,
                avg_entry_price REAL NOT NULL,
                realized_pnl REAL NOT NULL DEFAULT 0.0,
                total_fees REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                value REAL NOT NULL,
                fees REAL NOT NULL,
                strategy TEXT,
                executed_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Price snapshots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                source TEXT NOT NULL,
                freshness_seconds REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database initialized: {self.db_path}")
    
    def seed_initial_balance(self, balance: float = 100000.0):
        """Seed initial account balance."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if already seeded
        cursor.execute("SELECT COUNT(*) FROM account_state")
        if cursor.fetchone()[0] > 0:
            logger.info("Database already seeded")
            conn.close()
            return
        
        # Insert initial state
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
            INSERT INTO account_state (cash_balance, total_equity, total_pnl, created_at, updated_at)
            VALUES (?, ?, 0.0, ?, ?)
        ''', (balance, balance, now, now))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database seeded with ${balance:,.2f} initial balance")
    
    def get_account_state(self) -> Optional[Dict]:
        """Get current account state."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT cash_balance, total_equity, total_pnl, updated_at 
            FROM account_state 
            ORDER BY id DESC LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "cash_balance": row[0],
                "total_equity": row[1],
                "total_pnl": row[2],
                "updated_at": row[3]
            }
        return None
    
    def update_account_state(self, cash_balance: float, total_equity: float, total_pnl: float):
        """Update account state."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
            INSERT INTO account_state (cash_balance, total_equity, total_pnl, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (cash_balance, total_equity, total_pnl, now, now))
        
        conn.commit()
        conn.close()
    
    def get_positions(self) -> Dict:
        """Get all active positions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT symbol, quantity, avg_entry_price, realized_pnl, total_fees, updated_at
            FROM positions 
            WHERE quantity != 0
        ''')
        
        positions = {}
        for row in cursor.fetchall():
            symbol, quantity, avg_entry_price, realized_pnl, total_fees, updated_at = row
            positions[symbol] = {
                "quantity": quantity,
                "avg_entry_price": avg_entry_price,
                "realized_pnl": realized_pnl,
                "total_fees": total_fees,
                "updated_at": updated_at
            }
        
        conn.close()
        return positions
    
    def update_position(self, symbol: str, quantity: float, avg_entry_price: float, 
                       realized_pnl: float = 0.0, fees: float = 0.0):
        """Update or create position."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute('''
            INSERT OR REPLACE INTO positions 
            (symbol, quantity, avg_entry_price, realized_pnl, total_fees, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 
                    COALESCE((SELECT created_at FROM positions WHERE symbol = ?), ?), 
                    ?)
        ''', (symbol, quantity, avg_entry_price, realized_pnl, fees, symbol, now, now))
        
        conn.commit()
        conn.close()
    
    def add_trade(self, trade_id: str, symbol: str, side: str, quantity: float, 
                  price: float, fees: float, strategy: str = "manual"):
        """Add trade to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        value = quantity * price
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute('''
            INSERT INTO trades 
            (trade_id, symbol, side, quantity, price, value, fees, strategy, executed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (trade_id, symbol, side, quantity, price, value, fees, strategy, now, now))
        
        conn.commit()
        conn.close()
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent trades."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT trade_id, symbol, side, quantity, price, value, fees, strategy, executed_at
            FROM trades 
            ORDER BY executed_at DESC 
            LIMIT ?
        ''', (limit,))
        
        trades = []
        for row in cursor.fetchall():
            trade_id, symbol, side, quantity, price, value, fees, strategy, executed_at = row
            trades.append({
                "trade_id": trade_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "value": value,
                "fees": fees,
                "strategy": strategy,
                "executed_at": executed_at
            })
        
        conn.close()
        return trades
    
    def reset_database(self):
        """Reset database to initial state."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM trades")
        cursor.execute("DELETE FROM positions")
        cursor.execute("DELETE FROM account_state")
        cursor.execute("DELETE FROM price_snapshots")
        
        conn.commit()
        conn.close()
        
        # Re-seed
        self.seed_initial_balance()
        
        logger.info("Database reset to initial state")


# Global database instance
_database = None

def get_database(db_path: str = "sofia.db") -> SofiaDatabase:
    """Get or create the global database instance."""
    global _database
    if _database is None:
        # Use environment variable for DB path
        db_path = os.getenv("SOFIA_DB_URL", "sqlite:///sofia.db").replace("sqlite:///", "")
        _database = SofiaDatabase(db_path)
    return _database