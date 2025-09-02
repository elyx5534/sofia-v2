# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.2.0] - 2025-09-02

### 🚀 Titan Pilot Readiness Release

This major release introduces the complete TITAN feature set (A-N) and GL pilot trading system (1-6), bringing production-ready capabilities for safe micro-live trading with comprehensive monitoring and safety controls.

### Added

#### TITAN Features (A-N)
- **Route Optimizer (A)**: Smart route selection with A/B testing capability
- **Turkish Tax Model (B)**: BSMV, stamp duty, and stopaj calculations for accurate P&L
- **Expected Value Gate v2 (C)**: Probabilistic trade filtering with fill probability modeling
- **Hash-Chained Audit (D)**: Tamper-evident logging with SHA256 chains
- **Monte Carlo Risk (E)**: 10,000-path simulations for robust risk assessment
- **Z-Score Anomaly Guard (F)**: Real-time anomaly detection with auto-pause triggers
- **Delta-Neutral Funding (G)**: Advanced funding rate strategies with borrow cost modeling
- **Blue-Green Deploy (H)**: Zero-downtime deployment with health checks
- **Kill Switch Tests (I)**: Fault injection and resilience testing
- **Shadow vs Paper (J)**: Comprehensive comparison reporting
- **Grid Parameter Sweep (K)**: Automated parameter optimization
- **Campaign Runner (L)**: Multi-day paper trading campaigns
- **Micro Scalper MM-Lite (M)**: Maker-only strategy (PAPER ONLY)
- **Profit Attribution (N)**: Detailed P&L attribution by symbol/hour

#### GL Pilot Trading System (1-6)
- **GL-1: 24h Proof Sprint**: 3-session campaign with Symbol Plan and EV Gate
- **GL-2: GO/NO-GO Wall**: Strict readiness gate with 12 criteria (all must pass)
- **GL-3: Micro-Live Toggle**: Safe pilot mode with two-man approval
- **GL-4: Pilot Telemetry**: 5-second interval monitoring with day reports
- **GL-5: Auto Rollback**: Emergency shutdown with incident snapshots
- **GL-6: Post-Pilot Learning**: EV impact analysis and next-day planning

#### Development Tools
- **Developer Console (/dev)**: Real-time monitoring and control panel
- **Job Runner**: Background task execution with SSE streaming
- **Dev Environment Launcher**: One-command startup with auto browser opening
- **Health Monitoring**: Comprehensive health checks across all services

### Enhanced
- **API Structure**: Improved organization with dedicated routers
- **Testing Coverage**: Expanded test suite with >70% coverage target
- **Error Handling**: Consistent error responses with detailed messages
- **Logging**: Structured logging with separate streams for different components
- **Documentation**: Comprehensive pilot workflow and README updates

### Security
- **Release Scanner**: Automated secret detection before releases
- **Two-Man Rule**: Dual approval requirement for live trading
- **Micro Caps**: Strict position limits (100-250 TL per trade)
- **Time Windows**: Trading restricted to 10:00-18:00 Istanbul time
- **Emergency Stop**: Instant shutdown with full state preservation

### Fixed
- Windows compatibility issues with emoji encoding
- Path handling for cross-platform support
- WebSocket connection stability
- Memory leaks in long-running processes
- Race conditions in concurrent operations

### Performance
- Optimized database queries with proper indexing
- Reduced API latency with caching layers
- Improved backtest engine speed (5x faster)
- Streamlined data pipeline with batch processing

## [v0.1.0] - 2025-08-25

### Initial Release
- Basic trading infrastructure
- Paper trading engine
- Simple backtesting
- API endpoints
- Basic UI dashboard

---

## Key Highlights

### Safety Features
- **Strict Readiness Gate**: ALL 12 criteria must pass for GO decision
- **Auto-Pause Triggers**: Anomaly, reconciliation fail, or drawdown breach
- **Incident Snapshots**: Complete evidence collection on emergency stop
- **Warmup Mode**: Start with reduced capital limits

### Monitoring & Reporting
- **Real-time Telemetry**: 5-second interval metrics collection
- **Daily Reports**: Comprehensive P&L with Turkish tax calculations
- **Attribution Analysis**: Performance breakdown by symbol and time
- **EV Impact**: Correlation between predicted and realized outcomes

### Developer Experience
- **make up**: Start everything with auto browser opening
- **make quick-campaign**: Run 24-hour proof sprint
- **make readiness-v2**: Check GO/NO-GO status
- **make live-on**: Enable pilot trading (with approvals)
- **make pilot-off**: Emergency shutdown

### File Structure
```
logs/             # Service and trading logs
reports/          # Campaign and daily reports
incidents/        # Emergency snapshots
artifacts/        # Build and scan reports
config/           # Live trading configuration
.dev/             # Development runtime files
```

### Commit Convention
This project follows conventional commits:
- `feat:` New features
- `fix:` Bug fixes
- `ops:` Operations and deployment
- `test:` Testing improvements
- `docs:` Documentation updates
- `perf:` Performance improvements
- `security:` Security enhancements