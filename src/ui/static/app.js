// Main application JavaScript
// API helper functions and event handlers

// API Base URL
const API_BASE = window.location.origin;

// API Fetch Helper
async function apiFetch(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    };
    
    const response = await fetch(API_BASE + url, {...defaultOptions, ...options});
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({detail: 'Unknown error'}));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }
    
    return response.json();
}

// Toast notification helper
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999;';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show`;
    toast.role = 'alert';
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    toastContainer.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Format number with commas
function formatNumber(num) {
    return new Intl.NumberFormat('en-US').format(num);
}

// Format currency
function formatCurrency(num, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
    }).format(num);
}

// Format percentage
function formatPercent(num) {
    return `${num.toFixed(2)}%`;
}

// WebSocket connection for real-time data (optional)
class DataStream {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.handlers = {};
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
    }
    
    connect() {
        try {
            this.ws = new WebSocket(this.url);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectDelay = 1000;
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    const handler = this.handlers[data.type];
                    if (handler) {
                        handler(data);
                    }
                } catch (error) {
                    console.error('WebSocket message error:', error);
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.reconnect();
            };
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.reconnect();
        }
    }
    
    reconnect() {
        setTimeout(() => {
            console.log('Attempting to reconnect...');
            this.connect();
            this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
        }, this.reconnectDelay);
    }
    
    on(type, handler) {
        this.handlers[type] = handler;
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }
    
    close() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Global data stream instance (optional)
// const dataStream = new DataStream('ws://localhost:8000/ws');

// Poll for connection status
async function checkConnectionStatus() {
    try {
        const response = await fetch(API_BASE + '/api/health');
        const data = await response.json();
        
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            if (data.status === 'ok') {
                statusElement.innerHTML = '<span class="badge bg-success">Connected</span>';
            } else {
                statusElement.innerHTML = '<span class="badge bg-warning">Degraded</span>';
            }
        }
    } catch (error) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.innerHTML = '<span class="badge bg-danger">Disconnected</span>';
        }
    }
}

// Check connection every 10 seconds
setInterval(checkConnectionStatus, 10000);
checkConnectionStatus();

// Symbol search autocomplete
function setupSymbolAutocomplete(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    let timeout;
    input.addEventListener('input', function() {
        clearTimeout(timeout);
        timeout = setTimeout(async () => {
            const query = this.value;
            if (query.length < 2) return;
            
            try {
                const symbols = await apiFetch('/api/quotes/symbols');
                // Filter and show suggestions
                const filtered = symbols.filter(s => 
                    s.toLowerCase().includes(query.toLowerCase())
                );
                // Update datalist or show dropdown
                console.log('Suggestions:', filtered);
            } catch (error) {
                console.error('Symbol search error:', error);
            }
        }, 300);
    });
}

// Export utility functions
window.apiFetch = apiFetch;
window.showToast = showToast;
window.formatNumber = formatNumber;
window.formatCurrency = formatCurrency;
window.formatPercent = formatPercent;
window.DataStream = DataStream;