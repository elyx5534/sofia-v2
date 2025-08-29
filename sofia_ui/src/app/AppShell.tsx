import React from 'react';
import { Link, useLocation } from 'react-router-dom';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const location = useLocation();

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: 'fas fa-chart-line' },
    { path: '/strategies', label: 'Strategies', icon: 'fas fa-robot' },
    { path: '/backtests', label: 'Backtests', icon: 'fas fa-history' },
    { path: '/signals', label: 'Signals', icon: 'fas fa-bell' },
    { path: '/markets', label: 'Markets', icon: 'fas fa-coins' },
    { path: '/settings', label: 'Settings', icon: 'fas fa-cog' },
    { path: '/status', label: 'Status', icon: 'fas fa-heartbeat' },
  ];

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="min-h-screen bg-background">
      {/* Single Navbar - NO SIDEBAR */}
      <header className="sticky top-0 z-50 w-full border-b border-gray-800 bg-gray-900/95 backdrop-blur supports-[backdrop-filter]:bg-gray-900/75">
        <div className="container mx-auto px-4">
          <div className="flex h-16 items-center justify-between">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-2">
              <i className="fas fa-robot text-2xl text-primary"></i>
              <span className="text-xl font-bold text-white">Sofia V2</span>
            </Link>

            {/* Navigation */}
            <nav className="hidden md:flex items-center gap-6">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-2 text-sm font-medium transition-colors hover:text-primary ${
                    isActive(item.path) ? 'text-primary' : 'text-gray-400'
                  }`}
                >
                  <i className={item.icon}></i>
                  <span>{item.label}</span>
                </Link>
              ))}
            </nav>

            {/* Right Actions */}
            <div className="flex items-center gap-4">
              {/* Theme Toggle */}
              <button
                className="text-gray-400 hover:text-white transition-colors"
                aria-label="Toggle theme"
              >
                <i className="fas fa-moon"></i>
              </button>

              {/* Profile */}
              <button
                className="text-gray-400 hover:text-white transition-colors"
                aria-label="Profile"
              >
                <i className="fas fa-user-circle text-xl"></i>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content - No sidebar, full width */}
      <main className="container mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  );
};

export default AppShell;