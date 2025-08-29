/**
 * Sofia V2 API Configuration
 * Non-invasive configuration for UI-API integration
 * This file does NOT modify any existing UI files
 */

window.SofiaConfig = {
    // API Configuration - sync with .env
    API_BASE: 'http://127.0.0.1:8020',
    WS_URL: 'ws://127.0.0.1:8020/ws',
    
    // Timing Configuration
    HEALTH_PING_INTERVAL: 30000, // 30 seconds
    SCORE_UPDATE_INTERVAL: 5000, // 5 seconds
    WS_RECONNECT_BASE_DELAY: 1000, // 1 second
    WS_RECONNECT_MAX_DELAY: 30000, // 30 seconds
    
    // Trading Configuration
    AUTO_TRADE_ENABLED: true,
    MIN_SCORE_THRESHOLD: 70, // Minimum score to trigger trade
    MAX_POSITION_SIZE: 10000, // Maximum USD per position
    
    // Feature Flags
    ENABLE_WEBSOCKET: true,
    ENABLE_PAPER_TRADING: true,
    ENABLE_METRICS: true,
    ENABLE_NEWS: true,
    ENABLE_WHALE_ALERTS: true,
    
    // Debug Mode
    DEBUG: true,
    
    // Symbols to track
    SYMBOLS: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
    
    // Default horizon for AI predictions
    DEFAULT_HORIZON: '15m'
};

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.SofiaConfig;
}