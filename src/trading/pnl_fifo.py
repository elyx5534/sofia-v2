"""
P&L FIFO Engine with Multi-Currency Support
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from dataclasses import dataclass, asdict
from collections import deque
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Position:
    """FIFO position tracking"""
    symbol: str
    quantity: Decimal
    entry_price: Decimal
    entry_time: datetime
    entry_fee: Decimal
    position_id: str
    base_currency: str
    quote_currency: str
    fx_rate: Decimal  # FX rate at entry


@dataclass
class Trade:
    """Trade execution record"""
    trade_id: str
    symbol: str
    side: str  # buy/sell
    quantity: Decimal
    price: Decimal
    fee: Decimal
    funding_fee: Decimal
    timestamp: datetime
    base_currency: str
    quote_currency: str
    fx_rate: Decimal


@dataclass
class RealizedPnL:
    """Realized P&L record"""
    symbol: str
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    entry_time: datetime
    exit_time: datetime
    pnl_base: Decimal  # P&L in base currency
    pnl_usd: Decimal   # P&L in USD
    fees: Decimal
    funding: Decimal
    fx_gain_loss: Decimal
    holding_period_days: int


class PnLFIFOEngine:
    """FIFO P&L calculation engine with multi-currency support"""
    
    def __init__(self, base_currency: str = "USD"):
        self.base_currency = base_currency
        self.positions: Dict[str, deque] = {}  # Symbol -> FIFO queue of positions
        self.realized_pnl: List[RealizedPnL] = []
        self.trades: List[Trade] = []
        self.fx_rates: Dict[str, Decimal] = {}  # Currency -> USD rate
        
        # Fee structure
        self.maker_fee = Decimal("0.001")  # 0.1%
        self.taker_fee = Decimal("0.001")  # 0.1%
        self.funding_rate = Decimal("0.0001")  # 0.01% per 8h
        
        # Tax tracking
        self.tax_lots: List[Dict[str, Any]] = []
        
    def set_fx_rate(self, currency: str, rate: Decimal):
        """Set FX rate to USD"""
        self.fx_rates[currency] = rate
        logger.info(f"FX rate set: {currency}/USD = {rate}")
    
    def get_fx_rate(self, currency: str) -> Decimal:
        """Get FX rate to USD"""
        if currency == "USD":
            return Decimal("1")
        return self.fx_rates.get(currency, Decimal("1"))
    
    def process_trade(self, trade: Trade) -> Dict[str, Any]:
        """Process a trade and calculate P&L"""
        logger.info(f"Processing trade: {trade.trade_id} - {trade.side} {trade.quantity} {trade.symbol} @ {trade.price}")
        
        self.trades.append(trade)
        result = {
            'trade_id': trade.trade_id,
            'symbol': trade.symbol,
            'realized_pnl': Decimal("0"),
            'realized_pnl_usd': Decimal("0"),
            'positions_closed': [],
            'new_position': None
        }
        
        if trade.side == "buy":
            # Create new position
            position = Position(
                symbol=trade.symbol,
                quantity=trade.quantity,
                entry_price=trade.price,
                entry_time=trade.timestamp,
                entry_fee=trade.fee,
                position_id=f"POS-{trade.trade_id}",
                base_currency=trade.base_currency,
                quote_currency=trade.quote_currency,
                fx_rate=trade.fx_rate
            )
            
            if trade.symbol not in self.positions:
                self.positions[trade.symbol] = deque()
            
            self.positions[trade.symbol].append(position)
            result['new_position'] = position
            
            logger.info(f"Opened position: {position.position_id}")
            
        elif trade.side == "sell":
            # Close positions FIFO
            if trade.symbol not in self.positions or not self.positions[trade.symbol]:
                logger.warning(f"No positions to close for {trade.symbol}")
                return result
            
            remaining_quantity = trade.quantity
            
            while remaining_quantity > 0 and self.positions[trade.symbol]:
                position = self.positions[trade.symbol][0]
                
                if position.quantity <= remaining_quantity:
                    # Close entire position
                    closed_quantity = position.quantity
                    self.positions[trade.symbol].popleft()
                else:
                    # Partially close position
                    closed_quantity = remaining_quantity
                    position.quantity -= closed_quantity
                
                # Calculate P&L
                pnl_record = self._calculate_pnl(
                    position, trade, closed_quantity
                )
                
                self.realized_pnl.append(pnl_record)
                result['realized_pnl'] += pnl_record.pnl_base
                result['realized_pnl_usd'] += pnl_record.pnl_usd
                result['positions_closed'].append(pnl_record)
                
                # Tax lot tracking
                self._record_tax_lot(pnl_record)
                
                remaining_quantity -= closed_quantity
                
                logger.info(f"Closed {closed_quantity} @ P&L: {pnl_record.pnl_usd} USD")
        
        return result
    
    def _calculate_pnl(self, position: Position, trade: Trade, quantity: Decimal) -> RealizedPnL:
        """Calculate realized P&L for a position"""
        # Base P&L calculation
        pnl_base = (trade.price - position.entry_price) * quantity
        
        # Fee calculation (proportional)
        position_ratio = quantity / position.quantity
        entry_fee = position.entry_fee * position_ratio
        exit_fee = trade.fee * (quantity / trade.quantity)
        total_fees = entry_fee + exit_fee
        
        # Funding calculation
        holding_days = (trade.timestamp - position.entry_time).days
        funding_periods = holding_days * 3  # 3 funding periods per day
        funding_fee = quantity * trade.price * self.funding_rate * funding_periods
        
        # Net P&L in base currency
        net_pnl_base = pnl_base - total_fees - funding_fee
        
        # FX conversion
        entry_value_usd = position.entry_price * quantity * position.fx_rate
        exit_value_usd = trade.price * quantity * trade.fx_rate
        pnl_usd = exit_value_usd - entry_value_usd
        
        # FX gain/loss
        fx_gain_loss = (trade.fx_rate - position.fx_rate) * trade.price * quantity
        
        return RealizedPnL(
            symbol=position.symbol,
            quantity=quantity,
            entry_price=position.entry_price,
            exit_price=trade.price,
            entry_time=position.entry_time,
            exit_time=trade.timestamp,
            pnl_base=net_pnl_base,
            pnl_usd=pnl_usd - total_fees - funding_fee,
            fees=total_fees,
            funding=funding_fee,
            fx_gain_loss=fx_gain_loss,
            holding_period_days=holding_days
        )
    
    def _record_tax_lot(self, pnl: RealizedPnL):
        """Record tax lot for reporting"""
        tax_lot = {
            'date_acquired': pnl.entry_time.date(),
            'date_sold': pnl.exit_time.date(),
            'symbol': pnl.symbol,
            'quantity': str(pnl.quantity),
            'cost_basis': str(pnl.entry_price * pnl.quantity),
            'proceeds': str(pnl.exit_price * pnl.quantity),
            'gain_loss': str(pnl.pnl_usd),
            'holding_period': 'long' if pnl.holding_period_days > 365 else 'short',
            'wash_sale': self._check_wash_sale(pnl)
        }
        self.tax_lots.append(tax_lot)
    
    def _check_wash_sale(self, pnl: RealizedPnL) -> bool:
        """Check for wash sale rule violation"""
        if pnl.pnl_usd >= 0:
            return False
        
        # Check if same symbol was bought within 30 days
        wash_window_start = pnl.exit_time - timedelta(days=30)
        wash_window_end = pnl.exit_time + timedelta(days=30)
        
        for trade in self.trades:
            if (trade.symbol == pnl.symbol and 
                trade.side == "buy" and
                wash_window_start <= trade.timestamp <= wash_window_end):
                return True
        
        return False
    
    def get_unrealized_pnl(self, current_prices: Dict[str, Decimal]) -> Dict[str, Any]:
        """Calculate unrealized P&L for open positions"""
        unrealized = {
            'total_usd': Decimal("0"),
            'by_symbol': {},
            'positions': []
        }
        
        for symbol, position_queue in self.positions.items():
            if not position_queue:
                continue
            
            current_price = current_prices.get(symbol, Decimal("0"))
            if current_price == 0:
                continue
            
            symbol_unrealized = Decimal("0")
            
            for position in position_queue:
                position_pnl = (current_price - position.entry_price) * position.quantity
                position_pnl_usd = position_pnl * self.get_fx_rate(position.quote_currency)
                
                symbol_unrealized += position_pnl_usd
                
                unrealized['positions'].append({
                    'symbol': symbol,
                    'quantity': str(position.quantity),
                    'entry_price': str(position.entry_price),
                    'current_price': str(current_price),
                    'unrealized_pnl': str(position_pnl_usd),
                    'entry_time': position.entry_time.isoformat()
                })
            
            unrealized['by_symbol'][symbol] = str(symbol_unrealized)
            unrealized['total_usd'] += symbol_unrealized
        
        unrealized['total_usd'] = str(unrealized['total_usd'])
        return unrealized
    
    def generate_pnl_report(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Generate P&L report for date range"""
        report = {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': {
                'total_realized_pnl': Decimal("0"),
                'total_fees': Decimal("0"),
                'total_funding': Decimal("0"),
                'total_fx_gain_loss': Decimal("0"),
                'net_pnl': Decimal("0")
            },
            'by_symbol': {},
            'by_currency': {},
            'daily_pnl': {},
            'trades': []
        }
        
        # Filter P&L records by date
        period_pnl = [
            pnl for pnl in self.realized_pnl
            if start_date <= pnl.exit_time.date() <= end_date
        ]
        
        # Calculate summaries
        for pnl in period_pnl:
            report['summary']['total_realized_pnl'] += pnl.pnl_usd
            report['summary']['total_fees'] += pnl.fees
            report['summary']['total_funding'] += pnl.funding
            report['summary']['total_fx_gain_loss'] += pnl.fx_gain_loss
            
            # By symbol
            if pnl.symbol not in report['by_symbol']:
                report['by_symbol'][pnl.symbol] = {
                    'realized_pnl': Decimal("0"),
                    'trades': 0,
                    'fees': Decimal("0")
                }
            
            report['by_symbol'][pnl.symbol]['realized_pnl'] += pnl.pnl_usd
            report['by_symbol'][pnl.symbol]['trades'] += 1
            report['by_symbol'][pnl.symbol]['fees'] += pnl.fees
            
            # Daily P&L
            date_key = pnl.exit_time.date().isoformat()
            if date_key not in report['daily_pnl']:
                report['daily_pnl'][date_key] = Decimal("0")
            report['daily_pnl'][date_key] += pnl.pnl_usd
        
        # Calculate net P&L
        report['summary']['net_pnl'] = (
            report['summary']['total_realized_pnl'] -
            report['summary']['total_fees'] -
            report['summary']['total_funding']
        )
        
        # Convert Decimals to strings for JSON serialization
        report['summary'] = {k: str(v) for k, v in report['summary'].items()}
        report['by_symbol'] = {
            symbol: {k: str(v) for k, v in data.items()}
            for symbol, data in report['by_symbol'].items()
        }
        report['daily_pnl'] = {k: str(v) for k, v in report['daily_pnl'].items()}
        
        return report
    
    def export_to_csv(self, filename: str):
        """Export P&L records to CSV"""
        df_data = []
        
        for pnl in self.realized_pnl:
            df_data.append({
                'Date': pnl.exit_time.date(),
                'Symbol': pnl.symbol,
                'Quantity': float(pnl.quantity),
                'Entry Price': float(pnl.entry_price),
                'Exit Price': float(pnl.exit_price),
                'P&L (USD)': float(pnl.pnl_usd),
                'Fees': float(pnl.fees),
                'Funding': float(pnl.funding),
                'FX Gain/Loss': float(pnl.fx_gain_loss),
                'Holding Days': pnl.holding_period_days
            })
        
        df = pd.DataFrame(df_data)
        df.to_csv(filename, index=False)
        logger.info(f"P&L exported to {filename}")
    
    def export_to_pdf(self, filename: str, start_date: date, end_date: date):
        """Export P&L report to PDF"""
        doc = SimpleDocTemplate(filename, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title = Paragraph(f"P&L Report: {start_date} to {end_date}", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 0.2*inch))
        
        # Get report data
        report = self.generate_pnl_report(start_date, end_date)
        
        # Summary table
        summary_data = [
            ['Summary', 'Amount (USD)'],
            ['Total Realized P&L', report['summary']['total_realized_pnl']],
            ['Total Fees', report['summary']['total_fees']],
            ['Total Funding', report['summary']['total_funding']],
            ['FX Gain/Loss', report['summary']['total_fx_gain_loss']],
            ['Net P&L', report['summary']['net_pnl']]
        ]
        
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))
        
        # P&L by symbol
        if report['by_symbol']:
            symbol_title = Paragraph("P&L by Symbol", styles['Heading2'])
            story.append(symbol_title)
            
            symbol_data = [['Symbol', 'P&L (USD)', 'Trades', 'Fees']]
            for symbol, data in report['by_symbol'].items():
                symbol_data.append([
                    symbol,
                    data['realized_pnl'],
                    data['trades'],
                    data['fees']
                ])
            
            symbol_table = Table(symbol_data)
            symbol_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(symbol_table)
        
        # Build PDF
        doc.build(story)
        logger.info(f"P&L report exported to {filename}")
    
    def validate_double_entry(self) -> bool:
        """Validate double-entry bookkeeping"""
        total_debits = Decimal("0")
        total_credits = Decimal("0")
        
        # Sum all trades
        for trade in self.trades:
            if trade.side == "buy":
                total_debits += trade.quantity * trade.price + trade.fee
            else:
                total_credits += trade.quantity * trade.price - trade.fee
        
        # Sum realized P&L
        for pnl in self.realized_pnl:
            total_credits += pnl.pnl_base
        
        # Check balance
        imbalance = abs(total_debits - total_credits)
        
        if imbalance > Decimal("0.01"):  # Allow small rounding difference
            logger.error(f"Double-entry validation failed: imbalance = {imbalance}")
            return False
        
        logger.info("Double-entry validation passed")
        return True