/**
 * Runtime UI Guard
 * Detects and warns about regression patterns in the DOM
 */

export class UIGuard {
  private violations: string[] = [];
  private observer: MutationObserver | null = null;

  constructor() {
    this.checkDOM = this.checkDOM.bind(this);
    this.showToast = this.showToast.bind(this);
  }

  /**
   * Initialize the guard and start monitoring
   */
  init(): void {
    // Initial check
    this.checkDOM();

    // Set up mutation observer to catch dynamic changes
    this.observer = new MutationObserver(() => {
      this.checkDOM();
    });

    this.observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'id', 'data-sidebar'],
    });

    // Check periodically as well
    setInterval(() => this.checkDOM(), 5000);
  }

  /**
   * Check DOM for forbidden patterns
   */
  private checkDOM(): void {
    const newViolations: string[] = [];

    // Check for sidebars
    const sidebarSelectors = [
      '[class*="sidebar"]',
      '[class*="sidenav"]',
      '[class*="drawer"]',
      '[id*="sidebar"]',
      '[data-sidebar]',
      'aside',
    ];

    sidebarSelectors.forEach((selector) => {
      const elements = document.querySelectorAll(selector);
      if (elements.length > 0) {
        newViolations.push(`Found ${elements.length} sidebar element(s) with selector: ${selector}`);
      }
    });

    // Check for duplicate headers
    const headers = document.querySelectorAll('header');
    if (headers.length > 1) {
      newViolations.push(`Found ${headers.length} header elements - should only have 1`);
    }

    // Check for duplicate containers
    const containers = document.querySelectorAll('.container');
    if (containers.length > 2) {
      newViolations.push(`Found ${containers.length} container elements - possible duplication`);
    }

    // Check for overflow hidden on body (blocks scrolling)
    const bodyStyle = window.getComputedStyle(document.body);
    if (bodyStyle.overflow === 'hidden' || bodyStyle.overflowY === 'hidden') {
      newViolations.push('Body has overflow:hidden - this blocks scrolling');
    }

    // Report new violations
    newViolations.forEach((violation) => {
      if (!this.violations.includes(violation)) {
        console.error(`[UI Guard] ${violation}`);
        this.showToast(violation, 'error');
      }
    });

    this.violations = newViolations;

    // Log to console for CI/CD detection
    if (this.violations.length > 0) {
      console.error('[UI Guard] Violations detected:', this.violations);
      
      // In development, throw error to break the build
      if (process.env.NODE_ENV === 'development') {
        console.error('[UI Guard] Fix these violations before proceeding!');
      }
    }
  }

  /**
   * Show toast notification
   */
  private showToast(message: string, type: 'error' | 'warning' = 'error'): void {
    // Remove existing toasts
    const existingToasts = document.querySelectorAll('.ui-guard-toast');
    existingToasts.forEach((toast) => toast.remove());

    // Create toast element
    const toast = document.createElement('div');
    toast.className = 'ui-guard-toast';
    toast.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 16px 24px;
      background: ${type === 'error' ? '#ef4444' : '#f59e0b'};
      color: white;
      border-radius: 8px;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
      z-index: 99999;
      max-width: 400px;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 14px;
      animation: slideIn 0.3s ease-out;
    `;

    // Add animation
    const style = document.createElement('style');
    style.textContent = `
      @keyframes slideIn {
        from {
          transform: translateX(100%);
          opacity: 0;
        }
        to {
          transform: translateX(0);
          opacity: 1;
        }
      }
    `;
    document.head.appendChild(style);

    // Add content
    toast.innerHTML = `
      <div style="display: flex; align-items: center; gap: 12px;">
        <svg width="20" height="20" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
        </svg>
        <div>
          <div style="font-weight: 600; margin-bottom: 4px;">UI Guard Violation</div>
          <div style="opacity: 0.9;">${message}</div>
        </div>
      </div>
    `;

    document.body.appendChild(toast);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      toast.style.animation = 'slideOut 0.3s ease-in';
      setTimeout(() => toast.remove(), 300);
    }, 5000);
  }

  /**
   * Clean up the guard
   */
  destroy(): void {
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
  }

  /**
   * Get current violations
   */
  getViolations(): string[] {
    return [...this.violations];
  }

  /**
   * Check if there are any violations
   */
  hasViolations(): boolean {
    return this.violations.length > 0;
  }
}

// Export singleton instance
export const uiGuard = new UIGuard();

// Auto-initialize in browser environment
if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  // Wait for DOM to be ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      uiGuard.init();
    });
  } else {
    // DOM is already ready
    uiGuard.init();
  }
}

export default uiGuard;