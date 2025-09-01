"""
Enterprise-Level Risk Management System
Comprehensive risk controls for institutional trading
"""

import asyncio
import logging
import json
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
import pandas as pd
from enum import Enum
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class AlertType(Enum):
    POSITION_SIZE = "position_size"
    STOP_LOSS_HIT = "stop_loss_hit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    CORRELATION_HIGH = "correlation_high"
    EMERGENCY_STOP = "emergency_stop"
    PORTFOLIO_HEAT = "portfolio_heat"
    NETWORK_ERROR = "network_error"
    DATABASE_BACKUP = "database_backup"

@dataclass
class Position:
    """Trading position with risk metrics"""
    id: str
    symbol: str
    side: str  # long/short
    entry_price: Decimal
    current_price: Decimal
    size: Decimal
    timestamp: datetime
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    trailing_stop_distance: Optional[Decimal] = None
    max_price: Optional[Decimal] = None  # For trailing stop
    correlation_group: Optional[str] = None
    
    @property
    def pnl(self) -> Decimal:
        """Calculate P&L"""
        if self.side == "long":
            return (self.current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - self.current_price) * self.size
    
    @property
    def pnl_percentage(self) -> Decimal:
        """Calculate P&L percentage"""
        return (self.pnl / (self.entry_price * self.size)) * 100
    
    @property
    def risk_amount(self) -> Decimal:
        """Calculate risk amount based on stop loss"""
        if self.stop_loss:
            if self.side == "long":
                return (self.entry_price - self.stop_loss) * self.size
            else:
                return (self.stop_loss - self.entry_price) * self.size
        return self.entry_price * self.size * Decimal("0.02")  # Default 2% risk

@dataclass
class RiskMetrics:
    """Portfolio risk metrics"""
    total_positions: int
    total_exposure: Decimal
    portfolio_heat: Decimal  # Total risk as % of portfolio
    daily_pnl: Decimal
    daily_pnl_percentage: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal
    var_95: Decimal  # Value at Risk
    correlation_matrix: Dict[str, Dict[str, float]]
    risk_level: RiskLevel
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class Alert:
    """Risk alert"""
    type: AlertType
    level: RiskLevel
    message: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

