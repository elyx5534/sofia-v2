"""
Portfolio and position tracking for paper trading
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import sqlite3
from pathlib import Path

@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    timestamp: float
    side: str = "long"
    
    @property
    def pnl(self) -> float:
        """Calculate unrealized P&L"""
        return (self.current_price - self.entry_price) * self.quantity
    
    @property
    def pnl_pct(self) -> float:
        """P&L percentage"""
        if self.entry_price == 0:
            return 0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100


class PortfolioManager:
    """Manages paper trading portfolio"""
    
    def __init__(self, db_path: str = "sofia.db"):
        self.db_path = db_path
        self.base_currency = "USD"
        self._init_db()
        
    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Portfolio table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY,
                cash_balance REAL DEFAULT 100000,
                base_currency TEXT DEFAULT 'USD',
                updated_at REAL
            )
        ''')
        
        # Positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL,
                side TEXT DEFAULT 'long',
                timestamp REAL,
                closed INTEGER DEFAULT 0
            )
        ''')
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                usd_amount REAL,
                timestamp REAL,
                pnl REAL,
                fees REAL DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def get_portfolio(self) -> Dict:
        """Get current portfolio state"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get or create portfolio
        cursor.execute('SELECT cash_balance, base_currency FROM portfolio LIMIT 1')
        row = cursor.fetchone()
        
        if not row:
            # Initialize with default balance
            balance = float(os.getenv('SOFIA_START_BALANCE', '100000'))
            cursor.execute('INSERT INTO portfolio (cash_balance, base_currency, updated_at) VALUES (?, ?, ?)',
                         (balance, self.base_currency, time.time()))
            conn.commit()
            cash_balance = balance
        else:
            cash_balance = row[0]
            
        # Get open positions
        cursor.execute('SELECT * FROM positions WHERE closed = 0')
        positions = []
        total_position_value = 0
        
        for row in cursor.fetchall():
            pos = Position(
                symbol=row[1],
                quantity=row[2],
                entry_price=row[3],
                current_price=row[4] or row[3],
                timestamp=row[6] or time.time(),
                side=row[5]
            )
            pos_dict = asdict(pos)
            # Add computed properties
            pos_dict['pnl'] = pos.pnl
            pos_dict['pnl_pct'] = pos.pnl_pct
            positions.append(pos_dict)
            total_position_value += pos.quantity * pos.current_price
            
        conn.close()
        
        return {
            'base_currency': self.base_currency,
            'cash_balance': cash_balance,
            'positions_value': total_position_value,
            'total_balance': cash_balance + total_position_value,
            'positions': positions,
            'timestamp': time.time()
        }
    
    def execute_order(self, symbol: str, side: str, usd_amount: float, price: float) -> Dict:
        """Execute a paper trade order"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current cash
        cursor.execute('SELECT cash_balance FROM portfolio LIMIT 1')
        row = cursor.fetchone()
        cash_balance = row[0] if row else 100000.0
        
        if side == 'buy':
            if usd_amount > cash_balance:
                conn.close()
                return {'success': False, 'error': 'Insufficient funds'}
                
            quantity = usd_amount / price
            fees = usd_amount * 0.001  # 0.1% fee
            
            # Update cash
            new_balance = cash_balance - usd_amount - fees
            cursor.execute('UPDATE portfolio SET cash_balance = ?, updated_at = ?',
                         (new_balance, time.time()))
            
            # Add position
            cursor.execute('''
                INSERT INTO positions (symbol, quantity, entry_price, current_price, side, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (symbol, quantity, price, price, 'long', time.time()))
            
            # Record trade
            cursor.execute('''
                INSERT INTO trades (symbol, side, quantity, price, usd_amount, timestamp, fees)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, side, quantity, price, usd_amount, time.time(), fees))
            
        else:  # sell
            # Get position
            cursor.execute('SELECT id, quantity, entry_price FROM positions WHERE symbol = ? AND closed = 0 LIMIT 1',
                         (symbol,))
            pos = cursor.fetchone()
            
            if not pos:
                conn.close()
                return {'success': False, 'error': 'No position to sell'}
                
            pos_id, pos_qty, entry_price = pos
            sell_qty = min(pos_qty, usd_amount / price)
            proceeds = sell_qty * price
            fees = proceeds * 0.001
            pnl = (price - entry_price) * sell_qty - fees
            
            # Update cash
            new_balance = cash_balance + proceeds - fees
            cursor.execute('UPDATE portfolio SET cash_balance = ?, updated_at = ?',
                         (new_balance, time.time()))
            
            # Update or close position
            remaining = pos_qty - sell_qty
            if remaining < 0.00001:
                cursor.execute('UPDATE positions SET closed = 1 WHERE id = ?', (pos_id,))
            else:
                cursor.execute('UPDATE positions SET quantity = ? WHERE id = ?', (remaining, pos_id))
                
            # Record trade
            cursor.execute('''
                INSERT INTO trades (symbol, side, quantity, price, usd_amount, timestamp, pnl, fees)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, side, sell_qty, price, proceeds, time.time(), pnl, fees))
            
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'symbol': symbol,
            'side': side,
            'quantity': quantity if side == 'buy' else sell_qty,
            'price': price,
            'timestamp': time.time()
        }
        
    def update_position_prices(self, prices: Dict[str, float]):
        """Update current prices for positions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for symbol, price in prices.items():
            cursor.execute('UPDATE positions SET current_price = ? WHERE symbol = ? AND closed = 0',
                         (price, symbol))
                         
        conn.commit()
        conn.close()


# Global instance
portfolio_manager = PortfolioManager()