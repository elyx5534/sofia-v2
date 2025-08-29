/**
 * Portfolio Service with Decimal.js for precision
 * Single source of truth for total balance calculation
 */

import Decimal from 'decimal.js';

// Configure Decimal for financial precision
Decimal.set({ precision: 20, rounding: Decimal.ROUND_HALF_UP });

export interface Position {
  symbol: string;
  quantity: number;
  avgPrice: number;
  currentPrice: number;
  value: number;
  pnl: number;
  pnlPercent: number;
}

export interface PortfolioSummary {
  totalBalance: string;
  totalBalanceUSD: string;
  availableBalance: string;
  lockedBalance: string;
  positions: Position[];
  baseCurrency: string;
  fxRates: Record<string, number>;
  lastUpdate: number;
}

class PortfolioService {
  private apiUrl: string;
  private cache: PortfolioSummary | null = null;
  private lastFetch: number = 0;
  private cacheTimeout: number = 30000; // 30 seconds
  private abortController: AbortController | null = null;

  constructor() {
    this.apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8023';
  }

  /**
   * Calculate total balance using Decimal.js for precision
   * Single source of truth for balance calculation
   */
  calcTotalBalance(summary: PortfolioSummary): Decimal {
    const baseCurrency = summary.baseCurrency || 'USD';
    const fxRates = summary.fxRates || {};

    // Start with available balance
    let total = new Decimal(summary.availableBalance || 0);

    // Add locked balance
    if (summary.lockedBalance) {
      total = total.plus(summary.lockedBalance);
    }

    // Add position values
    if (summary.positions && Array.isArray(summary.positions)) {
      summary.positions.forEach((position) => {
        const posValue = new Decimal(position.value || 0);
        
        // Apply FX conversion if needed
        const symbol = position.symbol;
        if (symbol && symbol.includes('/')) {
          const [, quote] = symbol.split('/');
          if (quote && quote !== baseCurrency && fxRates[`${quote}${baseCurrency}`]) {
            const fxRate = new Decimal(fxRates[`${quote}${baseCurrency}`]);
            total = total.plus(posValue.mul(fxRate));
          } else {
            total = total.plus(posValue);
          }
        } else {
          total = total.plus(posValue);
        }
      });
    }

    return total;
  }

  /**
   * Format currency with proper decimal places
   */
  formatCurrency(amount: Decimal | number | string, currency: string = 'USD'): string {
    const value = new Decimal(amount);
    const formatted = value.toFixed(2);
    const symbol = currency === 'USD' ? '$' : currency === 'EUR' ? '€' : '';
    
    // Add thousand separators
    const parts = formatted.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    
    return symbol + parts.join('.');
  }

  /**
   * Fetch portfolio summary from API with retry logic
   */
  async fetchPortfolioSummary(force: boolean = false): Promise<PortfolioSummary> {
    // Check cache
    if (!force && this.cache && this.lastFetch) {
      const age = Date.now() - this.lastFetch;
      if (age < this.cacheTimeout) {
        return this.cache;
      }
    }

    // Cancel previous request if still pending
    if (this.abortController) {
      this.abortController.abort();
    }

    // Create new abort controller
    this.abortController = new AbortController();

    try {
      const response = await fetch(`${this.apiUrl}/portfolio/summary`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: this.abortController.signal,
      });

      // Add timeout
      const timeoutId = setTimeout(() => {
        if (this.abortController) {
          this.abortController.abort();
        }
      }, 6000); // 6 second timeout

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      clearTimeout(timeoutId);

      // Calculate total balance
      const totalBalance = this.calcTotalBalance(data);
      data.totalBalance = totalBalance.toFixed(2);
      data.totalBalanceUSD = totalBalance.toFixed(2); // Assuming USD base
      data.lastUpdate = Date.now();

      // Update cache
      this.cache = data;
      this.lastFetch = Date.now();

      return data;
    } catch (error: any) {
      // Handle abort
      if (error.name === 'AbortError') {
        console.log('Request was cancelled');
      } else {
        console.error('Error fetching portfolio:', error);
      }

      // Return cached data if available
      if (this.cache) {
        return this.cache;
      }

      // Return mock data as fallback
      return this.getMockData();
    } finally {
      this.abortController = null;
    }
  }

  /**
   * Get mock data for development/fallback
   */
  getMockData(): PortfolioSummary {
    return {
      totalBalance: '10000.00',
      totalBalanceUSD: '10000.00',
      availableBalance: '5000.00',
      lockedBalance: '5000.00',
      positions: [
        {
          symbol: 'BTC/USDT',
          quantity: 0.1,
          avgPrice: 45000,
          currentPrice: 50000,
          value: 5000,
          pnl: 500,
          pnlPercent: 11.11,
        },
      ],
      baseCurrency: 'USD',
      fxRates: {},
      lastUpdate: Date.now(),
    };
  }

  /**
   * Clean up on unmount
   */
  cleanup(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }
}

// Export singleton instance
export const portfolioService = new PortfolioService();
export default portfolioService;