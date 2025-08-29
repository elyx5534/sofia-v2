/**
 * Portfolio Service - Single source of truth for Total Balance
 * Uses Decimal precision for all calculations
 */

// API configuration - Check both ports
const API_BASE = window.location.port === '8004' 
    ? 'http://127.0.0.1:8022'  // When UI is on 8004, API is on 8022
    : 'http://127.0.0.1:8020'; // Default API port

// Portfolio state
let portfolioState = {
    loading: true,
    error: null,
    data: null,
    lastUpdate: null
};

// Subscribers for state changes
const subscribers = new Set();

/**
 * Format money with proper currency symbol and precision
 * @param {string|number} value - The value to format
 * @param {string} currency - Currency code (USD, EUR, etc.)
 * @returns {string} Formatted money string
 */
function formatMoney(value, currency = 'USD') {
    const num = parseFloat(value);
    if (isNaN(num)) return `${currency} 0.00`;
    
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

/**
 * Format percentage with color
 * @param {string|number} value - The percentage value
 * @returns {object} Object with formatted text and color class
 */
function formatPercentage(value) {
    const num = parseFloat(value);
    if (isNaN(num)) return { text: '0.00%', color: 'text-gray-400' };
    
    const formatted = num.toFixed(2) + '%';
    const color = num > 0 ? 'text-green-400' : num < 0 ? 'text-red-400' : 'text-gray-400';
    const prefix = num > 0 ? '+' : '';
    
    return {
        text: prefix + formatted,
        color: color
    };
}

/**
 * Fetch portfolio summary from API
 * @param {AbortSignal} signal - Optional abort signal for cancellation
 * @returns {Promise<object>} Portfolio data
 */
async function fetchPortfolioSummary(signal = null) {
    const options = {
        method: 'GET',
        headers: {
            'Accept': 'application/json',
        }
    };
    
    if (signal) options.signal = signal;
    
    // Add timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 6000); // 6 second timeout
    
    try {
        const response = await fetch(`${API_BASE}/portfolio/summary`, {
            ...options,
            signal: signal || controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Request timeout');
        }
        throw error;
    }
}

/**
 * Update portfolio state and notify subscribers
 * @param {object} newState - New state properties
 */
function updateState(newState) {
    portfolioState = { ...portfolioState, ...newState };
    portfolioState.lastUpdate = new Date();
    
    // Notify all subscribers
    subscribers.forEach(callback => {
        try {
            callback(portfolioState);
        } catch (error) {
            console.error('Subscriber error:', error);
        }
    });
}

/**
 * Subscribe to portfolio state changes
 * @param {function} callback - Function to call on state change
 * @returns {function} Unsubscribe function
 */
function subscribe(callback) {
    subscribers.add(callback);
    // Immediately call with current state
    callback(portfolioState);
    
    // Return unsubscribe function
    return () => subscribers.delete(callback);
}

/**
 * Load portfolio data with retry logic
 * @param {number} retries - Number of retries
 */
async function loadPortfolio(retries = 2) {
    updateState({ loading: true, error: null });
    
    let lastError = null;
    
    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const data = await fetchPortfolioSummary();
            updateState({ 
                loading: false, 
                error: null, 
                data: data 
            });
            return data;
        } catch (error) {
            lastError = error;
            console.error(`Portfolio fetch attempt ${attempt + 1} failed:`, error);
            
            if (attempt < retries) {
                // Exponential backoff
                const delay = Math.min(1000 * Math.pow(2, attempt), 5000);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
    }
    
    updateState({ 
        loading: false, 
        error: lastError.message || 'Failed to load portfolio data'
    });
    return null;
}

/**
 * Update UI elements with portfolio data
 */
function updatePortfolioUI() {
    const state = portfolioState;
    
    // Get UI elements
    const totalBalanceEl = document.getElementById('total-balance');
    const totalBalanceChangeEl = document.getElementById('total-balance-change');
    const todaysPnlEl = document.getElementById('todays-pnl');
    const todaysPnlPercentEl = document.getElementById('todays-pnl-percent');
    const positionsCountEl = document.getElementById('positions-count');
    const cashBalanceEl = document.getElementById('cash-balance');
    
    // Show loading state
    if (state.loading) {
        if (totalBalanceEl) {
            totalBalanceEl.innerHTML = '<span class="animate-pulse">Loading...</span>';
        }
        return;
    }
    
    // Show error state
    if (state.error) {
        if (totalBalanceEl) {
            totalBalanceEl.innerHTML = '<span class="text-red-400">Error loading</span>';
        }
        return;
    }
    
    // Update with real data
    if (state.data) {
        const data = state.data;
        
        // Total Balance
        if (totalBalanceEl) {
            totalBalanceEl.textContent = formatMoney(data.total_balance, data.base_currency);
        }
        
        // 24h Change
        if (totalBalanceChangeEl) {
            const pctData = formatPercentage(data.pnl_percentage_24h);
            totalBalanceChangeEl.innerHTML = `
                <span class="${pctData.color}">${pctData.text}</span>
                <span class="text-xs text-slate-500">24h</span>
            `;
        }
        
        // Today's P&L
        if (todaysPnlEl) {
            const pnl = parseFloat(data.pnl_24h);
            const color = pnl >= 0 ? 'text-green-400' : 'text-red-400';
            const prefix = pnl >= 0 ? '+' : '';
            todaysPnlEl.className = `text-2xl font-bold ${color} mb-1`;
            todaysPnlEl.textContent = prefix + formatMoney(Math.abs(pnl), data.base_currency);
        }
        
        // P&L Percentage
        if (todaysPnlPercentEl) {
            const pctData = formatPercentage(data.pnl_percentage_24h);
            todaysPnlPercentEl.className = `text-xs ${pctData.color}`;
            todaysPnlPercentEl.textContent = pctData.text;
        }
        
        // Positions Count
        if (positionsCountEl) {
            positionsCountEl.textContent = data.positions.length;
        }
        
        // Cash Balance
        if (cashBalanceEl) {
            cashBalanceEl.textContent = formatMoney(data.cash_balance, data.base_currency);
        }
    }
}

/**
 * Initialize portfolio service
 */
async function initPortfolio() {
    // Subscribe to state changes
    subscribe(updatePortfolioUI);
    
    // Load initial data
    await loadPortfolio();
    
    // Refresh every 30 seconds
    setInterval(() => {
        loadPortfolio(1); // Only 1 retry for periodic updates
    }, 30000);
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPortfolio);
} else {
    initPortfolio();
}

// Export for use in other modules
window.PortfolioService = {
    subscribe,
    loadPortfolio,
    formatMoney,
    formatPercentage,
    getState: () => portfolioState
};