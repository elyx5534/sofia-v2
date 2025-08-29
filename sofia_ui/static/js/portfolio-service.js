/**
 * Portfolio Service - Single source of truth for portfolio data and Total Balance calculation
 */

// Import Decimal.js for precision calculations
const Decimal = window.Decimal || function(val) { 
    return { 
        valueOf: () => parseFloat(val), 
        toString: () => String(val),
        plus: function(other) { return new Decimal(this.valueOf() + parseFloat(other)); },
        minus: function(other) { return new Decimal(this.valueOf() - parseFloat(other)); },
        mul: function(other) { return new Decimal(this.valueOf() * parseFloat(other)); },
        toFixed: function(dp) { return this.valueOf().toFixed(dp); }
    };
};

class PortfolioService {
    constructor() {
        this.apiUrl = window.API_URL || 'http://127.0.0.1:8023';
        this.cache = null;
        this.lastFetch = null;
        this.cacheTimeout = 30000; // 30 seconds
        this.listeners = [];
    }

    /**
     * Convert amount from one currency to another using FX rates
     */
    convert(amount, fromCurrency, toCurrency, fxRates) {
        if (fromCurrency === toCurrency) {
            return new Decimal(amount);
        }
        
        const directRate = fxRates[`${fromCurrency}${toCurrency}`];
        if (directRate) {
            return new Decimal(amount).mul(new Decimal(directRate));
        }
        
        const inverseRate = fxRates[`${toCurrency}${fromCurrency}`];
        if (inverseRate) {
            return new Decimal(amount).mul(new Decimal(1).div(new Decimal(inverseRate)));
        }
        
        // Default to 1:1 if no rate found
        console.warn(`No FX rate found for ${fromCurrency}/${toCurrency}`);
        return new Decimal(amount);
    }

    /**
     * Calculate Total Balance from portfolio summary
     * Formula: TB = cash_balance + Σ(position.qty * mark_price) - fees_accrued
     */
    calculateTotalBalance(summary) {
        if (!summary) return new Decimal(0);
        
        const baseCurrency = summary.base_currency || 'USD';
        const cash = new Decimal(summary.cash_balance || 0);
        const fees = new Decimal(summary.fees_accrued || 0);
        const fxRates = summary.fx_rates || {};
        
        // Calculate positions value
        let positionsValue = new Decimal(0);
        if (summary.positions && Array.isArray(summary.positions)) {
            for (const position of summary.positions) {
                const qty = new Decimal(position.qty || 0);
                const price = new Decimal(position.mark_price || 0);
                const value = qty.mul(price);
                
                // Convert to base currency if needed
                const convertedValue = this.convert(
                    value,
                    position.currency || baseCurrency,
                    baseCurrency,
                    fxRates
                );
                
                positionsValue = positionsValue.plus(convertedValue);
            }
        }
        
        // Calculate total balance
        return cash.plus(positionsValue).minus(fees);
    }

    /**
     * Format money value with currency symbol
     */
    formatMoney(value, currency = 'USD') {
        const symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'TRY': '₺',
            'USDT': 'USDT '
        };
        
        const symbol = symbols[currency] || currency + ' ';
        const amount = value instanceof Decimal ? value.toFixed(2) : parseFloat(value).toFixed(2);
        
        // Add thousand separators
        const parts = amount.split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        
        return symbol + parts.join('.');
    }

    /**
     * Fetch portfolio summary from API
     */
    async fetchPortfolioSummary(force = false) {
        // Check cache
        if (!force && this.cache && this.lastFetch) {
            const age = Date.now() - this.lastFetch;
            if (age < this.cacheTimeout) {
                return this.cache;
            }
        }

        try {
            const response = await fetch(`${this.apiUrl}/portfolio/summary`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                },
                signal: AbortSignal.timeout(6000) // 6 second timeout
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Calculate and add total balance
            data.total_balance_calculated = this.calculateTotalBalance(data);
            
            // Update cache
            this.cache = data;
            this.lastFetch = Date.now();
            
            // Notify listeners
            this.notifyListeners(data);
            
            return data;
        } catch (error) {
            console.error('Error fetching portfolio summary:', error);
            
            // Return cached data if available
            if (this.cache) {
                console.log('Returning cached data due to error');
                return this.cache;
            }
            
            // Return mock data as fallback
            return this.getMockData();
        }
    }

    /**
     * Get mock portfolio data for testing
     */
    getMockData() {
        const mockData = {
            base_currency: "USD",
            cash_balance: "50000.00",
            fees_accrued: "125.50",
            positions: [
                {
                    symbol: "BTC/USDT",
                    qty: "0.5",
                    mark_price: "67500.00",
                    currency: "USDT",
                    unrealized_pnl: "2500.00"
                },
                {
                    symbol: "ETH/USDT",
                    qty: "10",
                    mark_price: "3200.00",
                    currency: "USDT",
                    unrealized_pnl: "500.00"
                },
                {
                    symbol: "AAPL",
                    qty: "100",
                    mark_price: "175.50",
                    currency: "USD",
                    unrealized_pnl: "1250.00"
                }
            ],
            fx_rates: {
                "USDTUSD": "1.00",
                "USDTRY": "34.50"
            },
            timestamp: new Date().toISOString()
        };
        
        mockData.total_balance_calculated = this.calculateTotalBalance(mockData);
        return mockData;
    }

    /**
     * Subscribe to portfolio updates
     */
    subscribe(callback) {
        this.listeners.push(callback);
        return () => {
            this.listeners = this.listeners.filter(cb => cb !== callback);
        };
    }

    /**
     * Notify all listeners of data changes
     */
    notifyListeners(data) {
        this.listeners.forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                console.error('Error in portfolio listener:', error);
            }
        });
    }

    /**
     * Start auto-refresh
     */
    startAutoRefresh(interval = 30000) {
        this.stopAutoRefresh();
        this.refreshInterval = setInterval(() => {
            this.fetchPortfolioSummary(true);
        }, interval);
    }

    /**
     * Stop auto-refresh
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
}

// Create singleton instance
const portfolioService = new PortfolioService();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = portfolioService;
} else {
    window.portfolioService = portfolioService;
}