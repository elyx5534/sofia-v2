/**
 * usePortfolio Hook
 * Robust portfolio data fetching with retry and auto-refresh
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { portfolioService, PortfolioSummary } from '../services/portfolio-service';

export interface UsePortfolioOptions {
  autoRefresh?: boolean;
  refreshInterval?: number;
  maxRetries?: number;
  retryDelay?: number;
}

export interface UsePortfolioResult {
  data: PortfolioSummary | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  isStale: boolean;
}

export const usePortfolio = (options: UsePortfolioOptions = {}): UsePortfolioResult => {
  const {
    autoRefresh = true,
    refreshInterval = 30000, // 30 seconds
    maxRetries = 2,
    retryDelay = 1000,
  } = options;

  const [data, setData] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [isStale, setIsStale] = useState<boolean>(false);

  const retryCount = useRef(0);
  const refreshTimer = useRef<NodeJS.Timeout | null>(null);
  const staleTimer = useRef<NodeJS.Timeout | null>(null);
  const isMounted = useRef(true);

  const fetchPortfolio = useCallback(async (isRetry: boolean = false) => {
    // Don't fetch if component is unmounted
    if (!isMounted.current) return;

    // Set loading state only on initial fetch
    if (!isRetry && !data) {
      setLoading(true);
    }

    setError(null);
    setIsStale(false);

    try {
      const summary = await portfolioService.fetchPortfolioSummary();
      
      if (isMounted.current) {
        setData(summary);
        setLoading(false);
        retryCount.current = 0;

        // Set stale timer (data becomes stale after 60 seconds)
        if (staleTimer.current) {
          clearTimeout(staleTimer.current);
        }
        staleTimer.current = setTimeout(() => {
          if (isMounted.current) {
            setIsStale(true);
          }
        }, 60000);
      }
    } catch (err) {
      if (!isMounted.current) return;

      const error = err as Error;
      console.error('Portfolio fetch error:', error);

      // Retry logic
      if (retryCount.current < maxRetries) {
        retryCount.current++;
        console.log(`Retrying... (${retryCount.current}/${maxRetries})`);
        
        setTimeout(() => {
          if (isMounted.current) {
            fetchPortfolio(true);
          }
        }, retryDelay * retryCount.current);
      } else {
        setError(error);
        setLoading(false);
        setIsStale(true);
      }
    }
  }, [data, maxRetries, retryDelay]);

  // Initial fetch
  useEffect(() => {
    isMounted.current = true;
    fetchPortfolio();

    return () => {
      isMounted.current = false;
      portfolioService.cleanup();
      
      if (refreshTimer.current) {
        clearInterval(refreshTimer.current);
      }
      if (staleTimer.current) {
        clearTimeout(staleTimer.current);
      }
    };
  }, []);

  // Auto-refresh
  useEffect(() => {
    if (autoRefresh && refreshInterval > 0) {
      refreshTimer.current = setInterval(() => {
        if (isMounted.current) {
          fetchPortfolio();
        }
      }, refreshInterval);

      return () => {
        if (refreshTimer.current) {
          clearInterval(refreshTimer.current);
        }
      };
    }
  }, [autoRefresh, refreshInterval, fetchPortfolio]);

  const refetch = useCallback(async () => {
    retryCount.current = 0;
    await fetchPortfolio();
  }, [fetchPortfolio]);

  return {
    data,
    loading,
    error,
    refetch,
    isStale,
  };
};

export default usePortfolio;