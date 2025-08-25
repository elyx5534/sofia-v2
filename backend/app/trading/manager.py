"""
Sofia V2 Trading Manager - Orchestrates All Trading Components
Professional trading system competing with hedge funds
"""

import asyncio
import math
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import structlog

from ..bus import EventBus, EventType
from ..config import Settings
from .engine import TradingEngine, TradingMode, Portfolio
from .strategies import (MeanReversionStrategy, MomentumBreakoutStrategy, 
                        ScalpingStrategy, GridTradingStrategy, 
                        ArbitrageStrategy, MLMomentumStrategy)
from .risk_management import RiskManager
from .indicators import MultiTimeframeAnalysis

logger = structlog.get_logger(__name__)

def _sanitize_for_json(obj):
    """Sanitize numerical values for JSON serialization"""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj

class TradingManager:
    """Master trading manager coordinating all trading activities"""
    
    def __init__(self, event_bus: EventBus, settings: Settings):
        self.event_bus = event_bus
        self.settings = settings
        
        # Get trading configuration
        trading_config = self._get_trading_config()
        
        # Initialize core components
        initial_balance = trading_config.get('initial_balance', 100000.0)
        self.portfolio = Portfolio(initial_balance, trading_config.get('max_risk_per_trade', 0.02))
        
        self.trading_engine = TradingEngine(event_bus, settings, initial_balance)
        self.risk_manager = RiskManager(self.portfolio, trading_config.get('risk_settings', {}))
        
        # Multi-timeframe analysis
        self.mtf_analysis = MultiTimeframeAnalysis()
        
        # Strategy instances
        self.strategies = {}
        self._initialize_strategies(trading_config.get('strategies', {}))
        
        # Trading state
        self.is_trading_enabled = trading_config.get('enabled', False)
        self.trading_mode = TradingMode(trading_config.get('mode', 'paper'))
        self.last_portfolio_update = datetime.now(timezone.utc)
        
        # Performance tracking
        self.daily_pnl = 0.0
        self.session_start_balance = initial_balance
        
        logger.info("Trading manager initialized",
                   initial_balance=initial_balance,
                   trading_enabled=self.is_trading_enabled,
                   mode=self.trading_mode.value,
                   strategies=list(self.strategies.keys()))
    
    def _get_trading_config(self) -> Dict[str, Any]:
        """Get trading configuration from YAML"""
        yaml_config = self.settings.yaml_config
        return yaml_config.get('trading', {
            'enabled': False,  # Start disabled by default
            'mode': 'paper',   # paper/live/backtest
            'initial_balance': 100000.0,
            'max_risk_per_trade': 0.02,
            'strategies': {
                'mean_reversion': {'enabled': True, 'weight': 0.2},
                'momentum_breakout': {'enabled': True, 'weight': 0.25},
                'scalping': {'enabled': True, 'weight': 0.15},
                'grid_trading': {'enabled': True, 'weight': 0.15},
                'arbitrage': {'enabled': True, 'weight': 0.1},
                'ml_momentum': {'enabled': True, 'weight': 0.15}
            },
            'risk_settings': {
                'max_portfolio_risk': 0.20,
                'max_position_risk': 0.05,
                'max_correlation_risk': 0.80,
                'var_confidence': 0.95
            }
        })
    
    def _initialize_strategies(self, strategy_configs: Dict[str, Any]):
        """Initialize all trading strategies"""
        available_strategies = {
            'mean_reversion': MeanReversionStrategy,
            'momentum_breakout': MomentumBreakoutStrategy,
            'scalping': ScalpingStrategy,
            'grid_trading': GridTradingStrategy,
            'arbitrage': ArbitrageStrategy,
            'ml_momentum': MLMomentumStrategy
        }
        
        for strategy_name, config in strategy_configs.items():
            if config.get('enabled', False) and strategy_name in available_strategies:
                try:
                    strategy_class = available_strategies[strategy_name]
                    strategy_instance = strategy_class(self.portfolio, config.get('settings', {}))
                    
                    # Set strategy weight for position sizing
                    strategy_instance.weight = config.get('weight', 0.1)
                    
                    self.strategies[strategy_name] = strategy_instance
                    self.trading_engine.add_strategy(strategy_instance)
                    
                    logger.info("Strategy initialized",
                               strategy=strategy_name,
                               weight=strategy_instance.weight)
                    
                except Exception as e:
                    logger.error("Failed to initialize strategy",
                               strategy=strategy_name,
                               error=str(e))
    
    async def start_trading(self):
        """Start the trading system"""
        if not self.is_trading_enabled:
            logger.warning("Trading is disabled in configuration")
            return
        
        self.trading_engine.set_trading_mode(self.trading_mode)
        
        # Subscribe to trading events
        self.event_bus.subscribe(EventType.BIG_TRADE, self._handle_trade_execution)
        
        # Start background tasks
        asyncio.create_task(self._portfolio_monitoring_loop())
        asyncio.create_task(self._risk_monitoring_loop())
        asyncio.create_task(self._performance_reporting_loop())
        
        logger.info("Trading system started",
                   mode=self.trading_mode.value,
                   strategies_count=len(self.strategies))
    
    async def stop_trading(self):
        """Stop trading and close all positions"""
        logger.info("Stopping trading system...")
        
        # Close all open positions
        for symbol in list(self.portfolio.positions.keys()):
            await self._close_position(symbol, "System shutdown")
        
        # Disable all strategies
        for strategy in self.strategies.values():
            strategy.enabled = False
        
        logger.info("Trading system stopped")
    
    async def _handle_trade_execution(self, trade_event: Dict[str, Any]):
        """Handle trade execution events from strategies"""
        try:
            if trade_event.get('type') == 'position_opened':
                await self._log_trade_execution(trade_event, 'OPEN')
            elif trade_event.get('type') == 'position_closed':
                await self._log_trade_execution(trade_event, 'CLOSE')
                
        except Exception as e:
            logger.error("Trade execution handling error", error=str(e))
    
    async def _log_trade_execution(self, trade_event: Dict[str, Any], action: str):
        """Log trade execution for monitoring"""
        logger.info("Trade executed",
                   action=action,
                   strategy=trade_event.get('strategy'),
                   symbol=trade_event.get('symbol'),
                   side=trade_event.get('side'),
                   size=trade_event.get('size'),
                   price=trade_event.get('entry_price', trade_event.get('price')),
                   pnl=trade_event.get('pnl', 0))
        
        # Update daily PnL
        if action == 'CLOSE':
            self.daily_pnl += trade_event.get('pnl', 0)
    
    async def _close_position(self, symbol: str, reason: str):
        """Force close a position"""
        if symbol in self.portfolio.positions:
            position = self.portfolio.positions[symbol]
            # In paper trading, we simulate the close
            pnl = self.portfolio.close_position(
                symbol, 
                position.current_price, 
                datetime.now(timezone.utc)
            )
            
            logger.info("Position force closed",
                       symbol=symbol,
                       reason=reason,
                       pnl=pnl)
    
    async def _portfolio_monitoring_loop(self):
        """Monitor portfolio and update risk metrics"""
        while True:
            try:
                # Update portfolio performance data
                current_time = datetime.now(timezone.utc)
                
                # Update risk manager with current performance
                self.risk_manager.update_performance_data(self.portfolio.current_balance)
                
                # Check if rebalancing is needed
                if self.risk_manager.should_rebalance_portfolio():
                    await self._rebalance_portfolio()
                
                self.last_portfolio_update = current_time
                
                # Sleep for 1 minute
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info("Portfolio monitoring stopped")
                break
            except Exception as e:
                logger.error("Portfolio monitoring error", error=str(e))
                await asyncio.sleep(60)
    
    async def _risk_monitoring_loop(self):
        """Monitor risk metrics and generate alerts"""
        while True:
            try:
                # Generate risk report
                risk_report = self.risk_manager.generate_risk_report()
                
                # Check for critical risk alerts
                critical_alerts = [
                    alert for alert in risk_report['risk_alerts'] 
                    if alert.get('severity') == 'critical'
                ]
                
                if critical_alerts:
                    await self._handle_critical_risk_alerts(critical_alerts)
                
                # Log risk summary
                if len(risk_report['risk_alerts']) > 0:
                    logger.warning("Risk alerts active",
                                 alerts_count=len(risk_report['risk_alerts']),
                                 risk_level=risk_report['risk_metrics']['risk_level'])
                
                # Sleep for 5 minutes
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                logger.info("Risk monitoring stopped")
                break
            except Exception as e:
                logger.error("Risk monitoring error", error=str(e))
                await asyncio.sleep(300)
    
    async def _performance_reporting_loop(self):
        """Generate periodic performance reports"""
        while True:
            try:
                # Generate performance report every hour
                await asyncio.sleep(3600)  # 1 hour
                
                performance_report = self._generate_performance_report()
                
                # Emit performance event
                await self.event_bus.publish(EventType.BIG_TRADE, {
                    'type': 'performance_report',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'report': performance_report
                })
                
                logger.info("Performance report generated",
                           total_return=performance_report['total_return_pct'],
                           daily_pnl=self.daily_pnl,
                           positions=len(self.portfolio.positions))
                
            except asyncio.CancelledError:
                logger.info("Performance reporting stopped")
                break
            except Exception as e:
                logger.error("Performance reporting error", error=str(e))
                await asyncio.sleep(3600)
    
    async def _handle_critical_risk_alerts(self, alerts: List[Dict[str, Any]]):
        """Handle critical risk alerts"""
        logger.critical("CRITICAL RISK ALERTS TRIGGERED", alerts=alerts)
        
        # In case of critical risk, consider:
        # 1. Reducing position sizes
        # 2. Closing risky positions
        # 3. Disabling aggressive strategies
        
        for alert in alerts:
            if alert['type'] == 'drawdown' and 'maximum drawdown' in alert['message']:
                # Close some positions to reduce risk
                await self._emergency_risk_reduction()
    
    async def _emergency_risk_reduction(self):
        """Emergency risk reduction procedures"""
        logger.warning("Initiating emergency risk reduction")
        
        # Close positions with highest risk
        risky_positions = []
        for symbol, position in self.portfolio.positions.items():
            if position.stop_loss:
                risk = abs(position.current_price - position.stop_loss) * position.size
                risky_positions.append((symbol, risk))
        
        # Sort by risk (highest first) and close top positions
        risky_positions.sort(key=lambda x: x[1], reverse=True)
        
        for symbol, risk in risky_positions[:3]:  # Close top 3 risky positions
            await self._close_position(symbol, "Emergency risk reduction")
    
    async def _rebalance_portfolio(self):
        """Rebalance portfolio based on risk metrics"""
        logger.info("Portfolio rebalancing initiated")
        
        # Simple rebalancing logic
        total_value = self.portfolio.current_balance
        max_position_size = total_value * 0.05  # 5% max per position
        
        for symbol, position in list(self.portfolio.positions.items()):
            position_value = position.size * position.current_price
            
            if position_value > max_position_size:
                # Reduce position size
                target_size = max_position_size / position.current_price
                reduction = position.size - target_size
                
                if reduction > 0:
                    # Simulate partial close
                    partial_pnl = self.portfolio.close_position(
                        f"{symbol}_partial", 
                        position.current_price, 
                        datetime.now(timezone.utc)
                    )
                    
                    # Update position size
                    position.size = target_size
                    
                    logger.info("Position rebalanced",
                               symbol=symbol,
                               old_size=position.size + reduction,
                               new_size=target_size,
                               pnl=partial_pnl)
        
        self.risk_manager.last_rebalance = datetime.now(timezone.utc)
    
    def _generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        portfolio_metrics = self.portfolio.get_metrics()
        risk_metrics = self.risk_manager.calculate_portfolio_risk()
        engine_status = self.trading_engine.get_status()
        
        # Session performance
        session_return = (self.portfolio.current_balance - self.session_start_balance) / self.session_start_balance * 100
        
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'portfolio_metrics': portfolio_metrics,
            'risk_metrics': {
                'sharpe_ratio': risk_metrics.sharpe_ratio,
                'max_drawdown_pct': risk_metrics.max_drawdown * 100,
                'volatility_pct': risk_metrics.volatility * 100,
                'var_95_pct': risk_metrics.var_95 * 100,
                'risk_level': risk_metrics.risk_level.value
            },
            'trading_metrics': {
                'strategies_active': len([s for s in self.strategies.values() if s.enabled]),
                'total_signals': sum(s.total_signals for s in self.strategies.values()),
                'session_return_pct': session_return,
                'daily_pnl': self.daily_pnl,
                'positions_count': len(self.portfolio.positions)
            },
            'strategy_performance': {
                name: {
                    'total_signals': strategy.total_signals,
                    'success_rate': strategy.successful_signals / max(strategy.total_signals, 1) * 100,
                    'enabled': strategy.enabled
                }
                for name, strategy in self.strategies.items()
            }
        }
    
    def enable_trading(self):
        """Enable trading system"""
        self.is_trading_enabled = True
        logger.info("Trading system enabled")
    
    def disable_trading(self):
        """Disable trading system"""
        self.is_trading_enabled = False
        for strategy in self.strategies.values():
            strategy.enabled = False
        logger.info("Trading system disabled")
    
    def enable_strategy(self, strategy_name: str) -> bool:
        """Enable specific strategy"""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].enabled = True
            logger.info("Strategy enabled", strategy=strategy_name)
            return True
        return False
    
    def disable_strategy(self, strategy_name: str) -> bool:
        """Disable specific strategy"""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].enabled = False
            logger.info("Strategy disabled", strategy=strategy_name)
            return True
        return False
    
    def get_trading_status(self) -> Dict[str, Any]:
        """Get comprehensive trading system status"""
        portfolio_metrics = self.portfolio.get_metrics()
        risk_report = self.risk_manager.generate_risk_report()
        engine_status = self.trading_engine.get_status()
        
        result = {
            'trading_enabled': self.is_trading_enabled,
            'trading_mode': self.trading_mode.value,
            'portfolio': portfolio_metrics,
            'risk_summary': {
                'risk_level': risk_report['risk_metrics']['risk_level'],
                'total_portfolio_risk_pct': risk_report['total_portfolio_risk_pct'],
                'max_drawdown_pct': risk_report['risk_metrics']['max_drawdown_pct'],
                'sharpe_ratio': risk_report['risk_metrics']['sharpe_ratio'],
                'alerts_count': len(risk_report['risk_alerts'])
            },
            'strategies': {
                name: {
                    'enabled': strategy.enabled,
                    'total_signals': strategy.total_signals,
                    'weight': getattr(strategy, 'weight', 0.1)
                }
                for name, strategy in self.strategies.items()
            },
            'engine_status': engine_status,
            'session_performance': {
                'session_return_pct': (self.portfolio.current_balance - self.session_start_balance) / self.session_start_balance * 100,
                'daily_pnl': self.daily_pnl,
                'uptime_minutes': engine_status.get('uptime_seconds', 0) / 60
            }
        }
        
        # Sanitize for JSON serialization
        return _sanitize_for_json(result)