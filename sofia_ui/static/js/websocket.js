/**
 * WebSocket Manager for Real-time Updates
 * Handles price updates, alerts, and portfolio changes
 */

class WebSocketManager {
    constructor() {
        this.connections = {};
        this.reconnectInterval = 5000;
        this.maxReconnectAttempts = 10;
        this.reconnectAttempts = {};
        this.callbacks = {};
        this.isActive = true;
    }

    /**
     * Connect to WebSocket endpoint
     */
    connect(name, url, onMessage, onError = null) {
        if (this.connections[name]) {
            console.log(`WebSocket ${name} already connected`);
            return;
        }

        console.log(`Connecting to WebSocket: ${name} at ${url}`);
        
        const ws = new WebSocket(url);
        this.connections[name] = ws;
        this.reconnectAttempts[name] = 0;
        
        ws.onopen = () => {
            console.log(`WebSocket ${name} connected`);
            this.reconnectAttempts[name] = 0;
            this.showNotification(`Connected to ${name}`, 'success');
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (onMessage) {
                    onMessage(data);
                }
                // Trigger any registered callbacks
                if (this.callbacks[name]) {
                    this.callbacks[name].forEach(callback => callback(data));
                }
            } catch (error) {
                console.error(`Error parsing WebSocket message from ${name}:`, error);
            }
        };

        ws.onerror = (error) => {
            console.error(`WebSocket ${name} error:`, error);
            if (onError) {
                onError(error);
            }
        };

        ws.onclose = () => {
            console.log(`WebSocket ${name} disconnected`);
            delete this.connections[name];
            
            // Attempt reconnection
            if (this.isActive && this.reconnectAttempts[name] < this.maxReconnectAttempts) {
                this.reconnectAttempts[name]++;
                console.log(`Reconnecting ${name} (attempt ${this.reconnectAttempts[name]})...`);
                setTimeout(() => {
                    if (this.isActive) {
                        this.connect(name, url, onMessage, onError);
                    }
                }, this.reconnectInterval);
            }
        };
    }

    /**
     * Send message through WebSocket
     */
    send(name, data) {
        const ws = this.connections[name];
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        } else {
            console.warn(`WebSocket ${name} is not connected`);
        }
    }

    /**
     * Close specific connection
     */
    close(name) {
        const ws = this.connections[name];
        if (ws) {
            ws.close();
            delete this.connections[name];
        }
    }

    /**
     * Close all connections
     */
    closeAll() {
        this.isActive = false;
        Object.keys(this.connections).forEach(name => {
            this.close(name);
        });
    }

    /**
     * Register callback for WebSocket messages
     */
    on(name, callback) {
        if (!this.callbacks[name]) {
            this.callbacks[name] = [];
        }
        this.callbacks[name].push(callback);
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check' : 'info'}-circle"></i>
            <span>${message}</span>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 500);
        }, 3000);
    }
}

/**
 * Real-time Price Updates Handler
 */
class PriceUpdater {
    constructor(wsManager) {
        this.wsManager = wsManager;
        this.priceElements = {};
        this.charts = {};
    }

    /**
     * Initialize price updates
     */
    init() {
        // Connect to price WebSocket
        this.wsManager.connect(
            'prices',
            'ws://localhost:8007/ws/market',
            (data) => this.handlePriceUpdate(data)
        );

        // Find all price elements
        this.findPriceElements();
    }

    /**
     * Find elements that display prices
     */
    findPriceElements() {
        document.querySelectorAll('[data-price-symbol]').forEach(element => {
            const symbol = element.dataset.priceSymbol;
            if (!this.priceElements[symbol]) {
                this.priceElements[symbol] = [];
            }
            this.priceElements[symbol].push(element);
        });
    }

    /**
     * Handle price update from WebSocket
     */
    handlePriceUpdate(data) {
        if (data.type === 'market_update' && data.data) {
            Object.entries(data.data).forEach(([symbol, priceData]) => {
                this.updatePrice(symbol, priceData);
            });
        }
    }

    /**
     * Update price in UI
     */
    updatePrice(symbol, priceData) {
        const elements = this.priceElements[symbol] || [];
        
        elements.forEach(element => {
            const oldPrice = parseFloat(element.textContent.replace(/[^0-9.-]/g, ''));
            const newPrice = priceData.price;
            
            // Update price text
            element.textContent = this.formatPrice(newPrice);
            
            // Add animation class
            if (newPrice > oldPrice) {
                element.classList.add('price-up');
                setTimeout(() => element.classList.remove('price-up'), 1000);
            } else if (newPrice < oldPrice) {
                element.classList.add('price-down');
                setTimeout(() => element.classList.remove('price-down'), 1000);
            }
        });

        // Update charts if exists
        if (this.charts[symbol]) {
            this.updateChart(symbol, priceData);
        }
    }

