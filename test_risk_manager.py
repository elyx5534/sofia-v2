#!/usr/bin/env python3
"""
Test Enterprise Risk Management System
"""

import asyncio
from decimal import Decimal
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.live import Live

from src.core.enterprise_risk_manager import (
    EnterpriseRiskManager, Position, RiskLevel, AlertType
)

console = Console()

async def test_risk_manager():
    """Test the enterprise risk management system"""
    
    # Configuration
    config = {
        "max_positions": 10,
        "max_position_size": 0.05,  # 5% per position
        "max_daily_loss": 0.03,      # 3% daily loss limit
        "max_correlation": 0.7,
        "max_portfolio_heat": 0.1,   # 10% portfolio heat
        "kelly_fraction": 0.25,
        "default_stop_loss": 0.02,   # 2% stop loss
        "trailing_activation": 0.01,  # 1% profit to activate trailing
        "time_stop_hours": 24,
        "breakeven_trigger": 0.005,  # 0.5% profit to move to breakeven
        
        # Alert configurations (mock)
        "telegram": {
            "bot_token": "mock_token",
            "chat_id": "mock_chat"
        },
        "discord_webhook": "https://discord.com/api/webhooks/mock",
        "email": {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender": "alerts@sofia.com",
            "password": "mock_password",
            "recipients": ["trader@example.com"]
        }
    }
    
    # Initialize risk manager
    risk_manager = EnterpriseRiskManager(config)
    await risk_manager.initialize()
    
    console.print("[green]Enterprise Risk Manager initialized[/green]")
    
    # Test 1: Position Sizing with Kelly Criterion
    console.print("\n[cyan]Test 1: Position Sizing Algorithms[/cyan]")
    
    portfolio_value = Decimal("10000")
    win_rate = 0.6
    avg_win = Decimal("150")
    avg_loss = Decimal("100")
    
    kelly_size = risk_manager.calculate_kelly_size(
        win_rate, avg_win, avg_loss, portfolio_value
    )
    
    console.print(f"Kelly Criterion position size: ${kelly_size:.2f}")
    console.print(f"  Win rate: {win_rate:.1%}")
    console.print(f"  Avg win: ${avg_win}")
    console.print(f"  Avg loss: ${avg_loss}")
    console.print(f"  Kelly fraction: {risk_manager.kelly_fraction}")
    
    # ATR-based sizing
    atr = Decimal("100")
    price = Decimal("45000")
    risk_amount = Decimal("100")
    
    atr_size = risk_manager.calculate_atr_size(atr, price, risk_amount)
    console.print(f"\nATR-based position size: {atr_size:.4f} units")
    console.print(f"  ATR: ${atr}")
    console.print(f"  Risk amount: ${risk_amount}")
    
    # Test 2: Add positions with risk checks
    console.print("\n[cyan]Test 2: Position Management with Risk Limits[/cyan]")
    
    positions_to_add = [
        Position(
            id="POS001",
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("45000"),
            current_price=Decimal("45500"),
            size=Decimal("0.01"),
            timestamp=datetime.now()
        ),
        Position(
            id="POS002",
            symbol="ETH/USDT",
            side="long",
            entry_price=Decimal("3000"),
            current_price=Decimal("3050"),
            size=Decimal("0.5"),
            timestamp=datetime.now()
        ),
        Position(
            id="POS003",
            symbol="BNB/USDT",
            side="short",
            entry_price=Decimal("400"),
            current_price=Decimal("395"),
            size=Decimal("2"),
            timestamp=datetime.now()
        )
    ]
    
    for position in positions_to_add:
        success = await risk_manager.add_position(position)
        status = "[green]Added[/green]" if success else "[red]Rejected[/red]"
        console.print(f"  {position.id} {position.symbol}: {status}")
    
    # Test 3: Portfolio metrics
    console.print("\n[cyan]Test 3: Portfolio Risk Metrics[/cyan]")
    
    portfolio_heat = risk_manager.calculate_portfolio_heat()
    console.print(f"Portfolio heat: {portfolio_heat:.2f}%")
    
    # Add price history for correlation
    risk_manager.price_history["BTC/USDT"] = [45000 + i*100 for i in range(30)]
    risk_manager.price_history["ETH/USDT"] = [3000 + i*10 for i in range(30)]
    risk_manager.price_history["BNB/USDT"] = [400 - i*2 for i in range(30)]
    
    correlations = risk_manager.calculate_correlation_matrix(
        ["BTC/USDT", "ETH/USDT", "BNB/USDT"]
    )
    
    if correlations:
        console.print("\nCorrelation Matrix:")
        corr_table = Table(title="Asset Correlations")
        corr_table.add_column("Asset", style="cyan")
        for symbol in correlations:
            corr_table.add_column(symbol.split("/")[0], style="yellow")
        
        for symbol1 in correlations:
            row = [symbol1.split("/")[0]]
            for symbol2 in correlations:
                corr = correlations[symbol1].get(symbol2, 0)
                color = "red" if abs(corr) > 0.7 else "green" if abs(corr) < 0.3 else "yellow"
                row.append(f"[{color}]{corr:.2f}[/{color}]")
            corr_table.add_row(*row)
        
        console.print(corr_table)
    
    # Test 4: Stop loss systems
    console.print("\n[cyan]Test 4: Dynamic Stop Loss Systems[/cyan]")
    
    # Update position prices to trigger trailing stop
    if "POS001" in risk_manager.positions:
        position = risk_manager.positions["POS001"]
        position.current_price = Decimal("46000")  # Price went up
        await risk_manager.update_stop_loss("POS001", "trailing")
        console.print(f"Trailing stop for BTC: ${position.stop_loss:.2f}")
        
        # Trigger breakeven stop
        position.current_price = Decimal("45500")
        await risk_manager.update_stop_loss("POS001", "breakeven")
        console.print(f"Breakeven stop for BTC: ${position.stop_loss:.2f}")
    
    # Test 5: Risk alerts
    console.print("\n[cyan]Test 5: Alert System[/cyan]")
    
    # Simulate different alert levels
    alerts_to_send = [
        (AlertType.POSITION_SIZE, RiskLevel.MEDIUM, "Position size approaching limit"),
        (AlertType.PORTFOLIO_HEAT, RiskLevel.HIGH, "Portfolio heat elevated at 8%"),
        (AlertType.STOP_LOSS_HIT, RiskLevel.HIGH, "Stop loss triggered for ETH/USDT"),
        (AlertType.DAILY_LOSS_LIMIT, RiskLevel.CRITICAL, "Daily loss at -2.5%")
    ]
    
    for alert_type, level, message in alerts_to_send:
        await risk_manager.send_alert(alert_type, level, message, {})
        console.print(f"  [{level.value}] {alert_type.value}: {message}")
    
    # Test 6: Generate risk report
    console.print("\n[cyan]Test 6: Risk Report Generation[/cyan]")
    
    report = await risk_manager.generate_risk_report()
    
    report_table = Table(title="Risk Report", show_header=False)
    report_table.add_column("Metric", style="cyan")
    report_table.add_column("Value", style="yellow")
    
    report_table.add_row("Risk Level", f"[{report.risk_level.value}]{report.risk_level.value.upper()}[/{report.risk_level.value}]")
    report_table.add_row("Total Positions", str(report.total_positions))
    report_table.add_row("Total Exposure", f"${report.total_exposure:.2f}")
    report_table.add_row("Portfolio Heat", f"{report.portfolio_heat:.2f}%")
    report_table.add_row("Daily P&L", f"${report.daily_pnl:.2f}")
    report_table.add_row("Daily P&L %", f"{report.daily_pnl_percentage:.2f}%")
    report_table.add_row("Max Drawdown", f"{report.max_drawdown:.2f}%")
    report_table.add_row("Sharpe Ratio", f"{report.sharpe_ratio:.2f}")
    report_table.add_row("VaR (95%)", f"{report.var_95:.2f}%")
    
    console.print(report_table)
    
    # Test 7: Emergency controls
    console.print("\n[cyan]Test 7: Emergency Controls[/cyan]")
    
    # Simulate emergency callback
    emergency_triggered = False
    
    async def emergency_callback():
        nonlocal emergency_triggered
        emergency_triggered = True
        console.print("[red]Emergency callback executed![/red]")
    
    risk_manager.emergency_callback = emergency_callback
    
    # Simulate conditions that trigger emergency stop
    console.print("Simulating daily loss limit breach...")
    risk_manager.daily_pnl = Decimal("-500")  # -5% loss
    
    # This would normally trigger emergency stop
    portfolio_value = sum(p.entry_price * p.size for p in risk_manager.positions.values())
    if portfolio_value > 0 and risk_manager.daily_pnl < -portfolio_value * risk_manager.max_daily_loss:
        console.print("[red]Daily loss limit exceeded - triggering emergency stop[/red]")
        await risk_manager.emergency_stop_all("Daily loss limit exceeded")
    
    console.print(f"Emergency mode: {risk_manager.emergency_mode}")
    console.print(f"Positions remaining: {len(risk_manager.positions)}")
    
    # Test 8: Position limits validation
    console.print("\n[cyan]Test 8: Position Limit Validation[/cyan]")
    
    # Try to add position that exceeds limits
    large_position = Position(
        id="POS_LARGE",
        symbol="SOL/USDT",
        side="long",
        entry_price=Decimal("100"),
        current_price=Decimal("100"),
        size=Decimal("100"),  # Very large position
        timestamp=datetime.now()
    )
    
    can_add, reason = await risk_manager.check_position_limits(
        large_position.symbol,
        large_position.size * large_position.entry_price,
        portfolio_value
    )
    
    console.print(f"Can add large position: {can_add}")
    console.print(f"Reason: {reason}")
    
    # Show final alerts summary
    console.print("\n[cyan]Alerts Summary[/cyan]")
    
    alert_counts = {}
    for alert in risk_manager.alerts:
        key = f"{alert.level.value} - {alert.type.value}"
        alert_counts[key] = alert_counts.get(key, 0) + 1
    
    for alert_type, count in alert_counts.items():
        console.print(f"  {alert_type}: {count}")
    
    # Cleanup
    await risk_manager.shutdown()
    console.print("\n[green]Risk Manager test completed successfully![/green]")

async def main():
    """Main entry point"""
    console.print("[bold cyan]Enterprise Risk Management System Test[/bold cyan]")
    console.print("=" * 60)
    
    try:
        await test_risk_manager()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())