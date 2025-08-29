/**
 * Enhanced Portfolio Service with Decimal.js precision
 * Single source of truth for Total Balance calculation
 */

// Load Decimal.js from CDN (add to HTML: <script src="https://cdn.jsdelivr.net/npm/decimal.js-light@2.5.1/decimal.min.js"></script>)
const Decimal = window.Decimal || function(value) { return { toString: () => String(value) }; };

// Configuration
const CONFIG = {
    API_BASE: window.location.port === '8004' ? 'http://127.0.0.1:8022' : 'http://127.0.0.1:8020',
    REFRESH_INTERVAL: 30000, // 30 seconds
    TIMEOUT_MS: 6000,
    MAX_RETRIES: 2,
    BACKOFF_BASE: 500
};

// Portfolio state management
class PortfolioService {
    constructor() {
        this.state = {
            loading: false,
            error: null,
            data: null,
            lastUpdate: null
        };
        this.subscribers = new Set();
        this.abortController = null;
        this.refreshTimer = null;
    }

    // Decimal utilities
    toDecimal(value) {
        if (!value) return new Decimal(0);
        return new Decimal(String(value));
    }

    // FX conversion
    convert(amount, fromCurrency, toCurrency, fxRates) {
        if (fromCurrency === toCurrency) return amount;
        
        const directKey = `${fromCurrency}${toCurrency}`;
        const reverseKey = `${toCurrency}${fromCurrency}`;
        
        if (fxRates[directKey]) {
            return amount.mul(this.toDecimal(fxRates[directKey]));
        } else if (fxRates[reverseKey]) {
            return amount.div(this.toDecimal(fxRates[reverseKey]));
        }
        
        // Default: assume 1:1 for USDT/USD
        if ((fromCurrency === 'USDT' && toCurrency === 'USD') ||
            (fromCurrency === 'USD' && toCurrency === 'USDT')) {
            return amount;
        }
        
        throw new Error(`No FX rate for ${fromCurrency}/${toCurrency}`);
    }

    // Calculate Total Balance (single source of truth)
    calculateTotalBalance(summary) {
        if (!summary) return new Decimal(0);
        
        const baseCurrency = summary.base_currency || 'USD';
        const cashBalance = this.toDecimal(summary.cash_balance);
        const feesAccrued = this.toDecimal(summary.fees_accrued || 0);
        
        // Calculate positions value
        let positionsValue = new Decimal(0);
        if (summary.positions && Array.isArray(summary.positions)) {
            for (const position of summary.positions) {
                const qty = this.toDecimal(position.qty);
                const price = this.toDecimal(position.mark_price);
                let value = qty.mul(price);
                
                // Convert to base currency if needed
                if (position.currency !== baseCurrency) {
                    try {
                        value = this.convert(value, position.currency, baseCurrency, summary.fx_rates || {});
                    } catch (e) {
                        console.warn(`FX conversion failed for ${position.symbol}:`, e);
                    }
                }
                
                positionsValue = positionsValue.plus(value);
            }
        }
        
        // Total Balance = cash + positions - fees
        return cashBalance.plus(positionsValue).minus(feesAccrued);
    }

    // Format money with currency symbol
    formatMoney(value, currency = 'USD') {
        const decimal = value instanceof Decimal ? value : this.toDecimal(value);
        const num = parseFloat(decimal.toString());
        
        const symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'TRY': '₺',
            'USDT': 'USDT '
        };
        
        const symbol = symbols[currency] || currency + ' ';
        const formatted = num.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        
        return symbol === '$' ? `${symbol}${formatted}` : `${formatted} ${symbol}`;
    }

    // Format percentage
    formatPercentage(value) {
        const num = parseFloat(String(value));
        if (isNaN(num)) return { text: '0.00%', color: 'text-gray-400' };
        
        const formatted = Math.abs(num).toFixed(2) + '%';
        const prefix = num > 0 ? '+' : num < 0 ? '-' : '';
        
        return {
            text: prefix + formatted,
            color: num > 0 ? 'text-green-400' : num < 0 ? 'text-red-400' : 'text-gray-400'
        };
    }

    // Fetch with retry and timeout
    async fetchWithRetry(url, options = {}, retries = CONFIG.MAX_RETRIES) {
        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                // Create abort controller for this attempt
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), CONFIG.TIMEOUT_MS);
                
                const response = await fetch(url, {
                    ...options,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                return await response.json();
            } catch (error) {
                console.error(`Attempt ${attempt + 1} failed:`, error);
                
                if (attempt === retries) {
                    throw error;
                }
                
                // Exponential backoff
                const delay = CONFIG.BACKOFF_BASE * Math.pow(2, attempt);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
    }

    // Load portfolio data
    async loadPortfolio() {
        // Cancel any pending request
        if (this.abortController) {
            this.abortController.abort();
        }
        
        this.abortController = new AbortController();
        this.updateState({ loading: true, error: null });
        
        try {
            const data = await this.fetchWithRetry(
                `${CONFIG.API_BASE}/portfolio/summary`,
                { signal: this.abortController.signal }
            );
            
            // Calculate total balance if not provided by backend
            if (!data.total_balance) {
                const totalBalance = this.calculateTotalBalance(data);
                data.total_balance = totalBalance.toString();
            }
            
            this.updateState({
                loading: false,
                error: null,
                data: data
            });
            
            return data;
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('Request cancelled');
                return null;
            }
            
            this.updateState({
                loading: false,
                error: error.message || 'Failed to load portfolio'
            });
            
            throw error;
        }
    }

    // Update state and notify subscribers
    updateState(updates) {
        this.state = {
            ...this.state,
            ...updates,
            lastUpdate: new Date()
        };
        
        this.notifySubscribers();
    }

    // Notify all subscribers
    notifySubscribers() {
        this.subscribers.forEach(callback => {
            try {
                callback(this.state);
            } catch (error) {
                console.error('Subscriber error:', error);
            }
        });
    }

    // Subscribe to state changes
    subscribe(callback) {
        this.subscribers.add(callback);
        callback(this.state); // Immediate callback
        
        return () => this.subscribers.delete(callback);
    }

    // Start auto-refresh
    startAutoRefresh() {
        this.stopAutoRefresh();
        
        this.refreshTimer = setInterval(() => {
            this.loadPortfolio().catch(console.error);
        }, CONFIG.REFRESH_INTERVAL);
    }

    // Stop auto-refresh
    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    // Cleanup
    destroy() {
        this.stopAutoRefresh();
        if (this.abortController) {
            this.abortController.abort();
        }
        this.subscribers.clear();
    }
}

