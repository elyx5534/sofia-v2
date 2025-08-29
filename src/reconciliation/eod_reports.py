"""
Daily Reconciliation and EOD Reports
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta, date
from dataclasses import dataclass, asdict
import pandas as pd
from jinja2 import Template
import aiofiles
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class TradingSummary:
    """Daily trading summary"""
    date: date
    total_orders: int
    executed_orders: int
    shadow_orders: int
    filled_orders: int
    canceled_orders: int
    total_volume: Decimal
    total_fees: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    positions: Dict[str, Decimal]
    top_symbols: List[str]
    risk_blocks: int
    kill_switch_events: int
    errors: int
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['date'] = self.date.isoformat()
        d['total_volume'] = str(self.total_volume)
        d['total_fees'] = str(self.total_fees)
        d['realized_pnl'] = str(self.realized_pnl)
        d['unrealized_pnl'] = str(self.unrealized_pnl)
        d['positions'] = {k: str(v) for k, v in self.positions.items()}
        return d


class ReconciliationEngine:
    """Daily reconciliation and reporting engine"""
    
    def __init__(self, live_adapter=None, risk_engine=None, shadow_controller=None):
        self.live_adapter = live_adapter
        self.risk_engine = risk_engine
        self.shadow_controller = shadow_controller
        
        # Report configuration
        self.reports_dir = "reports"
        self.reconciliation_dir = os.path.join(self.reports_dir, "reconciliation")
        self.eod_dir = os.path.join(self.reports_dir, "eod")
        
        # Create directories
        os.makedirs(self.reconciliation_dir, exist_ok=True)
        os.makedirs(self.eod_dir, exist_ok=True)
        
        # Reconciliation state
        self.discrepancies: List[Dict] = []
        self.last_reconciliation = None
        
        logger.info("Reconciliation Engine initialized")
    
    async def reconcile_positions(self) -> Dict[str, Any]:
        """
        Reconcile internal positions with exchange
        
        Returns:
            Reconciliation report
        """
        logger.info("Starting position reconciliation...")
        
        discrepancies = []
        reconciled_positions = {}
        
        try:
            # Get exchange positions
            if self.live_adapter:
                await self.live_adapter.resync()
                exchange_positions = {}
                
                # Calculate positions from open orders
                open_orders = await self.live_adapter.get_open_orders()
                for order in open_orders:
                    symbol = order.symbol
                    if symbol not in exchange_positions:
                        exchange_positions[symbol] = Decimal('0')
                    
                    if order.side == 'buy':
                        exchange_positions[symbol] += order.filled_quantity
                    else:
                        exchange_positions[symbol] -= order.filled_quantity
            else:
                exchange_positions = {}
            
            # Get internal positions
            internal_positions = {}
            if self.risk_engine:
                internal_positions = self.risk_engine.positions.copy()
            
            # Compare positions
            all_symbols = set(exchange_positions.keys()) | set(internal_positions.keys())
            
            for symbol in all_symbols:
                exchange_pos = exchange_positions.get(symbol, Decimal('0'))
                internal_pos = internal_positions.get(symbol, Decimal('0'))
                
                if abs(exchange_pos - internal_pos) > Decimal('0.0001'):
                    discrepancy = {
                        'symbol': symbol,
                        'exchange_position': str(exchange_pos),
                        'internal_position': str(internal_pos),
                        'difference': str(exchange_pos - internal_pos),
                        'timestamp': datetime.now().isoformat()
                    }
                    discrepancies.append(discrepancy)
                    
                    logger.warning(f"Position discrepancy for {symbol}: exchange={exchange_pos}, internal={internal_pos}")
                
                # Use exchange position as source of truth
                reconciled_positions[symbol] = exchange_pos
            
            # Update internal state with reconciled positions
            if self.risk_engine:
                for symbol, position in reconciled_positions.items():
                    self.risk_engine.update_position(symbol, position)
            
            self.discrepancies = discrepancies
            self.last_reconciliation = datetime.now()
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'status': 'success',
                'positions_checked': len(all_symbols),
                'discrepancies_found': len(discrepancies),
                'discrepancies': discrepancies,
                'reconciled_positions': {k: str(v) for k, v in reconciled_positions.items()}
            }
            
            # Save reconciliation report
            await self._save_reconciliation_report(report)
            
            logger.info(f"Reconciliation complete: {len(discrepancies)} discrepancies found")
            return report
            
        except Exception as e:
            logger.error(f"Reconciliation failed: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'status': 'failed',
                'error': str(e)
            }
    
    async def generate_eod_report(self) -> Dict[str, Any]:
        """Generate end-of-day report"""
        logger.info("Generating EOD report...")
        
        try:
            # Collect data from all components
            summary = await self._collect_trading_summary()
            
            # Generate HTML report
            html_report = self._generate_html_report(summary)
            
            # Save reports
            report_date = datetime.now().date()
            
            # Save JSON
            json_path = os.path.join(self.eod_dir, f"eod_{report_date}.json")
            async with aiofiles.open(json_path, 'w') as f:
                await f.write(json.dumps(summary.to_dict(), indent=2))
            
            # Save HTML
            html_path = os.path.join(self.eod_dir, f"eod_{report_date}.html")
            async with aiofiles.open(html_path, 'w') as f:
                await f.write(html_report)
            
            # Email notification (stub)
            await self._send_eod_notification(summary)
            
            logger.info(f"EOD report generated: {json_path}")
            
            return {
                'status': 'success',
                'date': report_date.isoformat(),
                'json_path': json_path,
                'html_path': html_path,
                'summary': summary.to_dict()
            }
            
        except Exception as e:
            logger.error(f"EOD report generation failed: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _collect_trading_summary(self) -> TradingSummary:
        """Collect trading summary data"""
        # Initialize counters
        total_orders = 0
        executed_orders = 0
        shadow_orders = 0
        filled_orders = 0
        canceled_orders = 0
        total_volume = Decimal('0')
        total_fees = Decimal('0')
        realized_pnl = Decimal('0')
        unrealized_pnl = Decimal('0')
        positions = {}
        top_symbols = []
        risk_blocks = 0
        kill_switch_events = 0
        errors = 0
        
        # Collect from live adapter
        if self.live_adapter:
            for order in self.live_adapter.orders.values():
                total_orders += 1
                if order.state.value == 'FILLED':
                    filled_orders += 1
                    total_volume += order.quantity * (order.average_price or order.price or Decimal('0'))
                    total_fees += order.quantity * (order.average_price or order.price or Decimal('0')) * Decimal('0.001')  # 0.1% fee
                elif order.state.value == 'CANCELED':
                    canceled_orders += 1
        
        # Collect from shadow controller
        if self.shadow_controller:
            status = self.shadow_controller.get_status()
            shadow_orders = status.get('shadow_count', 0)
            executed_orders = status.get('executed_count', 0)
            positions.update(self.shadow_controller.shadow_positions)
        
        # Collect from risk engine
        if self.risk_engine:
            status = self.risk_engine.get_status()
            risk_blocks = status.get('checks_blocked', 0)
            kill_switch_events = status.get('auto_halts', 0)
            realized_pnl = Decimal(status.get('daily_pnl', '0'))
            positions.update(self.risk_engine.positions)
        
        # Calculate top symbols
        symbol_volumes = {}
        if self.live_adapter:
            for order in self.live_adapter.orders.values():
                symbol = order.symbol
                volume = order.quantity * (order.price or Decimal('0'))
                symbol_volumes[symbol] = symbol_volumes.get(symbol, Decimal('0')) + volume
        
        top_symbols = sorted(symbol_volumes.keys(), key=lambda x: symbol_volumes[x], reverse=True)[:5]
        
        return TradingSummary(
            date=datetime.now().date(),
            total_orders=total_orders,
            executed_orders=executed_orders,
            shadow_orders=shadow_orders,
            filled_orders=filled_orders,
            canceled_orders=canceled_orders,
            total_volume=total_volume,
            total_fees=total_fees,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            positions=positions,
            top_symbols=top_symbols,
            risk_blocks=risk_blocks,
            kill_switch_events=kill_switch_events,
            errors=errors
        )
    
    def _generate_html_report(self, summary: TradingSummary) -> str:
        """Generate HTML report"""
        template_str = '''
<!DOCTYPE html>
<html>
<head>
    <title>EOD Report - {{ date }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }
        .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .metric-card { background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metric-value { font-size: 24px; font-weight: bold; color: #2c3e50; }
        .metric-label { color: #7f8c8d; font-size: 12px; text-transform: uppercase; }
        .positive { color: #27ae60; }
        .negative { color: #e74c3c; }
        table { width: 100%; background: white; border-radius: 5px; overflow: hidden; margin: 20px 0; }
        th { background: #34495e; color: white; padding: 10px; text-align: left; }
        td { padding: 10px; border-bottom: 1px solid #ecf0f1; }
        .footer { text-align: center; color: #7f8c8d; margin-top: 40px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>End of Day Report</h1>
        <p>{{ date }}</p>
    </div>
    
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-label">Total Orders</div>
            <div class="metric-value">{{ total_orders }}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Executed</div>
            <div class="metric-value">{{ executed_orders }}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Volume</div>
            <div class="metric-value">${{ "%.2f"|format(total_volume) }}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Fees</div>
            <div class="metric-value">${{ "%.2f"|format(total_fees) }}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Realized P&L</div>
            <div class="metric-value {% if realized_pnl >= 0 %}positive{% else %}negative{% endif %}">
                ${{ "%.2f"|format(realized_pnl) }}
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Risk Blocks</div>
            <div class="metric-value">{{ risk_blocks }}</div>
        </div>
    </div>
    
    <h2>Open Positions</h2>
    <table>
        <thead>
            <tr>
                <th>Symbol</th>
                <th>Position</th>
                <th>Value (USD)</th>
            </tr>
        </thead>
        <tbody>
            {% for symbol, position in positions.items() %}
            <tr>
                <td>{{ symbol }}</td>
                <td>{{ position }}</td>
                <td>${{ "%.2f"|format(position) }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    
    <h2>Top Symbols</h2>
    <ul>
        {% for symbol in top_symbols %}
        <li>{{ symbol }}</li>
        {% endfor %}
    </ul>
    
    <div class="footer">
        <p>Generated at {{ timestamp }}</p>
        <p>Sofia Trading System v0.2.0</p>
    </div>
</body>
</html>
        '''
        
        template = Template(template_str)
        return template.render(
            date=summary.date,
            total_orders=summary.total_orders,
            executed_orders=summary.executed_orders,
            total_volume=float(summary.total_volume),
            total_fees=float(summary.total_fees),
            realized_pnl=float(summary.realized_pnl),
            risk_blocks=summary.risk_blocks,
            positions=summary.positions,
            top_symbols=summary.top_symbols,
            timestamp=datetime.now().isoformat()
        )
    
    async def _save_reconciliation_report(self, report: Dict[str, Any]):
        """Save reconciliation report"""
        timestamp = datetime.now()
        filename = f"reconciliation_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.reconciliation_dir, filename)
        
        async with aiofiles.open(filepath, 'w') as f:
            await f.write(json.dumps(report, indent=2))
        
        logger.info(f"Reconciliation report saved: {filepath}")
    
    async def _send_eod_notification(self, summary: TradingSummary):
        """Send EOD notification (placeholder)"""
        # In production, integrate with email/Slack/etc
        logger.info(f"EOD notification would be sent: P&L={summary.realized_pnl}")
    
    def get_discrepancies(self) -> List[Dict[str, Any]]:
        """Get current discrepancies"""
        return self.discrepancies
    
    def get_last_reconciliation(self) -> Optional[datetime]:
        """Get last reconciliation timestamp"""
        return self.last_reconciliation