class EnterpriseRiskManager:
    """Enterprise-grade risk management system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Portfolio limits
        self.max_positions = config.get("max_positions", 10)
        self.max_position_size = Decimal(str(config.get("max_position_size", 0.05)))
        self.max_daily_loss = Decimal(str(config.get("max_daily_loss", 0.03)))
        self.max_correlation = config.get("max_correlation", 0.7)
        self.max_portfolio_heat = Decimal(str(config.get("max_portfolio_heat", 0.1)))
        
        # Kelly Criterion parameters
        self.kelly_fraction = Decimal(str(config.get("kelly_fraction", 0.25)))
        self.min_kelly_size = Decimal(str(config.get("min_kelly_size", 0.001)))
        self.max_kelly_size = Decimal(str(config.get("max_kelly_size", 0.1)))
        
        # Stop loss parameters
        self.default_stop_loss = Decimal(str(config.get("default_stop_loss", 0.02)))
        self.trailing_stop_activation = Decimal(str(config.get("trailing_activation", 0.01)))
        self.time_stop_hours = config.get("time_stop_hours", 24)
        self.breakeven_trigger = Decimal(str(config.get("breakeven_trigger", 0.005)))
        
        # Alert configurations
        self.telegram_config = config.get("telegram", {})
        self.discord_webhook = config.get("discord_webhook")
        self.email_config = config.get("email", {})
        self.twilio_config = config.get("twilio", {})
        
        # State tracking
        self.positions: Dict[str, Position] = {}
        self.daily_pnl = Decimal(0)
        self.daily_trades = []
        self.price_history: Dict[str, List[float]] = defaultdict(list)
        self.alerts: List[Alert] = []
        self.emergency_mode = False
        
        # Tasks
        self.monitor_task = None
        self.report_task = None
        self.backup_task = None
        
        # Callbacks
        self.emergency_callback: Optional[Callable] = None
        
    async def initialize(self):
        """Initialize risk management system"""
        logger.info("Initializing Risk Management System")
        
        # Start monitoring tasks
        self.monitor_task = asyncio.create_task(self._monitor_positions())
        self.report_task = asyncio.create_task(self._generate_reports())
        self.backup_task = asyncio.create_task(self._backup_data())
        
        logger.info("Risk Manager initialized successfully")
    
    async def shutdown(self):
        """Shutdown risk manager"""
        if self.monitor_task:
            self.monitor_task.cancel()
        if self.report_task:
            self.report_task.cancel()
        if self.backup_task:
            self.backup_task.cancel()
    
    def calculate_kelly_size(
        self,
        win_rate: float,
        avg_win: Decimal,
        avg_loss: Decimal,
        portfolio_value: Decimal
    ) -> Decimal:
        """Calculate position size using Kelly Criterion"""
        if avg_loss == 0:
            return self.min_kelly_size
        
        # Kelly formula: f = (p*b - q) / b
        # where p = win_rate, q = 1-p, b = avg_win/avg_loss
        p = Decimal(str(win_rate))
        q = Decimal(1) - p
        b = avg_win / avg_loss
        
        kelly = (p * b - q) / b
        
        # Apply Kelly fraction (usually 25% of full Kelly)
        kelly = kelly * self.kelly_fraction
        
        # Apply limits
        kelly = max(self.min_kelly_size, min(self.max_kelly_size, kelly))
        
        # Convert to position size
        position_size = portfolio_value * kelly
        
        return position_size
    
    def calculate_atr_size(
        self,
        atr: Decimal,
        price: Decimal,
        risk_amount: Decimal,
        atr_multiplier: Decimal = Decimal("2")
    ) -> Decimal:
        """Calculate position size based on ATR (Average True Range)"""
        # Stop distance = ATR * multiplier
        stop_distance = atr * atr_multiplier
        
        # Position size = Risk Amount / Stop Distance
        position_size = risk_amount / stop_distance
        
        return position_size
    
    def calculate_correlation_matrix(
        self,
        symbols: List[str],
        lookback: int = 30
    ) -> Dict[str, Dict[str, float]]:
        """Calculate correlation matrix for portfolio"""
        if len(symbols) < 2:
            return {}
        
        # Get price data for all symbols
        price_data = {}
        for symbol in symbols:
            if symbol in self.price_history:
                prices = self.price_history[symbol][-lookback:]
                if len(prices) >= 2:
                    # Calculate returns
                    returns = np.diff(np.log(prices))
                    price_data[symbol] = returns
        
        # Calculate correlation matrix
        correlation_matrix = {}
        for symbol1 in price_data:
            correlation_matrix[symbol1] = {}
            for symbol2 in price_data:
                if symbol1 == symbol2:
                    correlation_matrix[symbol1][symbol2] = 1.0
                else:
                    corr = np.corrcoef(price_data[symbol1], price_data[symbol2])[0, 1]
                    correlation_matrix[symbol1][symbol2] = float(corr)
        
        return correlation_matrix
    
    def calculate_portfolio_heat(self) -> Decimal:
        """Calculate total portfolio risk exposure"""
        total_risk = Decimal(0)
        portfolio_value = sum(p.entry_price * p.size for p in self.positions.values())
        
        if portfolio_value == 0:
            return Decimal(0)
        
        for position in self.positions.values():
            total_risk += position.risk_amount
        
        return (total_risk / portfolio_value) * 100
    
    async def check_position_limits(
        self,
        symbol: str,
        size: Decimal,
        portfolio_value: Decimal
    ) -> tuple[bool, str]:
        """Check if new position violates risk limits"""
        
        # Check max positions
        if len(self.positions) >= self.max_positions:
            return False, f"Maximum positions limit reached ({self.max_positions})"
        
        # Check position size
        position_value = size
        if position_value > portfolio_value * self.max_position_size:
            return False, f"Position size exceeds limit ({self.max_position_size:.1%})"
        
        # Check portfolio heat
        current_heat = self.calculate_portfolio_heat()
        if current_heat > self.max_portfolio_heat * 100:
            return False, f"Portfolio heat too high ({current_heat:.1f}%)"
        
        # Check correlations
        correlations = self.calculate_correlation_matrix(
            [p.symbol for p in self.positions.values()] + [symbol]
        )
        
        for pos in self.positions.values():
            if pos.symbol in correlations and symbol in correlations[pos.symbol]:
                corr = correlations[pos.symbol][symbol]
                if abs(corr) > self.max_correlation:
                    return False, f"High correlation with {pos.symbol} ({corr:.2f})"
        
        # Check daily loss limit
        if self.daily_pnl < -portfolio_value * self.max_daily_loss:
            return False, f"Daily loss limit reached ({self.daily_pnl:.2f})"
        
        return True, "OK"
    
    async def add_position(self, position: Position) -> bool:
        """Add new position with risk checks"""
        # Validate position
        portfolio_value = sum(p.entry_price * p.size for p in self.positions.values())
        portfolio_value += position.entry_price * position.size
        
        can_add, reason = await self.check_position_limits(
            position.symbol,
            position.size * position.entry_price,
            portfolio_value
        )
        
        if not can_add:
            await self.send_alert(
                AlertType.POSITION_SIZE,
                RiskLevel.HIGH,
                f"Position rejected: {reason}",
                {"position": position.__dict__}
            )
            return False
        
        # Add position
        self.positions[position.id] = position
        
        # Set default stop loss if not provided
        if not position.stop_loss:
            if position.side == "long":
                position.stop_loss = position.entry_price * (1 - self.default_stop_loss)
            else:
                position.stop_loss = position.entry_price * (1 + self.default_stop_loss)
        
        # Log trade
        self.daily_trades.append({
            "id": position.id,
            "symbol": position.symbol,
            "side": position.side,
            "entry": float(position.entry_price),
            "size": float(position.size),
            "timestamp": position.timestamp.isoformat()
        })
        
        logger.info(f"Position added: {position.id} {position.symbol} {position.side}")
        return True
    
    async def update_stop_loss(self, position_id: str, stop_type: str = "trailing"):
        """Update stop loss for position"""
        if position_id not in self.positions:
            return
        
        position = self.positions[position_id]
        
        if stop_type == "trailing":
            await self._update_trailing_stop(position)
        elif stop_type == "breakeven":
            await self._update_breakeven_stop(position)
        elif stop_type == "time":
            await self._update_time_stop(position)
        elif stop_type == "volatility":
            await self._update_volatility_stop(position)
    
    async def _update_trailing_stop(self, position: Position):
        """Update trailing stop loss"""
        if not position.trailing_stop_distance:
            position.trailing_stop_distance = position.entry_price * self.default_stop_loss
        
        # Update max price
        if position.side == "long":
            if not position.max_price or position.current_price > position.max_price:
                position.max_price = position.current_price
                # Move stop up
                new_stop = position.max_price - position.trailing_stop_distance
                if not position.stop_loss or new_stop > position.stop_loss:
                    position.stop_loss = new_stop
                    logger.info(f"Trailing stop updated for {position.id}: {position.stop_loss}")
        else:
            if not position.max_price or position.current_price < position.max_price:
                position.max_price = position.current_price
                # Move stop down
                new_stop = position.max_price + position.trailing_stop_distance
                if not position.stop_loss or new_stop < position.stop_loss:
                    position.stop_loss = new_stop
                    logger.info(f"Trailing stop updated for {position.id}: {position.stop_loss}")
    
    async def _update_breakeven_stop(self, position: Position):
        """Move stop to breakeven when in profit"""
        if position.pnl_percentage > self.breakeven_trigger * 100:
            if position.side == "long":
                if not position.stop_loss or position.stop_loss < position.entry_price:
                    position.stop_loss = position.entry_price * Decimal("1.001")  # Small profit
                    logger.info(f"Breakeven stop set for {position.id}")
            else:
                if not position.stop_loss or position.stop_loss > position.entry_price:
                    position.stop_loss = position.entry_price * Decimal("0.999")
                    logger.info(f"Breakeven stop set for {position.id}")
    
    async def _update_time_stop(self, position: Position):
        """Close position after time limit"""
        age = datetime.now() - position.timestamp
        if age > timedelta(hours=self.time_stop_hours):
            await self.close_position(position.id, "Time stop triggered")
    
    async def _update_volatility_stop(self, position: Position):
        """Update stop based on volatility (ATR)"""
        if position.symbol in self.price_history:
            prices = self.price_history[position.symbol][-20:]
            if len(prices) >= 2:
                # Simple ATR calculation
                high_low = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
                atr = sum(high_low) / len(high_low)
                
                stop_distance = Decimal(str(atr)) * Decimal("2")
                
                if position.side == "long":
                    new_stop = position.current_price - stop_distance
                    if not position.stop_loss or new_stop > position.stop_loss:
                        position.stop_loss = new_stop
                else:
                    new_stop = position.current_price + stop_distance
                    if not position.stop_loss or new_stop < position.stop_loss:
                        position.stop_loss = new_stop
    
    async def check_stop_losses(self):
        """Check and trigger stop losses"""
        positions_to_close = []
        
        for position in self.positions.values():
            if position.stop_loss:
                if position.side == "long" and position.current_price <= position.stop_loss:
                    positions_to_close.append(position.id)
                elif position.side == "short" and position.current_price >= position.stop_loss:
                    positions_to_close.append(position.id)
        
        for position_id in positions_to_close:
            await self.close_position(position_id, "Stop loss hit")
            await self.send_alert(
                AlertType.STOP_LOSS_HIT,
                RiskLevel.HIGH,
                f"Stop loss triggered for {self.positions[position_id].symbol}",
                {"position_id": position_id}
            )
    
    async def close_position(self, position_id: str, reason: str = ""):
        """Close a position"""
        if position_id not in self.positions:
            return
        
        position = self.positions[position_id]
        self.daily_pnl += position.pnl
        
        logger.info(f"Position closed: {position_id} ({reason}) P&L: {position.pnl:.2f}")
        
        del self.positions[position_id]
    
    async def emergency_stop_all(self, reason: str = "Emergency stop triggered"):
        """PANIC BUTTON - Close all positions immediately"""
        self.emergency_mode = True
        
        await self.send_alert(
            AlertType.EMERGENCY_STOP,
            RiskLevel.EMERGENCY,
            f"EMERGENCY STOP: {reason}",
            {"positions": len(self.positions)}
        )
        
        # Close all positions
        position_ids = list(self.positions.keys())
        for position_id in position_ids:
            await self.close_position(position_id, reason)
        
        # Call emergency callback if set
        if self.emergency_callback:
            await self.emergency_callback()
        
        logger.critical(f"Emergency stop executed: {reason}")
    
    async def send_alert(
        self,
        alert_type: AlertType,
        level: RiskLevel,
        message: str,
        data: Dict[str, Any] = None
    ):
        """Send alert through configured channels"""
        alert = Alert(
            type=alert_type,
            level=level,
            message=message,
            data=data or {}
        )
        
        self.alerts.append(alert)
        
        # Log alert
        logger.warning(f"ALERT [{level.value}]: {message}")
        
        # Send to various channels based on level
        if level in [RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.EMERGENCY]:
            # Telegram
            if self.telegram_config:
                asyncio.create_task(self._send_telegram_alert(alert))
            
            # Discord
            if self.discord_webhook:
                asyncio.create_task(self._send_discord_alert(alert))
            
            # Email
            if self.email_config and level in [RiskLevel.CRITICAL, RiskLevel.EMERGENCY]:
                asyncio.create_task(self._send_email_alert(alert))
            
            # SMS for emergency only
            if self.twilio_config and level == RiskLevel.EMERGENCY:
                asyncio.create_task(self._send_sms_alert(alert))
    
    async def _send_telegram_alert(self, alert: Alert):
        """Send alert to Telegram"""
        try:
            bot_token = self.telegram_config.get("bot_token")
            chat_id = self.telegram_config.get("chat_id")
            
            if not bot_token or not chat_id:
                return
            
            text = f"🚨 *{alert.level.value.upper()}*\n\n{alert.message}\n\nTime: {alert.timestamp}"
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown"
                })
            
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
    
    async def _send_discord_alert(self, alert: Alert):
        """Send alert to Discord"""
        try:
            if not self.discord_webhook:
                return
            
            color = {
                RiskLevel.LOW: 0x00FF00,
                RiskLevel.MEDIUM: 0xFFFF00,
                RiskLevel.HIGH: 0xFF8800,
                RiskLevel.CRITICAL: 0xFF0000,
                RiskLevel.EMERGENCY: 0x8B0000
            }.get(alert.level, 0x808080)
            
            embed = {
                "title": f"{alert.level.value.upper()} Alert",
                "description": alert.message,
                "color": color,
                "timestamp": alert.timestamp.isoformat(),
                "fields": [
                    {"name": "Type", "value": alert.type.value, "inline": True},
                    {"name": "Level", "value": alert.level.value, "inline": True}
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                await session.post(self.discord_webhook, json={"embeds": [embed]})
            
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
    
    async def _send_email_alert(self, alert: Alert):
        """Send alert via email"""
        try:
            smtp_server = self.email_config.get("smtp_server")
            smtp_port = self.email_config.get("smtp_port", 587)
            sender = self.email_config.get("sender")
            password = self.email_config.get("password")
            recipients = self.email_config.get("recipients", [])
            
            if not all([smtp_server, sender, password, recipients]):
                return
            
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = f"[{alert.level.value.upper()}] Risk Alert - {alert.type.value}"
            
            body = f"""
            Risk Alert Notification
            
            Level: {alert.level.value}
            Type: {alert.type.value}
            Message: {alert.message}
            Time: {alert.timestamp}
            
            Data: {json.dumps(alert.data, indent=2, default=str)}
            """
            
            msg.attach(MIMEText(body, "plain"))
            
            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    async def _send_sms_alert(self, alert: Alert):
        """Send SMS alert via Twilio"""
        try:
            account_sid = self.twilio_config.get("account_sid")
            auth_token = self.twilio_config.get("auth_token")
            from_number = self.twilio_config.get("from_number")
            to_numbers = self.twilio_config.get("to_numbers", [])
            
            if not all([account_sid, auth_token, from_number, to_numbers]):
                return
            
            # Twilio API URL
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            
            message = f"EMERGENCY: {alert.message[:140]}"  # SMS limit
            
            for to_number in to_numbers:
                async with aiohttp.ClientSession() as session:
                    await session.post(
                        url,
                        auth=aiohttp.BasicAuth(account_sid, auth_token),
                        data={
                            "From": from_number,
                            "To": to_number,
                            "Body": message
                        }
                    )
            
        except Exception as e:
            logger.error(f"Failed to send SMS alert: {e}")
    
    async def generate_risk_report(self) -> RiskMetrics:
        """Generate comprehensive risk report"""
        # Calculate metrics
        total_exposure = sum(p.entry_price * p.size for p in self.positions.values())
        portfolio_heat = self.calculate_portfolio_heat()
        
        # Calculate daily P&L percentage
        if total_exposure > 0:
            daily_pnl_pct = (self.daily_pnl / total_exposure) * 100
        else:
            daily_pnl_pct = Decimal(0)
        
        # Calculate max drawdown
        max_drawdown = min(p.pnl_percentage for p in self.positions.values()) if self.positions else Decimal(0)
        
        # Calculate Sharpe ratio (simplified)
        returns = [float(p.pnl_percentage) for p in self.positions.values()]
        if len(returns) > 1:
            sharpe = np.mean(returns) / (np.std(returns) + 1e-6) * np.sqrt(252)
        else:
            sharpe = 0
        
        # Calculate VaR (95% confidence)
        if returns:
            var_95 = Decimal(str(np.percentile(returns, 5)))
        else:
            var_95 = Decimal(0)
        
        # Get correlation matrix
        symbols = list(set(p.symbol for p in self.positions.values()))
        correlation_matrix = self.calculate_correlation_matrix(symbols)
        
        # Determine risk level
        if self.emergency_mode:
            risk_level = RiskLevel.EMERGENCY
        elif portfolio_heat > 15 or daily_pnl_pct < -2:
            risk_level = RiskLevel.CRITICAL
        elif portfolio_heat > 10 or daily_pnl_pct < -1:
            risk_level = RiskLevel.HIGH
        elif portfolio_heat > 5:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        return RiskMetrics(
            total_positions=len(self.positions),
            total_exposure=total_exposure,
            portfolio_heat=portfolio_heat,
            daily_pnl=self.daily_pnl,
            daily_pnl_percentage=daily_pnl_pct,
            max_drawdown=max_drawdown,
            sharpe_ratio=Decimal(str(sharpe)),
            var_95=var_95,
            correlation_matrix=correlation_matrix,
            risk_level=risk_level
        )
    
    async def _monitor_positions(self):
        """Monitor positions and risk limits"""
        while True:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                # Update stop losses
                for position in self.positions.values():
                    await self.update_stop_loss(position.id, "trailing")
                    await self.update_stop_loss(position.id, "breakeven")
                    await self.update_stop_loss(position.id, "time")
                
                # Check stop losses
                await self.check_stop_losses()
                
                # Check daily loss limit
                portfolio_value = sum(p.entry_price * p.size for p in self.positions.values())
                if portfolio_value > 0 and self.daily_pnl < -portfolio_value * self.max_daily_loss:
                    await self.emergency_stop_all("Daily loss limit exceeded")
                
                # Check portfolio heat
                heat = self.calculate_portfolio_heat()
                if heat > self.max_portfolio_heat * 100 * 1.5:  # 150% of limit
                    await self.send_alert(
                        AlertType.PORTFOLIO_HEAT,
                        RiskLevel.CRITICAL,
                        f"Portfolio heat critical: {heat:.1f}%",
                        {"heat": float(heat)}
                    )
                
            except Exception as e:
                logger.error(f"Position monitoring error: {e}")
                await self.send_alert(
                    AlertType.NETWORK_ERROR,
                    RiskLevel.HIGH,
                    f"Monitoring error: {str(e)}",
                    {"error": str(e)}
                )
    
    async def _generate_reports(self):
        """Generate periodic risk reports"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                report = await self.generate_risk_report()
                
                logger.info(f"Risk Report: Level={report.risk_level.value}, "
                          f"Positions={report.total_positions}, "
                          f"Heat={report.portfolio_heat:.1f}%, "
                          f"Daily P&L={report.daily_pnl:.2f}")
                
                # Send alert if risk is high
                if report.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                    await self.send_alert(
                        AlertType.PORTFOLIO_HEAT,
                        report.risk_level,
                        f"Risk level {report.risk_level.value}: Portfolio heat {report.portfolio_heat:.1f}%",
                        {"report": report.__dict__}
                    )
                
            except Exception as e:
                logger.error(f"Report generation error: {e}")
    
    async def _backup_data(self):
        """Backup trading data periodically"""
        while True:
            try:
                await asyncio.sleep(3600)  # Every hour
                
                backup_data = {
                    "timestamp": datetime.now().isoformat(),
                    "positions": {
                        pid: {
                            "symbol": p.symbol,
                            "side": p.side,
                            "entry": float(p.entry_price),
                            "current": float(p.current_price),
                            "size": float(p.size),
                            "pnl": float(p.pnl),
                            "stop_loss": float(p.stop_loss) if p.stop_loss else None
                        }
                        for pid, p in self.positions.items()
                    },
                    "daily_pnl": float(self.daily_pnl),
                    "daily_trades": self.daily_trades,
                    "alerts": [
                        {
                            "type": a.type.value,
                            "level": a.level.value,
                            "message": a.message,
                            "timestamp": a.timestamp.isoformat()
                        }
                        for a in self.alerts[-100:]  # Last 100 alerts
                    ]
                }
                
                # Save to file
                backup_file = f"risk_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(backup_file, 'w') as f:
                    json.dump(backup_data, f, indent=2)
                
                logger.info(f"Risk data backed up to {backup_file}")
                
            except Exception as e:
                logger.error(f"Backup error: {e}")
                await self.send_alert(
                    AlertType.DATABASE_BACKUP,
                    RiskLevel.MEDIUM,
                    f"Backup failed: {str(e)}",
                    {"error": str(e)}
                )