    /**
     * Format price for display
     */
    formatPrice(price) {
        if (price > 1000) {
            return `$${price.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
        } else if (price > 10) {
            return `$${price.toFixed(2)}`;
        } else {
            return `$${price.toFixed(4)}`;
        }
    }

    /**
     * Update chart with new price
     */
    updateChart(symbol, priceData) {
        const chart = this.charts[symbol];
        if (chart) {
            // Add new data point
            chart.data.labels.push(new Date().toLocaleTimeString());
            chart.data.datasets[0].data.push(priceData.price);
            
            // Keep only last 50 points
            if (chart.data.labels.length > 50) {
                chart.data.labels.shift();
                chart.data.datasets[0].data.shift();
            }
            
            chart.update('none'); // Update without animation
        }
    }
}

/**
 * Real-time Alert Handler
 */
class AlertUpdater {
    constructor(wsManager) {
        this.wsManager = wsManager;
        this.alertContainer = null;
        this.maxAlerts = 10;
        this.alerts = [];
    }

    /**
     * Initialize alert updates
     */
    init() {
        this.alertContainer = document.getElementById('alert-container');
        
        // Connect to alerts WebSocket
        this.wsManager.connect(
            'alerts',
            'ws://localhost:8007/ws/alerts',
            (data) => this.handleAlertUpdate(data)
        );
    }

    /**
     * Handle alert update from WebSocket
     */
    handleAlertUpdate(data) {
        if (data.type === 'alert' && data.data) {
            this.addAlert(data.data);
        }
    }

    /**
     * Add new alert to UI
     */
    addAlert(alert) {
        // Add to alerts array
        this.alerts.unshift(alert);
        if (this.alerts.length > this.maxAlerts) {
            this.alerts.pop();
        }

        // Create alert element
        const alertElement = this.createAlertElement(alert);
        
        // Add to container
        if (this.alertContainer) {
            this.alertContainer.insertBefore(alertElement, this.alertContainer.firstChild);
            
            // Remove oldest if too many
            while (this.alertContainer.children.length > this.maxAlerts) {
                this.alertContainer.removeChild(this.alertContainer.lastChild);
            }
        }

        // Show browser notification if permitted
        this.showBrowserNotification(alert);
        
        // Play sound for critical alerts
        if (alert.severity === 'critical') {
            this.playAlertSound();
        }
    }

    /**
     * Create alert DOM element
     */
    createAlertElement(alert) {
        const div = document.createElement('div');
        div.className = `alert-item alert-${alert.severity} fade-in`;
        
        const iconMap = {
            'hedge': '🛡️',
            'momentum_long': '📈',
            'short': '📉',
            'close_position': '❌'
        };
        
        div.innerHTML = `
            <div class="alert-header">
                <span class="alert-icon">${iconMap[alert.action] || '📊'}</span>
                <span class="alert-severity badge badge-${alert.severity}">${alert.severity.toUpperCase()}</span>
                <span class="alert-time">${new Date(alert.timestamp).toLocaleTimeString()}</span>
            </div>
            <div class="alert-message">${alert.message}</div>
            <div class="alert-action">
                <button class="btn-sm btn-primary" onclick="executeAlert('${alert.id}')">Execute</button>
                <button class="btn-sm btn-secondary" onclick="dismissAlert('${alert.id}')">Dismiss</button>
            </div>
        `;
        
        return div;
    }

    /**
     * Show browser notification
     */
    showBrowserNotification(alert) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('Sofia Alert', {
                body: alert.message,
                icon: '/static/img/logo.png',
                badge: '/static/img/badge.png',
                tag: alert.id,
                requireInteraction: alert.severity === 'critical'
            });
        }
    }

    /**
     * Play alert sound
     */
    playAlertSound() {
        const audio = new Audio('/static/sounds/alert.mp3');
        audio.play().catch(e => console.log('Could not play alert sound:', e));
    }
}

/**
 * Real-time Portfolio Updates
 */
class PortfolioUpdater {
    constructor(wsManager) {
        this.wsManager = wsManager;
        this.portfolioElements = {};
    }

    /**
     * Initialize portfolio updates
     */
    init() {
        // Connect to portfolio WebSocket
        this.wsManager.connect(
            'portfolio',
            'ws://localhost:8007/ws/portfolio',
            (data) => this.handlePortfolioUpdate(data)
        );

        this.findPortfolioElements();
    }

    /**
     * Find portfolio display elements
     */
    findPortfolioElements() {
        this.portfolioElements = {
            balance: document.getElementById('portfolio-balance'),
            pnl: document.getElementById('portfolio-pnl'),
            pnlPercent: document.getElementById('portfolio-pnl-percent'),
            positions: document.getElementById('positions-container')
        };
    }

    /**
     * Handle portfolio update
     */
    handlePortfolioUpdate(data) {
        if (data.type === 'portfolio_update' && data.data) {
            this.updatePortfolioStats(data.data);
            this.updatePositions(data.data.positions);
        }
    }

    /**
     * Update portfolio statistics
     */
    updatePortfolioStats(data) {
        if (this.portfolioElements.balance) {
            this.portfolioElements.balance.textContent = `$${data.balance.toLocaleString()}`;
        }
        
        if (this.portfolioElements.pnl) {
            const pnl = data.daily_pnl;
            this.portfolioElements.pnl.textContent = `$${Math.abs(pnl).toFixed(2)}`;
            this.portfolioElements.pnl.className = pnl >= 0 ? 'text-green-400' : 'text-red-400';
        }
        
        if (this.portfolioElements.pnlPercent) {
            const pnlPercent = (data.daily_pnl / data.balance) * 100;
            this.portfolioElements.pnlPercent.textContent = `${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%`;
            this.portfolioElements.pnlPercent.className = pnlPercent >= 0 ? 'text-green-400' : 'text-red-400';
        }
    }

    /**
     * Update positions display
     */
    updatePositions(positions) {
        if (!this.portfolioElements.positions || !positions) return;
        
        const container = this.portfolioElements.positions;
        container.innerHTML = '';
        
        positions.forEach(position => {
            const positionElement = this.createPositionElement(position);
            container.appendChild(positionElement);
        });
    }

    /**
     * Create position DOM element
     */
    createPositionElement(position) {
        const div = document.createElement('div');
        div.className = 'position-item';
        
        const pnlClass = position.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400';
        const pnlSign = position.unrealized_pnl >= 0 ? '+' : '';
        
        div.innerHTML = `
            <div class="position-header">
                <span class="position-symbol">${position.symbol}</span>
                <span class="position-side badge badge-${position.side}">${position.side.toUpperCase()}</span>
            </div>
            <div class="position-details">
                <div class="position-size">Size: ${position.size}</div>
                <div class="position-entry">Entry: $${position.entry_price}</div>
                <div class="position-current">Current: $${position.current_price}</div>
                <div class="position-pnl ${pnlClass}">
                    PnL: ${pnlSign}$${Math.abs(position.unrealized_pnl).toFixed(2)} 
                    (${pnlSign}${position.pnl_percent.toFixed(2)}%)
                </div>
            </div>
        `;
        
        return div;
    }
}

// Initialize WebSocket connections when page loads
document.addEventListener('DOMContentLoaded', () => {
    const wsManager = new WebSocketManager();
    
    // Initialize updaters
    const priceUpdater = new PriceUpdater(wsManager);
    const alertUpdater = new AlertUpdater(wsManager);
    const portfolioUpdater = new PortfolioUpdater(wsManager);
    
    // Start connections
    priceUpdater.init();
    alertUpdater.init();
    portfolioUpdater.init();
    
    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
    
    // Export for global access
    window.wsManager = wsManager;
    window.priceUpdater = priceUpdater;
    window.alertUpdater = alertUpdater;
    window.portfolioUpdater = portfolioUpdater;
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.wsManager) {
        window.wsManager.closeAll();
    }
});

/**
 * Execute alert action
 */
function executeAlert(alertId) {
    fetch('/api/execute-alert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_id: alertId })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Alert executed:', data);
        window.wsManager.showNotification('Alert executed successfully', 'success');
    })
    .catch(error => {
        console.error('Error executing alert:', error);
        window.wsManager.showNotification('Failed to execute alert', 'error');
    });
}

/**
 * Dismiss alert
 */
function dismissAlert(alertId) {
    const alertElement = document.querySelector(`[data-alert-id="${alertId}"]`);
    if (alertElement) {
        alertElement.classList.add('fade-out');
        setTimeout(() => alertElement.remove(), 500);
    }
}