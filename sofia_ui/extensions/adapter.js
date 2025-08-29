/**
 * Sofia V2 API Adapter
 * Non-invasive adapter for UI-API communication
 * Handles WebSocket, API calls, and automatic trading
 */

(function(window) {
    'use strict';
    
    const config = window.SofiaConfig || {};
    
    class SofiaAdapter {
        constructor() {
            this.ws = null;
            this.reconnectAttempts = 0;
            this.reconnectDelay = config.WS_RECONNECT_BASE_DELAY || 1000;
            this.scoreCache = new Map();
            this.lastPrices = new Map();
            this.isConnected = false;
            this.healthInterval = null;
            this.scoreInterval = null;
            
            this.init();
        }
        
        init() {
            if (config.DEBUG) {
                console.log('[SofiaAdapter] Initializing with config:', config);
            }
            
            // Start health checks
            this.startHealthCheck();
            
            // Connect WebSocket if enabled
            if (config.ENABLE_WEBSOCKET) {
                this.connectWebSocket();
            }
            
            // Start score updates
            if (config.AUTO_TRADE_ENABLED) {
                this.startScoreUpdates();
            }
        }
        
        // Health check ping
        async startHealthCheck() {
            const checkHealth = async () => {
                try {
                    const response = await fetch(`${config.API_BASE}/health`);
                    const data = await response.json();
                    
                    if (config.DEBUG) {
                        console.log('[Health] API status:', data);
                    }
                    
                    // Emit health event
                    this.emit('health', data);
                } catch (error) {
                    console.error('[Health] Check failed:', error);
                    this.emit('health_error', error);
                }
            };
            
            // Initial check
            checkHealth();
            
            // Schedule periodic checks
            this.healthInterval = setInterval(checkHealth, config.HEALTH_PING_INTERVAL);
        }
        
        // WebSocket connection with exponential backoff
        connectWebSocket() {
            if (!config.WS_URL) {
                console.warn('[WebSocket] No WS_URL configured');
                return;
            }
            
            try {
                this.ws = new WebSocket(config.WS_URL);
                
                this.ws.onopen = () => {
                    console.log('[WebSocket] Connected to', config.WS_URL);
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    this.reconnectDelay = config.WS_RECONNECT_BASE_DELAY;
                    this.emit('ws_connected');
                };
                
                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.handleWebSocketMessage(data);
                    } catch (error) {
                        console.error('[WebSocket] Message parse error:', error);
                    }
                };
                
                this.ws.onerror = (error) => {
                    console.error('[WebSocket] Error:', error);
                    this.emit('ws_error', error);
                };
                
                this.ws.onclose = () => {
                    console.log('[WebSocket] Disconnected');
                    this.isConnected = false;
                    this.emit('ws_disconnected');
                    this.scheduleReconnect();
                };
                
            } catch (error) {
                console.error('[WebSocket] Connection failed:', error);
                this.scheduleReconnect();
            }
        }
        
        // Exponential backoff reconnection
        scheduleReconnect() {
            if (this.reconnectAttempts >= 10) {
                console.error('[WebSocket] Max reconnection attempts reached');
                return;
            }
            
            this.reconnectAttempts++;
            const delay = Math.min(
                this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
                config.WS_RECONNECT_MAX_DELAY
            );
            
            console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
            
            setTimeout(() => {
                this.connectWebSocket();
            }, delay);
        }
        
        // Handle incoming WebSocket messages
        handleWebSocketMessage(data) {
            if (config.DEBUG) {
                console.log('[WebSocket] Message:', data);
            }
            
            // Handle different message types
            if (data.type === 'price') {
                this.handlePriceUpdate(data);
            } else if (data.type === 'trade') {
                this.handleTradeSignal(data);
            } else if (data.type === 'alert') {
                this.handleAlert(data);
            }
            
            // Emit generic message event
            this.emit('ws_message', data);
        }
        
        // Handle price updates
        handlePriceUpdate(data) {
            const { symbol, price, timestamp } = data;
            this.lastPrices.set(symbol, { price, timestamp });
            this.emit('price_update', { symbol, price, timestamp });
            
            // Trigger trade evaluation if auto-trading enabled
            if (config.AUTO_TRADE_ENABLED) {
                this.evaluateTrade(symbol, price);
            }
        }
        
        // Get AI score for symbol
        async getAIScore(symbol, horizon = config.DEFAULT_HORIZON) {
            try {
                const response = await fetch(`${config.API_BASE}/ai/score`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol, horizon })
                });
                
                if (!response.ok) {
                    throw new Error(`Score request failed: ${response.status}`);
                }
                
                const data = await response.json();
                
                // Cache the score
                this.scoreCache.set(symbol, {
                    score: data.score0_100,
                    prob_up: data.prob_up,
                    features: data.features_used,
                    timestamp: Date.now()
                });
                
                if (config.DEBUG) {
                    console.log(`[AI Score] ${symbol}:`, data);
                }
                
                this.emit('ai_score', { symbol, ...data });
                return data;
                
            } catch (error) {
                console.error(`[AI Score] Error for ${symbol}:`, error);
                this.emit('ai_score_error', { symbol, error });
                return null;
            }
        }
        
        // Evaluate and execute trade
        async evaluateTrade(symbol, price) {
            const score = await this.getAIScore(symbol);
            
            if (!score) return;
            
            // Check if score meets threshold
            if (score.score0_100 >= config.MIN_SCORE_THRESHOLD) {
                await this.executeTrade(symbol, price, score.score0_100);
            }
        }
        
        // Execute trade via API
        async executeTrade(symbol, price, score) {
            try {
                const response = await fetch(`${config.API_BASE}/trade/on_tick`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol, price, score })
                });
                
                const result = await response.json();
                
                if (config.DEBUG) {
                    console.log(`[Trade] ${symbol} @ ${price} (score: ${score}):`, result);
                }
                
                this.emit('trade_executed', { symbol, price, score, result });
                
                // Update account status
                await this.getAccountStatus();
                
                return result;
                
            } catch (error) {
                console.error(`[Trade] Execution failed for ${symbol}:`, error);
                this.emit('trade_error', { symbol, error });
                return null;
            }
        }
        
        // Get account status
        async getAccountStatus() {
            try {
                const response = await fetch(`${config.API_BASE}/trade/account`);
                const account = await response.json();
                
                if (config.DEBUG) {
                    console.log('[Account]', account);
                }
                
                this.emit('account_update', account);
                return account;
                
            } catch (error) {
                console.error('[Account] Status fetch failed:', error);
                return null;
            }
        }
        
        // Start periodic score updates for all symbols
        startScoreUpdates() {
            const updateScores = async () => {
                for (const symbol of config.SYMBOLS) {
                    await this.getAIScore(symbol);
                    
                    // Check if we have price for this symbol
                    const priceData = this.lastPrices.get(symbol);
                    if (priceData) {
                        await this.evaluateTrade(symbol, priceData.price);
                    }
                }
            };
            
            // Initial update
            updateScores();
            
            // Schedule periodic updates
            this.scoreInterval = setInterval(updateScores, config.SCORE_UPDATE_INTERVAL);
        }
        
        // Handle trade signals
        handleTradeSignal(data) {
            console.log('[Trade Signal]', data);
            this.emit('trade_signal', data);
        }
        
        // Handle alerts (whale, news, etc.)
        handleAlert(data) {
            console.log('[Alert]', data);
            this.emit('alert', data);
        }
        
        // Event emitter functionality
        emit(event, data) {
            const customEvent = new CustomEvent(`sofia:${event}`, { detail: data });
            window.dispatchEvent(customEvent);
        }
        
        // Cleanup
        destroy() {
            if (this.healthInterval) {
                clearInterval(this.healthInterval);
            }
            
            if (this.scoreInterval) {
                clearInterval(this.scoreInterval);
            }
            
            if (this.ws) {
                this.ws.close();
            }
        }
    }
    
    // Initialize adapter and attach to window
    window.SofiaAdapter = SofiaAdapter;
    window.sofiaAdapter = new SofiaAdapter();
    
    // Log initialization
    console.log('[Sofia V2] Adapter initialized. Listen for events with:');
    console.log("window.addEventListener('sofia:EVENT_NAME', (e) => console.log(e.detail))");
    
})(window);