// Paper Trading Service
class PaperTradingService {
    constructor() {
        this.API_BASE = CONFIG.API_BASE;
    }

    async placeOrder(symbol, side, quantity) {
        const response = await fetch(`${this.API_BASE}/paper/orders`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                symbol,
                side,
                quantity: String(quantity),
                order_type: 'market'
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Order failed');
        }
        
        return response.json();
    }

    async getPortfolio() {
        const response = await fetch(`${this.API_BASE}/paper/portfolio`);
        return response.json();
    }

    async getPositions() {
        const response = await fetch(`${this.API_BASE}/paper/positions`);
        return response.json();
    }

    async getOrders(limit = 50) {
        const response = await fetch(`${this.API_BASE}/paper/orders?limit=${limit}`);
        return response.json();
    }

    async reset() {
        const response = await fetch(`${this.API_BASE}/paper/reset`, {
            method: 'POST'
        });
        return response.json();
    }
}

// Initialize services
const portfolioService = new PortfolioService();
const paperTradingService = new PaperTradingService();

// UI Update functions
function updatePortfolioUI(state) {
    const elements = {
        totalBalance: document.getElementById('total-balance'),
        totalBalanceChange: document.getElementById('total-balance-change'),
        todaysPnl: document.getElementById('todays-pnl'),
        todaysPnlPercent: document.getElementById('todays-pnl-percent'),
        positionsCount: document.getElementById('positions-count'),
        cashBalance: document.getElementById('cash-balance')
    };
    
    // Show loading state
    if (state.loading && !state.data) {
        if (elements.totalBalance) {
            elements.totalBalance.innerHTML = '<span class="animate-pulse">Loading...</span>';
        }
        return;
    }
    
    // Show error state
    if (state.error) {
        if (elements.totalBalance) {
            elements.totalBalance.innerHTML = `<span class="text-red-400">Error: ${state.error}</span>`;
        }
        return;
    }
    
    // Update with real data
    if (state.data) {
        const data = state.data;
        
        // Total Balance
        if (elements.totalBalance) {
            const tb = portfolioService.calculateTotalBalance(data);
            elements.totalBalance.textContent = portfolioService.formatMoney(tb, data.base_currency);
            elements.totalBalance.setAttribute('data-value', tb.toString());
        }
        
        // 24h Change
        if (elements.totalBalanceChange) {
            const pct = portfolioService.formatPercentage(data.pnl_percentage_24h);
            elements.totalBalanceChange.innerHTML = `
                <span class="${pct.color}">${pct.text}</span>
                <span class="text-xs text-slate-500 ml-2">24h</span>
            `;
        }
        
        // Today's P&L
        if (elements.todaysPnl) {
            const pnl = parseFloat(data.pnl_24h || 0);
            const color = pnl >= 0 ? 'text-green-400' : 'text-red-400';
            elements.todaysPnl.className = `text-2xl font-bold ${color} mb-1`;
            elements.todaysPnl.textContent = portfolioService.formatMoney(Math.abs(pnl), data.base_currency);
        }
        
        // Positions
        if (elements.positionsCount && data.positions) {
            elements.positionsCount.textContent = data.positions.length;
        }
        
        // Cash Balance
        if (elements.cashBalance) {
            elements.cashBalance.textContent = portfolioService.formatMoney(data.cash_balance, data.base_currency);
        }
    }
}

// Initialize on DOM ready
function initPortfolio() {
    // Subscribe to portfolio updates
    portfolioService.subscribe(updatePortfolioUI);
    
    // Load initial data
    portfolioService.loadPortfolio();
    
    // Start auto-refresh
    portfolioService.startAutoRefresh();
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        portfolioService.destroy();
    });
}

// Auto-init
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPortfolio);
} else {
    initPortfolio();
}

// Export for use in other modules
window.PortfolioService = portfolioService;
window.PaperTradingService = paperTradingService;